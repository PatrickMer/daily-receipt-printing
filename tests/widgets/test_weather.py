"""Tests for widgets.weather — Open-Meteo weather forecast widget."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.actions import SetAction, TextAction
from core.context import Context
from widgets.weather import WeatherWidget


@pytest.fixture()
def widget() -> WeatherWidget:
    """Fresh WeatherWidget instance."""
    return WeatherWidget()


@pytest.fixture()
def context_morning() -> Context:
    """Context at 08:00 on 2026-06-21."""
    return Context(
        date=datetime.date(2026, 6, 21),
        time=datetime.time(8, 0),
        receipt_name="test",
    )


def _make_forecast_response(start_hour: int = 0, num_hours: int = 24) -> dict[str, Any]:
    """Build a realistic Open-Meteo hourly forecast response."""
    times = [
        f"2026-06-21T{h:02d}:00" for h in range(start_hour, start_hour + num_hours)
    ]
    temps = [18.0 + h * 0.5 for h in range(num_hours)]
    precips = [h * 5 for h in range(num_hours)]
    codes = [0] * num_hours
    return {
        "hourly": {
            "time": times,
            "temperature_2m": temps,
            "precipitation_probability": precips,
            "weathercode": codes,
        }
    }


def _make_geocoding_response(
    name: str = "Madrid", lat: float = 40.4168, lon: float = -3.7038
) -> dict[str, Any]:
    """Build a realistic Open-Meteo geocoding response."""
    return {
        "results": [
            {
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "country": "Spain",
            }
        ]
    }


class TestWeatherHappyPathCoords:
    """Happy path with direct coordinates."""

    @patch("widgets.weather.requests.get")
    def test_returns_formatted_weather_table(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Direct coords fetch forecast and return a formatted table."""
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()

        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 4}
        actions = widget.render(params, context_morning)

        # Should have: SetAction(bold), title text, SetAction(font=b),
        # header row, separator row, 4 data rows, SetAction(font=a)
        assert len(actions) >= 4
        assert isinstance(actions[0], SetAction)
        assert actions[0].bold is True

        title = actions[1]
        assert isinstance(title, TextAction)
        assert "Weather" in title.content
        assert "40.42, -3.70" in title.content

        # Check data rows contain hour information
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        # Title + header + separator + 4 data rows = 7 text actions
        assert len(text_actions) == 7

        # Verify first data row starts at 08:00
        data_rows = text_actions[3:]  # skip title, header, separator
        assert data_rows[0].content.startswith("08:00")

    @patch("widgets.weather.requests.get")
    def test_forecast_api_called_with_correct_params(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Verify the forecast API is called with the right parameters."""
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()
        mock_get.return_value = forecast_resp

        params = {
            "latitude": 40.4168,
            "longitude": -3.7038,
            "hours": 6,
            "timezone": "Europe/Madrid",
        }
        widget.render(params, context_morning)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["latitude"] == "40.4168"
        assert call_kwargs[1]["params"]["longitude"] == "-3.7038"
        assert call_kwargs[1]["params"]["timezone"] == "Europe/Madrid"
        assert call_kwargs[1]["timeout"] == 10


class TestWeatherHappyPathCity:
    """Happy path with city name — geocoding then forecast."""

    @patch("widgets.weather.requests.get")
    def test_geocoding_then_forecast(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """City name triggers geocoding call, then forecast fetch."""
        geocoding_resp = MagicMock()
        geocoding_resp.status_code = 200
        geocoding_resp.json.return_value = _make_geocoding_response()

        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()

        mock_get.side_effect = [geocoding_resp, forecast_resp]

        params = {"location": "Madrid", "hours": 3}
        actions = widget.render(params, context_morning)

        # Geocoding + forecast = 2 calls
        assert mock_get.call_count == 2

        # Title should contain city name
        title = actions[1]
        assert isinstance(title, TextAction)
        assert "Madrid" in title.content

    @patch("widgets.weather.requests.get")
    def test_geocoding_params(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Geocoding API called with correct city name."""
        geocoding_resp = MagicMock()
        geocoding_resp.status_code = 200
        geocoding_resp.json.return_value = _make_geocoding_response()

        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()

        mock_get.side_effect = [geocoding_resp, forecast_resp]

        params = {"location": "Barcelona", "hours": 2}
        widget.render(params, context_morning)

        first_call = mock_get.call_args_list[0]
        assert first_call[1]["params"]["name"] == "Barcelona"
        assert first_call[1]["params"]["count"] == "1"


class TestWeatherGeocodingFailure:
    """Geocoding failures return placeholder."""

    @patch("widgets.weather.requests.get")
    def test_geocoding_no_results(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Empty geocoding results produce unavailable placeholder."""
        geocoding_resp = MagicMock()
        geocoding_resp.status_code = 200
        geocoding_resp.json.return_value = {"results": []}

        mock_get.return_value = geocoding_resp

        params = {"location": "Nonexistentville", "hours": 4}
        actions = widget.render(params, context_morning)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[weather unavailable]" in actions[0].content

    @patch("widgets.weather.requests.get")
    def test_geocoding_none_results(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """No 'results' key in geocoding response returns placeholder."""
        geocoding_resp = MagicMock()
        geocoding_resp.status_code = 200
        geocoding_resp.json.return_value = {}

        mock_get.return_value = geocoding_resp

        params = {"location": "Nowhere", "hours": 4}
        actions = widget.render(params, context_morning)

        assert len(actions) == 1
        assert "[weather unavailable]" in actions[0].content


class TestWeatherForecastTimeout:
    """Forecast API timeout returns placeholder."""

    @patch("widgets.weather.requests.get")
    def test_timeout_returns_placeholder(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """requests.Timeout is caught and returns unavailable placeholder."""
        import requests as req

        mock_get.side_effect = req.Timeout("Connection timed out")

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 6}
        actions = widget.render(params, context_morning)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[weather unavailable]" in actions[0].content

    @patch("widgets.weather.requests.get")
    def test_connection_error_returns_placeholder(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """requests.ConnectionError is caught and returns unavailable placeholder."""
        import requests as req

        mock_get.side_effect = req.ConnectionError("DNS resolution failed")

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 6}
        actions = widget.render(params, context_morning)

        assert len(actions) == 1
        assert "[weather unavailable]" in actions[0].content


class TestWeatherMalformedResponse:
    """Malformed forecast response returns placeholder."""

    @patch("widgets.weather.requests.get")
    def test_missing_hourly_key(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Response missing 'hourly' key returns placeholder."""
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = {"daily": {}}

        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 6}
        actions = widget.render(params, context_morning)

        assert len(actions) == 1
        assert "[weather unavailable]" in actions[0].content

    @patch("widgets.weather.requests.get")
    def test_missing_temperature_key(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Response missing temperature data returns placeholder."""
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = {
            "hourly": {
                "time": ["2026-06-21T08:00"],
                # missing temperature_2m, precipitation_probability, weathercode
            }
        }

        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 6}
        actions = widget.render(params, context_morning)

        assert len(actions) == 1
        assert "[weather unavailable]" in actions[0].content


class TestWeatherHoursParam:
    """Hours param controls number of rows shown."""

    @patch("widgets.weather.requests.get")
    def test_hours_limits_rows(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
        context_morning: Context,
    ) -> None:
        """Setting hours=2 produces exactly 2 data rows."""
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()
        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 2}
        actions = widget.render(params, context_morning)

        # Count data rows (text actions excluding title, header, separator)
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        # title + header + separator + 2 data rows = 5
        assert len(text_actions) == 5

    @patch("widgets.weather.requests.get")
    def test_hours_default_is_12(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
    ) -> None:
        """Default hours=12 produces up to 12 data rows."""
        context = Context(
            date=datetime.date(2026, 6, 21),
            time=datetime.time(0, 0),
            receipt_name="test",
        )
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()
        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        # title + header + separator + 12 data rows = 15
        assert len(text_actions) == 15


class TestWeatherTimeFiltering:
    """Filters to only future hours based on context.time."""

    @patch("widgets.weather.requests.get")
    def test_filters_past_hours(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
    ) -> None:
        """Hours before context.time.hour are not shown."""
        # Context at 14:00 — should skip hours 0-13
        context = Context(
            date=datetime.date(2026, 6, 21),
            time=datetime.time(14, 0),
            receipt_name="test",
        )
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()
        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 24}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        data_rows = text_actions[3:]  # skip title, header, separator

        # 24 hours total, start at 14 => hours 14-23 = 10 rows
        assert len(data_rows) == 10
        # First row should start at 14:00
        assert data_rows[0].content.startswith("14:00")

    @patch("widgets.weather.requests.get")
    def test_late_evening_few_hours_left(
        self,
        mock_get: MagicMock,
        widget: WeatherWidget,
    ) -> None:
        """At 22:00 with hours=12, only 2 hours remain (22, 23)."""
        context = Context(
            date=datetime.date(2026, 6, 21),
            time=datetime.time(22, 0),
            receipt_name="test",
        )
        forecast_resp = MagicMock()
        forecast_resp.status_code = 200
        forecast_resp.json.return_value = _make_forecast_response()
        mock_get.return_value = forecast_resp

        params = {"latitude": 40.4168, "longitude": -3.7038, "hours": 12}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        data_rows = text_actions[3:]  # skip title, header, separator

        # Only hours 22 and 23 remain
        assert len(data_rows) == 2
        assert data_rows[0].content.startswith("22:00")
        assert data_rows[1].content.startswith("23:00")


class TestWeatherWidgetType:
    """Widget registration metadata."""

    def test_widget_type_is_weather(self) -> None:
        assert WeatherWidget.widget_type == "weather"

    def test_required_secrets_empty(self) -> None:
        assert WeatherWidget.required_secrets == []
