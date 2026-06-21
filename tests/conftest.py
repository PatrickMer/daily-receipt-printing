"""Root conftest — ensure src/ is importable for all tests."""

import sys
from pathlib import Path

# Add the src directory to sys.path so imports like `from core.actions import ...` work.
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
