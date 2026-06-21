"""Tests for the CLI entry point (core.main)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.actions import TextAction
from core.main import main


def _patch_main():
    """Context manager stack that mocks load_system_config and setup_logging."""
    return (
        patch("core.main.load_system_config", return_value={"logging": {}}),
        patch("core.main.setup_logging"),
    )


class TestMainCLI:
    """Tests for the main() CLI entry point."""

    def test_parses_receipt_positional_argument(self) -> None:
        """Receipt path is parsed from the first positional argument."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            m1,
            m2,
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with(
            "receipts/test.json", config_path="config.yaml"
        )

    def test_parses_optional_config_argument(self) -> None:
        """--config flag overrides the default config path."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "receipts/test.json", "--config", "my.yaml"]),
            m1,
            m2,
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with("receipts/test.json", config_path="my.yaml")

    def test_default_config_is_config_yaml(self) -> None:
        """Without --config, the default config path is 'config.yaml'."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "receipts/patrick.json"]),
            m1,
            m2,
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with(
            "receipts/patrick.json", config_path="config.yaml"
        )

    def test_exits_with_code_0_on_success(self) -> None:
        """Successful execution does not call sys.exit (implicit exit 0)."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            m1,
            m2,
            patch("core.main.print_receipt"),
        ):
            main()

    def test_exits_with_code_1_on_exception(self) -> None:
        """sys.exit(1) is called when print_receipt raises an exception."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            m1,
            m2,
            patch(
                "core.main.print_receipt", side_effect=RuntimeError("printer on fire")
            ),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_calls_print_receipt_with_correct_arguments(self) -> None:
        """print_receipt is called with receipt path and config_path keyword."""
        m1, m2 = _patch_main()
        with (
            patch(
                "sys.argv",
                ["main.py", "receipts/daily.json", "--config", "prod.yaml"],
            ),
            m1,
            m2,
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_print.assert_called_once_with(
            "receipts/daily.json", config_path="prod.yaml"
        )

    def test_setup_logging_called_with_config(self) -> None:
        """setup_logging is called with the logging section from system config."""
        log_cfg = {"level": "DEBUG", "file": "logs/test.log"}
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            patch("core.main.load_system_config", return_value={"logging": log_cfg}),
            patch("core.main.setup_logging") as mock_setup,
            patch("core.main.print_receipt"),
        ):
            main()

        mock_setup.assert_called_once_with(log_cfg)

    def test_preview_flag_calls_generate_actions_and_render(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--preview calls generate_actions + render_preview instead of print_receipt."""
        m1, m2 = _patch_main()
        fake_actions = [TextAction(content="hello\n")]
        with (
            patch("sys.argv", ["main.py", "--preview", "receipts/test.json"]),
            m1,
            m2,
            patch("core.main.generate_actions", return_value=fake_actions) as mock_gen,
            patch("core.main.render_preview", return_value="hello\n") as mock_render,
            patch("core.main.print_receipt") as mock_print,
        ):
            main()

        mock_gen.assert_called_once_with(
            "receipts/test.json", config_path="config.yaml"
        )
        mock_render.assert_called_once_with(fake_actions)
        mock_print.assert_not_called()

    def test_preview_output_goes_to_stdout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--preview prints the rendered preview to stdout."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "--preview", "receipts/test.json"]),
            m1,
            m2,
            patch("core.main.generate_actions", return_value=[]),
            patch("core.main.render_preview", return_value="preview output\n"),
        ):
            main()

        captured = capsys.readouterr()
        assert "preview output" in captured.out

    def test_without_preview_flag_calls_print_receipt(self) -> None:
        """Without --preview, print_receipt is called normally."""
        m1, m2 = _patch_main()
        with (
            patch("sys.argv", ["main.py", "receipts/test.json"]),
            m1,
            m2,
            patch("core.main.print_receipt") as mock_print,
            patch("core.main.generate_actions") as mock_gen,
        ):
            main()

        mock_print.assert_called_once()
        mock_gen.assert_not_called()
