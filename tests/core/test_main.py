"""Tests for the CLI entry point (core.main)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.main import main


class TestMainCLI:
    """Tests for the main() CLI entry point."""

    def test_parses_receipt_positional_argument(self) -> None:
        """Receipt path is parsed from the first positional argument."""
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with(
            "receipts/test.json", config_path="config.yaml"
        )

    def test_parses_optional_config_argument(self) -> None:
        """--config flag overrides the default config path."""
        with (
            patch("sys.argv", ["main.py", "receipts/test.json", "--config", "my.yaml"]),
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with("receipts/test.json", config_path="my.yaml")

    def test_default_config_is_config_yaml(self) -> None:
        """Without --config, the default config path is 'config.yaml'."""
        with (
            patch("sys.argv", ["main.py", "receipts/patrick.json"]),
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with(
            "receipts/patrick.json", config_path="config.yaml"
        )

    def test_exits_with_code_0_on_success(self) -> None:
        """Successful execution does not call sys.exit (implicit exit 0)."""
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            patch("core.main.print_receipt"),
        ):
            # Should not raise SystemExit
            main()

    def test_exits_with_code_1_on_exception(self) -> None:
        """sys.exit(1) is called when print_receipt raises an exception."""
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            patch(
                "core.main.print_receipt", side_effect=RuntimeError("printer on fire")
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_calls_print_receipt_with_correct_arguments(self) -> None:
        """print_receipt is called with receipt path and config_path keyword."""
        with (
            patch(
                "sys.argv",
                ["main.py", "receipts/daily.json", "--config", "prod.yaml"],
            ),
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with(
            "receipts/daily.json", config_path="prod.yaml"
        )
