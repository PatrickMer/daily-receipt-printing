"""E2E snapshot tests — run the full pipeline and compare output against saved snapshots."""

from __future__ import annotations

import datetime
import json
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from escpos.printer import Dummy

from core.actions import ESCPOSAction
from core.config import load_receipt_config
from core.context import Context
from core.engine import _run_widgets_grouped
from core.layout import apply_layout
from core.printer import execute_actions

_SNAPSHOTS_DIR = Path(__file__).resolve().parent / "snapshots"
_RECEIPT_PATH = Path(__file__).resolve().parent.parent / "receipts" / "test.json"

# Fixed date: 2026-01-15 is a Thursday — deterministic for snapshot comparison.
_FIXED_CONTEXT = Context(
    date=datetime.date(2026, 1, 15),
    time=datetime.time(8, 30),
    receipt_name="Patrick's Morning Brief",
)


def _actions_to_dicts(actions: list[ESCPOSAction]) -> list[dict[str, Any]]:
    """Serialize an action list to a list of plain dicts for snapshot comparison.

    Each dict contains the ``action`` field plus all non-None dataclass fields
    (excluding ``action`` itself, which is always included).
    """
    result: list[dict[str, Any]] = []
    for action in actions:
        d: dict[str, Any] = {"action": action.action}
        for f in fields(action):
            if f.name == "action":
                continue
            value = getattr(action, f.name)
            if value is not None:
                d[f.name] = value
        result.append(d)
    return result


def _load_snapshot(name: str) -> list[dict[str, Any]]:
    """Load a JSON snapshot file by name from the snapshots directory."""
    path = _SNAPSHOTS_DIR / name
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def _save_snapshot(name: str, data: list[dict[str, Any]]) -> None:
    """Save a JSON snapshot file to the snapshots directory."""
    path = _SNAPSHOTS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


class TestE2ESnapshot:
    """End-to-end snapshot tests exercising the full receipt pipeline."""

    @pytest.fixture()
    def actions(self) -> list[ESCPOSAction]:
        """Run the full pipeline and return the final action list."""
        receipt_config = load_receipt_config(_RECEIPT_PATH)
        widget_groups = _run_widgets_grouped(receipt_config, _FIXED_CONTEXT)
        return apply_layout(widget_groups, receipt_config, _FIXED_CONTEXT)

    def test_action_list_matches_snapshot(self, actions: list[ESCPOSAction]) -> None:
        """The serialized action list matches the committed snapshot exactly."""
        actual = _actions_to_dicts(actions)
        expected = _load_snapshot("test_receipt.json")

        assert actual == expected, (
            "Action list does not match snapshot.\n"
            f"Got {len(actual)} actions, expected {len(expected)}.\n"
            "Run with --update-snapshots to regenerate."
        )

    def test_dummy_printer_output_matches_snapshot(
        self, actions: list[ESCPOSAction]
    ) -> None:
        """Executing actions on a Dummy printer produces stable byte output.

        We capture the raw bytes from the Dummy printer and compare against a
        saved hex snapshot.  This tests the full printer driver dispatch path.
        """
        printer = Dummy()
        execute_actions(printer, actions)
        actual_bytes: bytes = printer.output

        snapshot_path = _SNAPSHOTS_DIR / "test_receipt_bytes.hex"

        if not snapshot_path.exists():
            # First run: save the snapshot.
            snapshot_path.write_text(actual_bytes.hex())
            pytest.skip("Snapshot created — re-run to verify.")

        expected_hex = snapshot_path.read_text().strip()
        assert actual_bytes.hex() == expected_hex, (
            "Dummy printer byte output does not match snapshot.\n"
            "Run with --update-snapshots to regenerate."
        )

    def test_snapshot_update(
        self, actions: list[ESCPOSAction], request: pytest.FixtureRequest
    ) -> None:
        """Regenerate snapshots when --update-snapshots flag is passed.

        Usage: pytest --update-snapshots tests/test_e2e_snapshot.py
        """
        if not request.config.getoption("--update-snapshots", default=False):
            pytest.skip("Pass --update-snapshots to regenerate snapshot files.")

        # Update action list snapshot.
        action_dicts = _actions_to_dicts(actions)
        _save_snapshot("test_receipt.json", action_dicts)

        # Update byte snapshot.
        printer = Dummy()
        execute_actions(printer, actions)
        snapshot_path = _SNAPSHOTS_DIR / "test_receipt_bytes.hex"
        snapshot_path.write_text(printer.output.hex())
