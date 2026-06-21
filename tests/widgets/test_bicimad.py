"""Tests for widgets.bicimad — BiciMad bike availability widget."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests as req

from core.actions import SetAction, TextAction
from core.context import Context
from widgets.bicimad import BiciMadWidget, _extract_name


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
                "station_id": "puerta-del-sol",
                "name": [{"language": "es", "text": "Puerta del Sol"}],
                "lat": 40.4168,
                "lon": -3.7038,
            },
            {
                "station_id": "atocha",
                "name": [{"language": "es", "text": "Atocha"}],
                "lat": 40.4065,
                "lon": -3.6930,
            },
            {
                "station_id": "gran-via",
                "name": [{"language": "es", "text": "Gran Via"}],
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
                "station_id": "puerta-del-sol",
                "is_renting": True,
                "num_vehicles_available": 12,
                "num_docks_available": 8,
            },
            {
                "station_id": "atocha",
                "is_renting": True,
                "num_vehicles_available": 5,
                "num_docks_available": 15,
            },
            {
                "station_id": "gran-via",
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
            {"name": "Puerta del Sol", "free_bikes": 10, "empty_slots": 10},
            {"name": "Atocha", "free_bikes": 7, "empty_slots": 13},
            {"name": "Gran Via", "free_bikes": 2, "empty_slots": 18},
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
    """Happy path with GBFS — stations matched, formatted correctly."""

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

        params = {"stations": ["sol"]}
        actions = widget.render(params, context)

        assert isinstance(actions[0], SetAction)
        assert actions[0].bold is True

        assert isinstance(actions[1], TextAction)
        assert "BiciMad" in actions[1].content

        assert isinstance(actions[2], SetAction)
        assert actions[2].bold is False

        assert isinstance(actions[3], TextAction)
        assert "Puerta del Sol" in actions[3].content
        assert "12 bikes" in actions[3].content


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

        params = {"stations": ["sol"]}
        actions = widget.render(params, context)

        # Should still produce valid output from CityBikes data.
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Puerta del Sol" in t.content for t in text_actions)
        assert any("10 bikes" in t.content for t in text_actions)

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

        params = {"stations": ["atocha"]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Atocha" in t.content for t in text_actions)
        assert any("7 bikes" in t.content for t in text_actions)


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

        params = {"stations": ["sol"]}
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

        params = {"stations": ["sol"]}
        actions = widget.render(params, context)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[bicimad unavailable]" in actions[0].content


class TestSubstringMatching:
    """Station substring matching (case-insensitive)."""

    @patch("widgets.bicimad.requests.get")
    def test_case_insensitive_match(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Matching is case-insensitive."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        # "SOL" should match "Puerta del Sol"
        params = {"stations": ["SOL"]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Puerta del Sol" in t.content for t in text_actions)

    @patch("widgets.bicimad.requests.get")
    def test_partial_substring_match(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Partial substrings match station names."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": ["gran"]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Gran Via" in t.content for t in text_actions)


class TestNoMatchForStation:
    """No match for a configured station — logged, skipped in output."""

    @patch("widgets.bicimad.requests.get")
    def test_no_match_skipped_silently(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A substring that matches nothing is logged and skipped."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": ["nonexistent", "sol"]}
        actions = widget.render(params, context)

        # "nonexistent" produces a warning log.
        assert "No stations matched substring 'nonexistent'" in caplog.text

        # "sol" still produces output.
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Puerta del Sol" in t.content for t in text_actions)

    @patch("widgets.bicimad.requests.get")
    def test_all_substrings_unmatched_returns_unavailable(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """If no substrings match anything, returns unavailable placeholder."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": ["zzzzz", "xxxxx"]}
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
                    "station_id": "puerta-del-sol",
                    "is_renting": False,
                    "num_vehicles_available": 12,
                    "num_docks_available": 8,
                },
                {
                    "station_id": "atocha",
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

        params = {"stations": ["sol", "atocha"]}
        actions = widget.render(params, context)

        # Warning about Puerta del Sol not renting.
        assert "not renting" in caplog.text
        assert "Puerta del Sol" in caplog.text

        # Atocha is still shown.
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Atocha" in t.content for t in text_actions)
        # Puerta del Sol should NOT be in output.
        assert not any("Puerta del Sol" in t.content for t in text_actions)


class TestMultipleStationsMatched:
    """Multiple stations matched."""

    @patch("widgets.bicimad.requests.get")
    def test_multiple_stations_in_output(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """Multiple station substrings produce multiple output lines."""
        mock_get.side_effect = [
            _mock_response(_gbfs_info_response()),
            _mock_response(_gbfs_status_response()),
        ]

        params = {"stations": ["sol", "atocha", "gran"]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        station_lines = [t for t in text_actions if "bikes" in t.content]
        assert len(station_lines) == 3
        assert "Puerta del Sol" in station_lines[0].content
        assert "Atocha" in station_lines[1].content
        assert "Gran Via" in station_lines[2].content

    @patch("widgets.bicimad.requests.get")
    def test_single_substring_matches_multiple_stations(
        self,
        mock_get: MagicMock,
        widget: BiciMadWidget,
        context: Context,
    ) -> None:
        """A single substring can match multiple stations."""
        info = _gbfs_info_response(
            stations=[
                {
                    "station_id": "calle-sol-1",
                    "name": [{"language": "es", "text": "Calle Sol Norte"}],
                    "lat": 40.42,
                    "lon": -3.70,
                },
                {
                    "station_id": "calle-sol-2",
                    "name": [{"language": "es", "text": "Calle Sol Sur"}],
                    "lat": 40.41,
                    "lon": -3.71,
                },
            ]
        )
        status = _gbfs_status_response(
            stations=[
                {
                    "station_id": "calle-sol-1",
                    "is_renting": True,
                    "num_vehicles_available": 4,
                    "num_docks_available": 16,
                },
                {
                    "station_id": "calle-sol-2",
                    "is_renting": True,
                    "num_vehicles_available": 7,
                    "num_docks_available": 13,
                },
            ]
        )
        mock_get.side_effect = [
            _mock_response(info),
            _mock_response(status),
        ]

        params = {"stations": ["sol"]}
        actions = widget.render(params, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        station_lines = [t for t in text_actions if "bikes" in t.content]
        assert len(station_lines) == 2
        assert "Calle Sol Norte" in station_lines[0].content
        assert "Calle Sol Sur" in station_lines[1].content


class TestNameExtraction:
    """Name extraction from localized array (es preference, fallback to first)."""

    def test_extracts_es_language(self) -> None:
        """Prefers the 'es' language entry."""
        name_field = [
            {"language": "en", "text": "Gate of the Sun"},
            {"language": "es", "text": "Puerta del Sol"},
        ]
        assert _extract_name(name_field) == "Puerta del Sol"

    def test_fallback_to_first_entry(self) -> None:
        """Falls back to first entry when no 'es' language present."""
        name_field = [
            {"language": "en", "text": "Gate of the Sun"},
            {"language": "fr", "text": "Porte du Soleil"},
        ]
        assert _extract_name(name_field) == "Gate of the Sun"

    def test_es_is_first_entry(self) -> None:
        """Works when 'es' is the first and only entry."""
        name_field = [{"language": "es", "text": "Atocha"}]
        assert _extract_name(name_field) == "Atocha"


class TestWidgetRegistration:
    """Widget registration metadata."""

    def test_widget_type_is_bicimad(self) -> None:
        assert BiciMadWidget.widget_type == "bicimad"

    def test_required_secrets_empty(self) -> None:
        assert BiciMadWidget.required_secrets == []
