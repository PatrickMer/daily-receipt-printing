"""Widget runner — iterates a receipt config and collects ESC/POS actions."""

from __future__ import annotations

import logging
from typing import Any

from core.actions import ESCPOSAction, TextAction
from core.context import Context
from widgets.widget import Widget

logger = logging.getLogger(__name__)


def run_widgets(receipt_config: dict[str, Any], context: Context) -> list[ESCPOSAction]:
    """Execute all widgets in *receipt_config* and return aggregated actions.

    Each widget is executed independently.  If a widget fails (unknown type,
    instantiation error, or render exception), the error is logged, a
    placeholder :class:`TextAction` is appended, and execution continues with
    the remaining widgets.

    Args:
        receipt_config: Parsed receipt JSON (must contain a ``"widgets"`` list).
        context: Shared execution context injected into every widget.

    Returns:
        Flat list of all ESC/POS actions produced by the widgets.
    """
    actions: list[ESCPOSAction] = []

    for widget_spec in receipt_config.get("widgets", []):
        try:
            widget_type: str = widget_spec["type"]
            params: dict[str, Any] = widget_spec.get("params", {})
            widget_cls = Widget.get(widget_type)
            widget = widget_cls()
            result = widget.render(params, context)
            actions.extend(result)
        except Exception:
            wtype = widget_spec.get("type", "<unknown>")
            logger.exception("Widget '%s' failed", wtype)
            actions.append(TextAction(content=f"[widget '{wtype}' failed]"))

    return actions
