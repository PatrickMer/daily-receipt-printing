"""Engine entry point — orchestrates config, widgets, layout, and printing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

# Ensure all widget modules are imported so the registry is populated.
import widgets  # noqa: F401
from core.actions import ESCPOSAction, TextAction
from core.config import load_receipt_config, load_system_config, validate_secrets
from core.context import Context, build_context
from core.layout import apply_layout
from core.printer import print_actions
from widgets.widget import Widget

logger = logging.getLogger(__name__)


def generate_actions(
    receipt_path: str, config_path: str = "config.yaml"
) -> list[ESCPOSAction]:
    """Run the full pipeline and return actions without printing.

    Executes config loading, widget rendering, and layout application but
    stops before sending to the printer. Useful for preview mode.

    Args:
        receipt_path: Path to the receipt JSON configuration file.
        config_path: Path to the system YAML configuration file.
            Defaults to ``"config.yaml"``.

    Returns:
        Final list of ESC/POS actions ready for rendering or printing.

    Raises:
        FileNotFoundError: If the receipt or system config file is missing.
        OSError: If required secrets are not set in the environment.
    """
    load_system_config(Path(config_path))  # validate config exists
    receipt_config = load_receipt_config(Path(receipt_path))
    validate_secrets(receipt_config)

    context = build_context(receipt_config["name"])

    widget_groups = _run_widgets_grouped(receipt_config, context)
    return apply_layout(widget_groups, receipt_config, context)


def print_receipt(receipt_path: str, config_path: str = "config.yaml") -> None:
    """Load configs, run widgets, apply layout, and print.

    Orchestrates the full receipt printing pipeline:
      1. Load system config (YAML).
      2. Load receipt config (JSON).
      3. Validate that required secrets are present.
      4. Build execution context.
      5. Run each widget independently, collecting per-widget action groups.
      6. Apply layout (header, separators, cut).
      7. Send final actions to the printer.

    Printer connection errors (OSError) are caught, logged, and the function
    returns without crashing.

    Args:
        receipt_path: Path to the receipt JSON configuration file.
        config_path: Path to the system YAML configuration file.
            Defaults to ``"config.yaml"``.

    Raises:
        FileNotFoundError: If the receipt or system config file is missing.
        OSError: If required secrets are not set in the environment.
    """
    system_config = load_system_config(Path(config_path))
    receipt_config = load_receipt_config(Path(receipt_path))
    validate_secrets(receipt_config)

    context = build_context(receipt_config["name"])

    widget_groups = _run_widgets_grouped(receipt_config, context)
    actions = apply_layout(widget_groups, receipt_config, context)

    try:
        print_actions(system_config, actions)
    except OSError:
        logger.exception("Printer connection failed")


def _run_widgets_grouped(
    receipt_config: dict[str, Any], context: Context
) -> list[list[ESCPOSAction]]:
    """Execute all widgets and return per-widget action groups.

    Each widget is executed independently.  If a widget fails, the error is
    logged and a placeholder TextAction group is inserted so downstream layout
    still receives the correct number of groups.

    Args:
        receipt_config: Parsed receipt JSON (must contain a ``"widgets"`` list).
        context: Shared execution context injected into every widget.

    Returns:
        List of action lists, one per widget.
    """
    groups: list[list[ESCPOSAction]] = []

    for widget_spec in receipt_config.get("widgets", []):
        try:
            widget_type: str = widget_spec["type"]
            params: dict[str, Any] = widget_spec.get("params", {})
            widget_cls = Widget.get(widget_type)
            widget = widget_cls()
            result = widget.render(params, context)
            groups.append(result)
        except Exception:
            wtype = widget_spec.get("type", "<unknown>")
            logger.exception("Widget '%s' failed", wtype)
            groups.append([TextAction(content=f"[widget '{wtype}' failed]\n")])

    return groups
