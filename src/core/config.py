"""Configuration loading and secret validation for the receipt printing system."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from dotenv import load_dotenv

from widgets.widget import Widget

load_dotenv()


def load_system_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load and return the system config from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        Parsed configuration as a dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        msg = f"System config file not found: {config_path}"
        raise FileNotFoundError(msg)

    with config_path.open() as f:
        result: dict[str, Any] = yaml.safe_load(f)

    return result


def load_receipt_config(path: str | Path) -> dict[str, Any]:
    """Load and return a receipt JSON configuration.

    Args:
        path: Path to the receipt JSON file.

    Returns:
        Parsed receipt configuration as a dictionary.

    Raises:
        FileNotFoundError: If the receipt file does not exist.
        ValueError: If the file contains invalid JSON.
    """
    receipt_path = Path(path)
    if not receipt_path.exists():
        msg = f"Receipt config file not found: {receipt_path}"
        raise FileNotFoundError(msg)

    text = receipt_path.read_text()
    try:
        result: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in receipt config {receipt_path}: {e}"
        raise ValueError(msg) from e

    return result


def validate_secrets(receipt_config: dict[str, Any]) -> None:
    """Validate that all secrets required by the receipt's widgets are present.

    Inspects each widget listed in the receipt config, looks up its class in
    the Widget registry, collects all ``required_secrets``, and verifies each
    one is set in ``os.environ``.

    Args:
        receipt_config: Parsed receipt configuration dictionary.

    Raises:
        KeyError: If a widget type in the config is not registered.
        EnvironmentError: If one or more required secrets are missing from
            the environment. The error message lists all missing secrets.
    """
    widgets = receipt_config.get("receipt", {}).get("widgets", [])

    missing: list[str] = []
    for widget_entry in widgets:
        widget_type: str = widget_entry["type"]
        widget_cls = Widget.get(widget_type)
        for secret in widget_cls.required_secrets:
            if secret not in os.environ:
                missing.append(secret)

    if missing:
        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique_missing: list[str] = []
        for s in missing:
            if s not in seen:
                seen.add(s)
                unique_missing.append(s)
        msg = (
            f"Missing required secrets: {', '.join(unique_missing)}. "
            f"Ensure these are set in your .env file."
        )
        raise OSError(msg)
