"""Tests for widgets.calendar — Google Calendar iCal widget."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.actions import SetAction, TextAction
from core.context import Context
from widgets.calendar import CalendarWidget


@pytest.fixture()
def widget() -> CalendarWidget:
    """Fresh CalendarWidget instance."""
    return CalendarWidget()


@pytest.fixture()
def context() -> Context:
    """Context at 08:00 on 2026-06-21."""
    return Context(
        date=datetime.date(2026, 6, 21),
        time=datetime.time(8, 0),
        receipt_name="test",
    )


def _make_mock_event(
    summary: str,
    dtstart: datetime.date | datetime.datetime,
) -> MagicMock:
    """Create a mock icalendar.Event with SUMMARY and DTSTART."""
    event = MagicMock()

    dt_prop = MagicMock()
    dt_prop.dt = dtstart

    def get_side_effect(key: str, default: Any = None) -> Any:
        if key == "SUMMARY":
            return summary
        if key == "DTSTART":
            return dt_prop
        return default

    event.get = MagicMock(side_effect=get_side_effect)
    return event


_ICAL_URL = "https://calendar.google.com/calendar/ical/test/basic.ics"

_MINIMAL_ICAL = """\
BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260621T090000
SUMMARY:Morning standup
END:VEVENT
BEGIN:VEVENT
DTSTART:20260621T140000
SUMMARY:Lunch meeting
END:VEVENT
END:VCALENDAR
"""


class TestCalendarHappyPath:
    """Happy path — events sorted by time, formatted correctly."""

    @patch("widgets.calendar.recurring_ical_events")
    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_events_sorted_by_time(
        self,
        mock_get: MagicMock,
        mock_rie: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """Events are sorted by start time and formatted as HH:MM  Summary."""
        mock_resp = MagicMock()
        mock_resp.text = _MINIMAL_ICAL
        mock_get.return_value = mock_resp

        events = [
            _make_mock_event("Lunch meeting", datetime.datetime(2026, 6, 21, 14, 0)),
            _make_mock_event("Morning standup", datetime.datetime(2026, 6, 21, 9, 0)),
        ]
        mock_rie.of.return_value.at.return_value = events

        actions = widget.render({}, context)

        # Title block: SetAction(bold), TextAction("Calendar\n"), SetAction(bold=False)
        assert isinstance(actions[0], SetAction)
        assert actions[0].bold is True
        assert isinstance(actions[1], TextAction)
        assert actions[1].content == "Calendar\n"
        assert isinstance(actions[2], SetAction)
        assert actions[2].bold is False

        # Event lines — sorted: 09:00 before 14:00
        assert isinstance(actions[3], TextAction)
        assert actions[3].content == "09:00  Morning standup\n"
        assert isinstance(actions[4], TextAction)
        assert actions[4].content == "14:00  Lunch meeting\n"

    @patch("widgets.calendar.recurring_ical_events")
    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_uses_real_ical_data(
        self,
        mock_get: MagicMock,
        mock_rie: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """Integration-style test with real iCal parsing (via mocked HTTP)."""
        import icalendar
        import recurring_ical_events as rie

        mock_resp = MagicMock()
        mock_resp.text = _MINIMAL_ICAL
        mock_get.return_value = mock_resp

        # Use real parsing — don't mock recurring_ical_events for this test
        cal = icalendar.Calendar.from_ical(_MINIMAL_ICAL)
        real_events = list(rie.of(cal).at(datetime.date(2026, 6, 21)))
        mock_rie.of.return_value.at.return_value = real_events

        actions = widget.render({}, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        # Title + 2 events = 3
        assert len(text_actions) == 3
        assert "Morning standup" in text_actions[1].content
        assert "Lunch meeting" in text_actions[2].content


class TestCalendarAllDayEvents:
    """All-day events shown as 'All day' at the top."""

    @patch("widgets.calendar.recurring_ical_events")
    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_all_day_event_formatting(
        self,
        mock_get: MagicMock,
        mock_rie: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """All-day events display as 'All day  Summary'."""
        mock_resp = MagicMock()
        mock_resp.text = "BEGIN:VCALENDAR\nEND:VCALENDAR"
        mock_get.return_value = mock_resp

        events = [
            _make_mock_event("Team holiday", datetime.date(2026, 6, 21)),
        ]
        mock_rie.of.return_value.at.return_value = events

        actions = widget.render({}, context)

        assert isinstance(actions[3], TextAction)
        assert actions[3].content == "All day  Team holiday\n"


class TestCalendarMixedEvents:
    """Mixed all-day + timed events — all-day first."""

    @patch("widgets.calendar.recurring_ical_events")
    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_all_day_before_timed(
        self,
        mock_get: MagicMock,
        mock_rie: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """All-day events sort before timed events regardless of insertion order."""
        mock_resp = MagicMock()
        mock_resp.text = "BEGIN:VCALENDAR\nEND:VCALENDAR"
        mock_get.return_value = mock_resp

        events = [
            _make_mock_event("Morning coffee", datetime.datetime(2026, 6, 21, 8, 30)),
            _make_mock_event("Company holiday", datetime.date(2026, 6, 21)),
            _make_mock_event("Afternoon sync", datetime.datetime(2026, 6, 21, 15, 0)),
        ]
        mock_rie.of.return_value.at.return_value = events

        actions = widget.render({}, context)

        event_actions = [a for a in actions[3:] if isinstance(a, TextAction)]
        assert event_actions[0].content == "All day  Company holiday\n"
        assert event_actions[1].content == "08:30  Morning coffee\n"
        assert event_actions[2].content == "15:00  Afternoon sync\n"


class TestCalendarRecurringEvents:
    """Recurring events are expanded via recurring_ical_events."""

    @patch("widgets.calendar.recurring_ical_events")
    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_recurring_events_expanded(
        self,
        mock_get: MagicMock,
        mock_rie: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """recurring_ical_events.of(cal).at(date) is called with context.date."""
        mock_resp = MagicMock()
        mock_resp.text = "BEGIN:VCALENDAR\nEND:VCALENDAR"
        mock_get.return_value = mock_resp

        events = [
            _make_mock_event("Daily standup", datetime.datetime(2026, 6, 21, 10, 0)),
        ]
        mock_rie.of.return_value.at.return_value = events

        actions = widget.render({}, context)

        # Verify recurring_ical_events was called with the right date
        mock_rie.of.return_value.at.assert_called_once_with(context.date)

        # The recurring event appears in output
        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert any("Daily standup" in a.content for a in text_actions)


class TestCalendarEmptyCalendar:
    """Empty calendar shows 'No events today'."""

    @patch("widgets.calendar.recurring_ical_events")
    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_no_events_message(
        self,
        mock_get: MagicMock,
        mock_rie: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """No events today displays a helpful message."""
        mock_resp = MagicMock()
        mock_resp.text = "BEGIN:VCALENDAR\nEND:VCALENDAR"
        mock_get.return_value = mock_resp

        mock_rie.of.return_value.at.return_value = []

        actions = widget.render({}, context)

        text_actions = [a for a in actions if isinstance(a, TextAction)]
        assert text_actions[0].content == "Calendar\n"
        assert text_actions[1].content == "No events today\n"


class TestCalendarFetchFailure:
    """Fetch failure returns placeholder."""

    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_timeout_returns_placeholder(
        self,
        mock_get: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """requests.Timeout is caught and returns unavailable placeholder."""
        mock_get.side_effect = requests.Timeout("Connection timed out")

        actions = widget.render({}, context)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[calendar unavailable]" in actions[0].content

    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_connection_error_returns_placeholder(
        self,
        mock_get: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """requests.ConnectionError returns unavailable placeholder."""
        mock_get.side_effect = requests.ConnectionError("DNS failed")

        actions = widget.render({}, context)

        assert len(actions) == 1
        assert "[calendar unavailable]" in actions[0].content


class TestCalendarParseError:
    """Parse error returns placeholder."""

    @patch("widgets.calendar.requests.get")
    @patch.dict("os.environ", {"GOOGLE_CALENDAR_ICAL_URL": _ICAL_URL})
    def test_invalid_ical_returns_placeholder(
        self,
        mock_get: MagicMock,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """Invalid iCal data returns unavailable placeholder."""
        mock_resp = MagicMock()
        mock_resp.text = "THIS IS NOT VALID ICAL DATA"
        mock_get.return_value = mock_resp

        actions = widget.render({}, context)

        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert "[calendar unavailable]" in actions[0].content

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_env_var_returns_placeholder(
        self,
        widget: CalendarWidget,
        context: Context,
    ) -> None:
        """Missing GOOGLE_CALENDAR_ICAL_URL env var returns placeholder."""
        actions = widget.render({}, context)

        assert len(actions) == 1
        assert "[calendar unavailable]" in actions[0].content


class TestCalendarMetadata:
    """Widget type and required_secrets metadata."""

    def test_widget_type_is_calendar(self) -> None:
        assert CalendarWidget.widget_type == "calendar"

    def test_required_secrets(self) -> None:
        assert CalendarWidget.required_secrets == ["GOOGLE_CALENDAR_ICAL_URL"]


# Import requests at module level for use in test classes
import requests  # noqa: E402
