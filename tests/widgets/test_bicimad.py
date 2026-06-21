"""Tests for widgets.bicimad — BiciMad bike availability widget."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests as req

from core.actions import SetAction, TextAction
from core.context import Context
from widgets.bicimad import BiciMadWidget, _extract_name, _extract_public_id


@pytest.fixture()
def widget() -> BiciMadWidget:
    """Fresh BiciMadWidget instance."""
    return BiciMadWidget()


@pytest.fixture()
def context() -> Context:
    """Context for testing."""
    return Context(
        date=datetime.date(2026, 6, 21),
        time=datetime.time(9, 0),
        receipt_name="test",
    )


def _gbfs_info_response(
    stations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a GBFS station_information response."""
    if stations is None:
        stations = [
            {
                "station_id": "1001",
                "name": [{"language": "es", "text": "10 - Puerta del Sol"}],
                "lat": 40.4168,
                "lon": -3.7038,
            },
            {
                "station_id": "1002",
                "name": [{"language": "es", "text": "20 - Atocha"}],
                "lat": 40.4065,
                "lon": -3.6930,
            },
            {
                "station_id": "1003",
                "name": [{"language": "es", "text": "30 - Gran Via"}],
                "lat": 40.4200,
                "lon": -3.7050,
            },
        ]
    return {"data": {"stations": stations}}


