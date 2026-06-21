"""Printer driver — bridges ESCPOSAction dataclasses to python-escpos."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from escpos.printer import Dummy, Network

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


def connect_printer(config: dict[str, Any]) -> Network:
    """Create and open a Network printer connection from system config.

    Args:
        config: System configuration dict containing a ``printer`` key
            with host, port, profile, and timeout values.

    Returns:
        An open Network printer instance.
    """
    printer_cfg = config["printer"]
    printer = Network(
        host=printer_cfg["host"],
        port=printer_cfg.get("port", 9100),
        timeout=printer_cfg.get("timeout", 10),
        profile=printer_cfg.get("profile", "default"),
    )
    printer.open()
    return printer


def _dispatch_action(printer: Network | Dummy, action: ESCPOSAction) -> None:
    """Dispatch a single action to the appropriate printer method."""
    if isinstance(action, SetAction):
        kwargs: dict[str, Any] = {}
        if action.align is not None:
            kwargs["align"] = action.align
        if action.bold is not None:
            kwargs["bold"] = action.bold
        if action.underline is not None:
            kwargs["underline"] = action.underline
        if action.width is not None:
            kwargs["width"] = action.width
        if action.height is not None:
            kwargs["height"] = action.height
        if action.font is not None:
            kwargs["font"] = action.font
        if action.invert is not None:
            kwargs["invert"] = action.invert
        printer.set(**kwargs)
    elif isinstance(action, TextAction):
        printer.text(action.content)
    elif isinstance(action, FeedAction):
        printer.print_and_feed(action.lines)
    elif isinstance(action, ImageAction):
        kwargs = {}
        if action.center is not None:
            kwargs["center"] = action.center
        if action.impl is not None:
            kwargs["impl"] = action.impl
        printer.image(action.path, **kwargs)
    elif isinstance(action, QRAction):
        kwargs = {}
        if action.size is not None:
            kwargs["size"] = action.size
        if action.native is not None:
            kwargs["native"] = action.native
        if action.center is not None:
            kwargs["center"] = action.center
        printer.qr(action.content, **kwargs)
    elif isinstance(action, BarcodeAction):
        kwargs = {}
        if action.height is not None:
            kwargs["height"] = action.height
        if action.width is not None:
            kwargs["width"] = action.width
        if action.pos is not None:
            kwargs["pos"] = action.pos
        printer.barcode(action.code, action.bc_type, **kwargs)
    elif isinstance(action, CutAction):
        printer.cut(mode=action.mode)
    else:
        msg = f"Unknown action type: {type(action).__name__}"
        raise ValueError(msg)


def execute_actions(printer: Network | Dummy, actions: Sequence[ESCPOSAction]) -> None:
    """Dispatch a list of ESCPOSActions to the printer.

    Iterates through each action and calls the corresponding printer method.
    Calls ``set_with_default()`` after the full batch to reset formatting.

    Args:
        printer: An open printer instance (Network or Dummy).
        actions: Ordered list of actions to execute.

    Raises:
        ValueError: If an unrecognised action type is encountered.
    """
    for action in actions:
        _dispatch_action(printer, action)
    printer.set_with_default()


def print_actions(config: dict[str, Any], actions: Sequence[ESCPOSAction]) -> None:
    """Connect to printer and execute actions, ensuring close() on exit.

    Args:
        config: System configuration dict (passed to :func:`connect_printer`).
        actions: Actions to execute on the printer.
    """
    printer = connect_printer(config)
    try:
        execute_actions(printer, actions)
    finally:
        printer.close()
