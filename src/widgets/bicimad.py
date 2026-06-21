"""BiciMad widget — fetches bike availability from GBFS/CityBikes APIs."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

import requests

from core.actions import ESCPOSAction, SetAction, TextAction
from core.context import Context
from widgets.widget import Widget

logger = logging.getLogger(__name__)

_GBFS_STATION_INFO_URL = (
    "https://madrid.publicbikesystem.net/customer/gbfs/v3.0/station_information"
)
_GBFS_STATION_STATUS_URL = (
    "https://madrid.publicbikesystem.net/customer/gbfs/v3.0/station_status"
)
_CITYBIKES_URL = "https://api.citybik.es/v2/networks/bicimad"
_REQUEST_TIMEOUT = 10

_UNAVAILABLE: list[ESCPOSAction] = [TextAction(content="[bicimad unavailable]\n")]


def _extract_name(name_field: list[dict[str, str]]) -> str:
    """Extract station name from GBFS v3.0 localized name array.

    Prefers the ``"es"`` language entry; falls back to the first entry.
    """
    for entry in name_field:
        if entry.get("language") == "es":
            return entry["text"]
    # Fallback to first entry if no "es" found.
    return name_field[0]["text"]


def _fetch_gbfs() -> list[dict[str, Any]]:
    """Fetch station data from GBFS v3.0 APIs and join info + status.

    Returns:
        List of dicts with keys: name, bikes, is_renting.

    Raises:
        requests.RequestException: On network/timeout errors.
        KeyError: On unexpected response structure.
    """
    info_resp = requests.get(_GBFS_STATION_INFO_URL, timeout=_REQUEST_TIMEOUT)
    info_resp.raise_for_status()
    info_data = info_resp.json()

    status_resp = requests.get(_GBFS_STATION_STATUS_URL, timeout=_REQUEST_TIMEOUT)
    status_resp.raise_for_status()
    status_data = status_resp.json()

    # Build lookup by station_id from station_information.
    info_by_id: dict[str, str] = {}
    for station in info_data["data"]["stations"]:
        station_id: str = station["station_id"]
        info_by_id[station_id] = _extract_name(station["name"])

    # Join with station_status.
    joined: list[dict[str, Any]] = []
    for station in status_data["data"]["stations"]:
        station_id = station["station_id"]
        name = info_by_id.get(station_id)
        if name is None:
            continue
        joined.append(
            {
                "name": name,
                "bikes": station["num_vehicles_available"],
                "is_renting": station.get("is_renting", True),
            }
        )

    return joined


def _fetch_citybikes() -> list[dict[str, Any]]:
    """Fetch station data from CityBikes API (fallback).

    Returns:
        List of dicts with keys: name, bikes, is_renting (always True).

    Raises:
        requests.RequestException: On network/timeout errors.
        KeyError: On unexpected response structure.
    """
    resp = requests.get(_CITYBIKES_URL, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    stations: list[dict[str, Any]] = []
    for station in data["network"]["stations"]:
        stations.append(
            {
                "name": station["name"],
                "bikes": station["free_bikes"],
                "is_renting": True,
            }
        )

    return stations


def _extract_public_id(name: str) -> str | None:
    """Extract the public station ID (leading number) from a station name.

    Station names follow the pattern "295 - Hernani - Edgar Neville".
    Returns the leading number as a string, or None if not found.
    """
    parts = name.split(" - ", maxsplit=1)
    first = parts[0].strip()
    if first.isdigit():
        return first
    return None


def _match_stations(
    all_stations: list[dict[str, Any]], station_ids: list[str | int]
) -> list[dict[str, Any]]:
    """Match stations by public ID (the number prefix in station names).

    For each configured ID, finds the matching station.
    Skips stations where is_renting is False (with a warning).
    Logs a warning and skips if an ID matches nothing.

    Returns:
        List of matched stations in the order requested.
    """
    id_lookup: dict[str, dict[str, Any]] = {}
    for station in all_stations:
        public_id = _extract_public_id(station["name"])
        if public_id is not None:
            id_lookup[public_id] = station

    matched: list[dict[str, Any]] = []
    for station_id in station_ids:
        key = str(station_id)
        if key not in id_lookup:
            logger.warning("No station matched ID '%s', skipping", key)
            continue
        station = id_lookup[key]
        if not station["is_renting"]:
            logger.warning("Station '%s' is not renting, skipping", station["name"])
            continue
        matched.append(station)

    return matched


class BiciMadWidget(Widget):
    """Displays BiciMad bike availability for configured stations."""

    widget_type: ClassVar[str] = "bicimad"
    required_secrets: ClassVar[list[str]] = []

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        """Render bike availability for matched stations.

        Params:
            stations: List of public station IDs (the number shown in the app).
            columns: Receipt width for name truncation (default 48).
        """
        station_ids: list[str | int] = params.get("stations", [])
        columns: int = params.get("columns", 48)

        all_stations = self._fetch_stations()
        if all_stations is None:
            return list(_UNAVAILABLE)

        matched = _match_stations(all_stations, station_ids)
        if not matched:
            return list(_UNAVAILABLE)

        actions: list[ESCPOSAction] = [
            SetAction(bold=True),
            TextAction(content="BiciMad\n"),
            SetAction(bold=False),
        ]
        for station in matched:
            bikes = station["bikes"]
            prefix = f"{bikes:>2} bikes - "
            name = station["name"]
            # Strip the public ID prefix ("295 - ") from the display name
            parts = name.split(" - ", maxsplit=1)
            if len(parts) > 1 and parts[0].strip().isdigit():
                name = parts[1]
            max_name_len = columns - len(prefix)
            if len(name) > max_name_len:
                name = name[: max_name_len - 1] + "~"
            actions.append(TextAction(content=f"{prefix}{name}\n"))

        return actions

    def _fetch_stations(self) -> list[dict[str, Any]] | None:
        """Try GBFS primary, then CityBikes fallback.

        Returns:
            Station list on success, None if all sources fail.
        """
        try:
            return _fetch_gbfs()
        except (requests.RequestException, KeyError, TypeError) as exc:
            logger.warning("GBFS fetch failed, trying CityBikes fallback: %s", exc)

        try:
            return _fetch_citybikes()
        except (requests.RequestException, KeyError, TypeError) as exc:
            logger.warning("CityBikes fallback also failed: %s", exc)

        return None
