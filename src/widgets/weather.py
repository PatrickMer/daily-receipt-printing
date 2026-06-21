"""Weather widget — fetches forecast from Open-Meteo and formats as a table."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import requests

from core.actions import ESCPOSAction, SetAction, TextAction
from core.context import Context
from widgets.widget import Widget

logger = logging.getLogger(__name__)

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_REQUEST_TIMEOUT = 10

# Simplified weather code descriptions.
_WEATHER_CODES: dict[int, str] = {
    0: "Clear",
    1: "Cloudy",
    2: "Cloudy",
    3: "Cloudy",
    45: "Fog",
    48: "Fog",
    51: "Drizzle",
    53: "Drizzle",
    55: "Drizzle",
    61: "Rain",
    63: "Rain",
    65: "Rain",
    71: "Snow",
    73: "Snow",
    75: "Snow",
    80: "Showers",
    81: "Showers",
    82: "Showers",
    95: "Thunder",
    96: "Thunder",
    99: "Thunder",
}

_UNAVAILABLE: list[ESCPOSAction] = [TextAction(content="[weather unavailable]\n")]


def _geocode(city: str) -> tuple[float, float, str]:
    """Resolve a city name to (latitude, longitude, display_name).

    Raises:
        ValueError: If no results found.
        requests.RequestException: On network errors.
    """
    resp = requests.get(
        _GEOCODING_URL,
        params={"name": city, "count": "1"},
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results")
    if not results:
        raise ValueError(f"No geocoding results for '{city}'")
    hit = results[0]
    return float(hit["latitude"]), float(hit["longitude"]), str(hit["name"])


def _fetch_forecast(latitude: float, longitude: float, timezone: str) -> dict[str, Any]:
    """Fetch hourly forecast from Open-Meteo.

    Returns:
        The "hourly" dict from the API response.

    Raises:
        KeyError: If response structure is unexpected.
        requests.RequestException: On network errors.
    """
    resp = requests.get(
        _FORECAST_URL,
        params={
            "latitude": str(latitude),
            "longitude": str(longitude),
            "hourly": "temperature_2m,precipitation_probability,weathercode",
            "timezone": timezone,
            "forecast_days": "1",
        },
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    hourly: dict[str, Any] = data["hourly"]
    return hourly


def _weather_desc(code: int) -> str:
    """Map a WMO weather code to a short description."""
    return _WEATHER_CODES.get(code, "?")


def _format_table(hourly: dict[str, Any], start_hour: int, hours: int) -> list[str]:
    """Format hourly forecast data as fixed-width table rows.

    Args:
        hourly: The "hourly" section from Open-Meteo response.
        start_hour: Hour of the day to start from (0-23).
        hours: Max number of rows to produce.

    Returns:
        List of formatted row strings (including header).
    """
    times: list[str] = hourly["time"]
    temps: list[float] = hourly["temperature_2m"]
    precips: list[int] = hourly["precipitation_probability"]
    codes: list[int] = hourly["weathercode"]

    rows: list[str] = []
    rows.append(f"{'Hour':<6}{'Temp':<7}{'Rain%':<6}{'Sky'}\n")
    rows.append(f"{'-' * 5:<6}{'-' * 5:<7}{'-' * 5:<6}{'-' * 7}\n")

    count = 0
    for i, time_str in enumerate(times):
        # time_str looks like "2026-06-21T08:00"
        hour = int(time_str.split("T")[1].split(":")[0])
        if hour < start_hour:
            continue
        if count >= hours:
            break

        temp_str = f"{temps[i]:.0f}C"
        rain_str = f"{precips[i]}%"
        sky = _weather_desc(codes[i])
        rows.append(f"{hour:02d}:00 {temp_str:<7}{rain_str:<6}{sky}\n")
        count += 1

    return rows


class WeatherWidget(Widget):
    """Displays hourly weather forecast from Open-Meteo."""

    widget_type: ClassVar[str] = "weather"
    required_secrets: ClassVar[list[str]] = []

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        """Render weather forecast as a formatted table.

        Params:
            latitude/longitude: Direct coordinates (preferred).
            location: City name to geocode (used if coords not provided).
            hours: Number of forecast hours to display (default 12).
            timezone: Timezone string (default "Europe/Madrid").
        """
        hours: int = params.get("hours", 12)
        timezone: str = params.get("timezone", "Europe/Madrid")

        try:
            latitude, longitude, label = self._resolve_location(params)
            hourly = _fetch_forecast(latitude, longitude, timezone)
            table_rows = _format_table(hourly, context.time.hour, hours)
        except (
            requests.RequestException,
            requests.Timeout,
            KeyError,
            ValueError,
            TypeError,
        ):
            logger.exception("Weather widget failed")
            return _UNAVAILABLE

        actions: list[ESCPOSAction] = [
            SetAction(bold=True),
            TextAction(content=f"Weather — {label}\n"),
            SetAction(bold=False, font="b"),
        ]
        for row in table_rows:
            actions.append(TextAction(content=row))
        actions.append(SetAction(font="a"))

        return actions

    def _resolve_location(self, params: dict[str, Any]) -> tuple[float, float, str]:
        """Resolve location from params — coords or city name."""
        if "latitude" in params and "longitude" in params:
            lat = float(params["latitude"])
            lon = float(params["longitude"])
            label = f"{lat:.2f}, {lon:.2f}"
            return lat, lon, label

        location = params.get("location")
        if not location:
            raise ValueError(
                "No location provided (need latitude/longitude or location)"
            )

        lat, lon, name = _geocode(str(location))
        return lat, lon, name
