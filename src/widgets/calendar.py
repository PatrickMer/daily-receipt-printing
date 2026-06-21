"""Calendar widget — fetches iCal events and lists today's schedule."""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any, ClassVar

import icalendar
import recurring_ical_events
import requests

from core.actions import ESCPOSAction, SetAction, TextAction
from core.context import Context
from widgets.widget import Widget

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10

_UNAVAILABLE: list[ESCPOSAction] = [TextAction(content="[calendar unavailable]\n")]


def _is_all_day(dtstart: datetime.date | datetime.datetime) -> bool:
    """Return True if the event is an all-day event (date, not datetime)."""
    return isinstance(dtstart, datetime.date) and not isinstance(
        dtstart, datetime.datetime
    )


def _sort_key(event: icalendar.Event) -> tuple[int, datetime.time]:
    """Sort key: all-day events first (priority 0), then by start time (priority 1)."""
    dtstart = event.get("DTSTART").dt  # type: ignore[no-untyped-call]
    if _is_all_day(dtstart):
        return (0, datetime.time.min)
    return (1, dtstart.time())


def _format_event(event: icalendar.Event) -> str:
    """Format a single event as a display line."""
    dtstart = event.get("DTSTART").dt  # type: ignore[no-untyped-call]
    summary = str(event.get("SUMMARY", "Untitled"))  # type: ignore[no-untyped-call]

    if _is_all_day(dtstart):
        return f"All day  {summary}\n"

    time_str = dtstart.strftime("%H:%M")
    return f"{time_str}  {summary}\n"


class CalendarWidget(Widget):
    """Displays today's events from a Google Calendar iCal feed."""

    widget_type: ClassVar[str] = "calendar"
    required_secrets: ClassVar[list[str]] = ["GOOGLE_CALENDAR_ICAL_URL"]

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        """Render today's calendar events.

        Reads the iCal URL from the GOOGLE_CALENDAR_ICAL_URL environment
        variable, fetches the calendar, and lists today's events sorted by
        start time (all-day events first).
        """
        try:
            ical_url = os.environ.get("GOOGLE_CALENDAR_ICAL_URL")
            if not ical_url:
                logger.error("GOOGLE_CALENDAR_ICAL_URL not set")
                return list(_UNAVAILABLE)

            response = requests.get(ical_url, timeout=_REQUEST_TIMEOUT)
            response.raise_for_status()

            cal = icalendar.Calendar.from_ical(response.text)
            events = recurring_ical_events.of(cal).at(context.date)
            events_sorted = sorted(events, key=_sort_key)

        except Exception:
            logger.exception("Calendar widget failed")
            return list(_UNAVAILABLE)

        actions: list[ESCPOSAction] = [
            SetAction(bold=True),
            TextAction(content="Calendar\n"),
            SetAction(bold=False),
        ]

        if not events_sorted:
            actions.append(TextAction(content="No events today\n"))
        else:
            for event in events_sorted:
                actions.append(TextAction(content=_format_event(event)))

        return actions
