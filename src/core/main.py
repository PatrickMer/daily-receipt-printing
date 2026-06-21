"""CLI entry point for daily receipt printing."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from core.config import load_system_config
from core.engine import print_receipt
from core.log_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse CLI arguments and print the receipt."""
    parser = argparse.ArgumentParser(description="Print a daily receipt")
    parser.add_argument("receipt", help="Path to the receipt JSON config file")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to system config YAML (default: config.yaml)",
    )
    args = parser.parse_args()

    system_config = load_system_config(Path(args.config))
    setup_logging(system_config.get("logging", {}))

    try:
        print_receipt(args.receipt, config_path=args.config)
    except Exception:
        logger.exception("Receipt printing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
