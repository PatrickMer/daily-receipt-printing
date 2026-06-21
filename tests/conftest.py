"""Root conftest — ensure src/ is importable for all tests."""

import sys
from pathlib import Path

import pytest

# Add the src directory to sys.path so imports like `from core.actions import ...` work.
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the --update-snapshots CLI flag for E2E snapshot tests."""
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Regenerate E2E snapshot files.",
    )