def _gbfs_status_response(
    stations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a GBFS station_status response."""
    if stations is None:
        stations = [
            {
                "station_id": "1001",
                "is_renting": True,
                "num_vehicles_available": 12,
                "num_docks_available": 8,
            },
            {
                "station_id": "1002",
                "is_renting": True,
                "num_vehicles_available": 5,
                "num_docks_available": 15,
            },
            {
                "station_id": "1003",
                "is_renting": True,
                "num_vehicles_available": 3,
                "num_docks_available": 17,
            },
        ]
    return {"data": {"stations": stations}}


def _citybikes_response(
    stations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a CityBikes API response."""
    if stations is None:
        stations = [
            {"name": "10 - Puerta del Sol", "free_bikes": 10, "empty_slots": 10},
            {"name": "20 - Atocha", "free_bikes": 7, "empty_slots": 13},
            {"name": "30 - Gran Via", "free_bikes": 2, "empty_slots": 18},
        ]
    return {"network": {"stations": stations}}


def _mock_response(json_data: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Create a mock response object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestGBFSHappyPath:
    """Happy path with GBFS — stations matched by public ID."""

    @patch("widgets.bicimad.requests.get")
    def test_returns_formatted_station_data(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """GBFS data is fetched, joined, and formatted correctly."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": [10]}
        actions = widget.render(params, context)

        assert isinstance(actions[0], SetAction)
        assert actions[0].bold is True
        assert isinstance(actions[1], TextAction)
        assert "BiciMad" in actions[1].content
        assert isinstance(actions[2], SetAction)
        assert actions[2].bold is False
        assert isinstance(actions[3], TextAction)
        assert "Puerta del Sol" in actions[3].content
        assert "12" in actions[3].content


class TestGBFSFallbackToCityBikes:
    """GBFS times out, CityBikes works."""

    @patch("widgets.bicimad.requests.get")
    def test_citybikes_used_on_gbfs_timeout(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """When GBFS times out, CityBikes fallback is used successfully."""
        mock_get.side_effect = [
            req.Timeout("Connection timed out"),
            _mock_response(_citybikes_response()),
        ]

        params = {"stations": [10]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Puerta del Sol" in t.content for t in text_actions)

    @patch("widgets.bicimad.requests.get")
    def test_citybikes_used_on_gbfs_connection_error(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """When GBFS has a connection error, CityBikes fallback is used."""
        mock_get.side_effect = [
            req.ConnectionError("DNS resolution failed"),
            _mock_response(_citybikes_response()),
        ]

        params = {"stations": [20]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Atocha" in t.content for t in text_actions)


class TestBothAPIsFail:
    """Both APIs fail — returns unavailable placeholder."""

    @patch("widgets.bicimad.requests.get")
    def test_returns_unavailable_when_all_fail(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Both GBFS and CityBikes failing returns placeholder text."""
        mock_get.side_effect = req.Timeout("Timeout")

        params = {"stations": [10]}
        actions = widget.render(params, context)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[bicimad unavailable]" in actions[0].content

    @patch("widgets.bicimad.requests.get")
    def test_returns_unavailable_on_http_error(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """HTTP 500 from both sources returns placeholder."""
        error_resp = MagicMock()
        error_resp.raise_for_status.side_effect = req.HTTPError("500 Server Error")
        mock_get.return_value = error_resp

        params = {"stations": [10]}
        actions = widget.render(params, context)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[bicimad unavailable]" in actions[0].content


class TestIDMatching:
    """Station matching by public ID."""

    @patch("widgets.bicimad.requests.get")
    def test_matches_by_integer_id(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Integer IDs match station name prefixes."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": [20]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Atocha" in t.content for t in text_actions)

    @patch("widgets.bicimad.requests.get")
    def test_matches_by_string_id(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """String IDs also work."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": ["30"]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Gran Via" in t.content for t in text_actions)


class TestNoMatchForStation:
    """No match for a configured station ID — logged, skipped."""

    @patch("widgets.bicimad.requests.get")
    def test_no_match_skipped_with_warning(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An ID that matches nothing is logged and skipped."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": [999, 10]}
        actions = widget.render(params, context)

        assert "No station matched ID '999'" in caplog.text
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Puerta del Sol" in t.content for t in text_actions)

    @patch("widgets.bicimad.requests.get")
    def test_all_ids_unmatched_returns_unavailable(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """If no IDs match anything, returns unavailable placeholder."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": [888, 999]}
        actions = widget.render(params, context)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[bicimad unavailable]" in actions[0].content


class TestIsRentingFalse:
    """Station with is_renting=false — skipped with warning."""

    @patch("widgets.bicimad.requests.get")
    def test_not_renting_skipped_with_warning(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Stations with is_renting=false are skipped and a warning is logged."""
        status_data = _gbfs_status_response(
            stations=[
                {
                    "station_id": "1001",
                    "is_renting": False,
                    "num_vehicles_available": 12,
                    "num_docks_available": 8,
                },
                {
                    "station_id": "1002",
                    "is_renting": True,
                    "num_vehicles_available": 5,
                    "num_docks_available": 15,
                },
            ]
        )
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(status_data),
        ]

        params = {"stations": [10, 20]}
        actions = widget.render(params, context)

        assert "not renting" in caplog.text
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Atocha" in t.content for t in text_actions)
        assert not any("Puerta del Sol" in t.content for t in text_actions)


class TestMultipleStationsMatched:
    """Multiple stations matched by ID."""

    @patch("widgets.bicimad.requests.get")
    def test_multiple_stations_in_output(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Multiple station IDs produce multiple output lines in order."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": [10, 20, 30]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        station_lines = [t for t in text_actions if "BiciMad" not in t.content]
        assert len(station_lines) == 3
        assert "Puerta del Sol" in station_lines[0].content
        assert "Atocha" in station_lines[1].content
        assert "Gran Via" in station_lines[2].content


class TestTruncation:
    """Long station names are truncated to fit column width."""

    @patch("widgets.bicimad.requests.get")
    def test_long_name_truncated(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Station names exceeding column width are truncated with ~."""
        info = _gbfs_info_response(
            stations=[
                {
                    "station_id": "2000",
                    "name": [
                        {
                            "language": "es",
                            "text": "50 - Raimundo Fernandez Villaverde - Dulcinea",
                        }
                    ],
                    "lat": 40.42,
                    "lon": -3.70,
                },
            ]
        )
        status = _gbfs_status_response(
            stations=[
                {
                    "station_id": "2000",
                    "is_renting": True,
                    "num_vehicles_available": 7,
                    "num_docks_available": 13,
                },
            ]
        )
        mock_get.side_effect = [_mock_response(info), _mock_response(status)]

        params = {"stations": [50], "columns": 30}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        station_line = next(t for t in text_actions if "BiciMad" not in t.content)
        assert len(station_line.content.rstrip("\n")) <= 30
        assert "~" in station_line.content


class TestPublicIDExtraction:
    """_extract_public_id helper."""

    def test_extracts_leading_number(self) -> None:
        assert _extract_public_id("295 - Hernani - Edgar Neville") == "295"

    def test_extracts_single_digit(self) -> None:
        assert _extract_public_id("1 - Metro Sol") == "1"

    def test_no_number_prefix(self) -> None:
        assert _extract_public_id("No Number Here") is None

    def test_non_digit_prefix(self) -> None:
        assert _extract_public_id("ABC - Some Station") is None


class TestNameExtraction:
    """Name extraction from localized array."""

    def test_extracts_es_language(self) -> None:
        name_field = [
            {"language": "en", "text": "Gate of the Sun"},
            {"language": "es", "text": "Puerta del Sol"},
        ]
        assert _extract_name(name_field) == "Puerta del Sol"

    def test_fallback_to_first_entry(self) -> None:
        name_field = [
            {"language": "en", "text": "Gate of the Sun"},
            {"language": "fr", "text": "Porte du Soleil"},
        ]
        assert _extract_name(name_field) == "Gate of the Sun"


class TestWidgetRegistration:
    """Widget registration metadata."""

    def test_widget_type_is_bicimad(self) -> None:
        assert BiciMadWidget.widget_type == "bicimad"

    def test_required_secrets_empty(self) -> None:
        assert BiciMadWidget.required_secrets == []
