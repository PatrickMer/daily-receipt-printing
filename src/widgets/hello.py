"""Hello world widget — simple test widget for E2E validation."""

from __future__ import annotations

from typing import Any

from core.actions import ESCPOSAction, TextAction
from core.context import Context
from widgets.widget import Widget


class HelloWidget(Widget):
    """Prints a greeting message."""

    widget_type = "hello"

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        name = params.get("name", "World")
        return [
            TextAction(content=f"Hello, {name}!\n"),
            TextAction(content=f"Today is {context.date.strftime('%A')}.\n"),
        ]
