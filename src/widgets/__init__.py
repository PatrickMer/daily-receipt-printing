"""Widget package — autodiscovery and public re-exports."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path

from widgets.widget import Widget

__all__ = ["Widget", "discover_widgets"]

logger = logging.getLogger(__name__)


def discover_widgets() -> None:
    """Import all modules in widgets/ to trigger __init_subclass__ registration.

    Modules whose names start with ``_`` or the base ``widget`` module itself
    are skipped.  Import failures are logged and do not halt discovery.
    """
    package_dir = Path(__file__).resolve().parent
    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if module_info.name.startswith("_") or module_info.name == "widget":
            continue
        try:
            importlib.import_module(f"{__package__}.{module_info.name}")
        except Exception:
            logger.exception("Failed to load widget module '%s'", module_info.name)


discover_widgets()
