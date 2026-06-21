"""Layout engine — wraps widget outputs with header, separators, and cut."""

from __future__ import annotations

import logging
from typing import Any

from core.actions import (
    CutAction,
    ESCPOSAction,
    FeedAction,
    SetAction,
    TextAction,
)
from core.context import Context

logger = logging.getLogger(__name__)

_DEFAULT_COLUMNS = 48


def apply_layout(
    widget_action_groups: list[list[ESCPOSAction]],
    receipt_config: dict[str, Any],
    context: Context,
) -> list[ESCPOSAction]:
    """Apply layout (header, separators, cut) around widget action groups.

    Args:
        widget_action_groups: List of action lists, one per widget.
        receipt_config: Full receipt config dict (reads the ``layout`` key).
        context: Execution context with date and receipt name.

    Returns:
        Flat list of ESCPOSAction ready for the printer.
    """
    layout = receipt_config.get("layout", {})
    header = layout.get("header", True)
    separator = layout.get("separator", True)
    cut_at_end = layout.get("cut_at_end", True)
    columns: int = layout.get("columns", _DEFAULT_COLUMNS)

    actions: list[ESCPOSAction] = []

    if header:
        actions.extend(_build_header(context))
        if separator:
            actions.append(_build_separator(columns))

    # Filter out empty groups before processing
    non_empty_groups = [g for g in widget_action_groups if g]

    for idx, group in enumerate(non_empty_groups):
        actions.extend(group)
        if separator and idx < len(non_empty_groups) - 1:
            actions.append(_build_separator(columns))

    if cut_at_end:
        actions.append(FeedAction(lines=3))
        actions.append(CutAction())

    return actions


def _build_header(context: Context) -> list[ESCPOSAction]:
    """Generate header actions: bold centered name + formatted date."""
    date_str = context.date.strftime("%A, %B %d, %Y")
    return [
        SetAction(align="center", bold=True),
        TextAction(content=f"{context.receipt_name}\n"),
        TextAction(content=f"{date_str}\n"),
        SetAction(),
    ]


def _build_separator(columns: int) -> TextAction:
    """Generate a separator line of dashes at the given column width."""
    return TextAction(content="-" * columns + "\n")
