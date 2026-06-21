"""Plain-text receipt preview renderer.

Renders a list of ESC/POS actions as a human-readable text approximation
of what the thermal printer would produce.
"""

from __future__ import annotations

import logging

from core.actions import (
    BarcodeAction,
    CutAction,
    ESCPOSAction,
    FeedAction,
    ImageAction,
    QRAction,
    SetAction,
    TextAction,
)

logger = logging.getLogger(__name__)


def _align_line(line: str, align: str, columns: int) -> str:
    """Align a single line within the given column width."""
    if not line:
        return ""
    if align == "center":
        return line.center(columns)
    if align == "right":
        return line.rjust(columns)
    return line  # left


def _render_aligned_text(text: str, align: str, columns: int) -> str:
    """Apply alignment to each line of a multi-line string."""
    lines = text.split("\n")
    # Process all lines, preserving trailing newline structure
    aligned = [_align_line(line, align, columns) for line in lines]
    return "\n".join(aligned)


def render_preview(actions: list[ESCPOSAction], columns: int = 48) -> str:
    """Render an action list as a plain-text receipt preview.

    Simulates what the thermal printer would produce by converting ESC/POS
    actions into formatted plain text. Tracks alignment and bold state.

    Args:
        actions: List of ESC/POS actions to render.
        columns: Character width of the receipt (default 48 for TM-T20II).

    Returns:
        Plain-text string representing the receipt output.
    """
    align = "left"
    bold = False
    output: list[str] = []

    for action in actions:
        if isinstance(action, SetAction):
            if action.align is not None:
                align = action.align
            if action.bold is not None:
                bold = action.bold

        elif isinstance(action, TextAction):
            content = action.content
            if bold:
                content = content.upper()
            output.append(_render_aligned_text(content, align, columns))

        elif isinstance(action, FeedAction):
            output.append("\n" * action.lines)

        elif isinstance(action, CutAction):
            output.append("=" * columns + "\n")

        elif isinstance(action, QRAction):
            placeholder = f"[QR: {action.content}]"
            output.append(_align_line(placeholder, align, columns) + "\n")

        elif isinstance(action, BarcodeAction):
            placeholder = f"[BARCODE: {action.code}]"
            output.append(_align_line(placeholder, align, columns) + "\n")

        elif isinstance(action, ImageAction):
            placeholder = f"[IMAGE: {action.path}]"
            output.append(_align_line(placeholder, align, columns) + "\n")

    return "".join(output)
