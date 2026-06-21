"""Fun-fact widget — fetches a random fact from the Useless Facts API."""

from __future__ import annotations

import hashlib
import logging
import textwrap
from typing import Any, ClassVar

import requests

from core.actions import ESCPOSAction, SetAction, TextAction
from core.context import Context
from widgets.widget import Widget

logger = logging.getLogger(__name__)

_API_URL = "https://uselessfacts.jsph.pl/api/v2/facts/random"
_REQUEST_TIMEOUT = 10

_FALLBACK_FACTS: list[str] = [
    "Honey never spoils. Archaeologists have found 3,000-year-old honey still edible.",
    "Octopuses have three hearts and blue blood.",
    "Bananas are berries, but strawberries are not.",
    "A group of flamingos is called a 'flamboyance'.",
    "The Eiffel Tower can be 15 cm taller during the summer due to thermal expansion.",
    "Scotland's national animal is the unicorn.",
    "There are more stars in the universe than grains of sand on Earth.",
    "Wombat droppings are cube-shaped.",
    "A day on Venus is longer than a year on Venus.",
    "The inventor of the Pringles can is buried in one.",
]


def _select_fallback(date_iso: str) -> str:
    """Deterministically pick a fallback fact based on the date string."""
    digest = hashlib.sha256(date_iso.encode()).digest()
    index = int.from_bytes(digest[:4], "big") % len(_FALLBACK_FACTS)
    return _FALLBACK_FACTS[index]


def _fetch_fact() -> str:
    """Fetch a random fact from the Useless Facts API.

    Returns:
        The fact text.

    Raises:
        requests.RequestException: On network errors.
        KeyError: If the response is missing the 'text' key.
    """
    resp = requests.get(
        _API_URL,
        params={"language": "en"},
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return str(data["text"])


class FunFactWidget(Widget):
    """Displays a random fun fact fetched from the Useless Facts API."""

    widget_type: ClassVar[str] = "fun-fact"
    required_secrets: ClassVar[list[str]] = []

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        """Render a fun fact as wrapped text.

        Params:
            columns: Line width for text wrapping (default 48).
        """
        columns: int = params.get("columns", 48)

        try:
            fact = _fetch_fact()
        except (requests.RequestException, KeyError, ValueError, TypeError):
            logger.exception("Fun-fact widget: API failed, using fallback")
            fact = _select_fallback(context.date.isoformat())

        wrapped = textwrap.fill(fact, width=columns)

        actions: list[ESCPOSAction] = [
            SetAction(bold=True),
            TextAction(content="Fun Fact\n"),
            SetAction(bold=False),
            TextAction(content=f"{wrapped}\n"),
        ]
        return actions
