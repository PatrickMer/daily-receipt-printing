"""Tests for core.engine — receipt printing orchestration."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.actions import TextAction
from core.context import Context
from core.engine import print_receipt


@pytest.fixture()
def _mock_pipeline() -> Any:
    """Patch all heavy dependencies and yield the mocks for inspection.

    Yields a dict with keys: system_config, receipt_config, validate_secrets,
    build_context, widget_cls, apply_layout, print_actions.
    """
    system_cfg = {"printer": {"host": "192.168.0.200"}}
    receipt_cfg = {
        "name": "test-receipt",
        "widgets": [
            {"type": "weather", "params": {"city": "Madrid"}},
            {"type": "calendar", "params": {}},
        ],
    }
    fake_context = MagicMock(spec=Context)

    widget_instance = MagicMock()
    widget_instance.render.return_value = [TextAction(content="hello\n")]
    fake_widget_cls = MagicMock(return_value=widget_instance)

    layout_result = [TextAction(content="laid out\n")]

    with (
        patch("core.engine.load_system_config", return_value=system_cfg) as m_sys,
        patch("core.engine.load_receipt_config", return_value=receipt_cfg) as m_rcpt,
        patch("core.engine.validate_secrets") as m_secrets,
        patch("core.engine.build_context", return_value=fake_context) as m_ctx,
        patch("core.engine.Widget") as m_widget,
        patch("core.engine.apply_layout", return_value=layout_result) as m_layout,
        patch("core.engine.print_actions") as m_print,
    ):
        m_widget.get.return_value = fake_widget_cls
        yield {
            "system_config": m_sys,
            "receipt_config": m_rcpt,
            "validate_secrets": m_secrets,
            "build_context": m_ctx,
            "widget_cls": fake_widget_cls,
            "widget_instance": widget_instance,
            "widget_get": m_widget.get,
            "apply_layout": m_layout,
            "print_actions": m_print,
            "fake_context": fake_context,
            "system_cfg": system_cfg,
            "receipt_cfg": receipt_cfg,
            "layout_result": layout_result,
        }


class TestHappyPath:
    """All modules called in correct order with correct arguments."""

    @pytest.fixture(autouse=True)
    def _setup(self, _mock_pipeline: Any) -> None:
        self.mocks = _mock_pipeline

    def test_load_system_config_called(self) -> None:
        print_receipt("receipts/test.json", config_path="custom.yaml")
        from pathlib import Path

        self.mocks["system_config"].assert_called_once_with(Path("custom.yaml"))

    def test_load_receipt_config_called(self) -> None:
        from pathlib import Path

        print_receipt("receipts/test.json")
        self.mocks["receipt_config"].assert_called_once_with(Path("receipts/test.json"))

    def test_validate_secrets_called(self) -> None:
        print_receipt("receipts/test.json")
        self.mocks["validate_secrets"].assert_called_once_with(
            self.mocks["receipt_cfg"]
        )

    def test_build_context_called_with_receipt_name(self) -> None:
        print_receipt("receipts/test.json")
        self.mocks["build_context"].assert_called_once_with("test-receipt")

    def test_widgets_executed(self) -> None:
        print_receipt("receipts/test.json")
        # Two widgets in the config, so Widget.get is called twice
        assert self.mocks["widget_get"].call_count == 2
        self.mocks["widget_get"].assert_any_call("weather")
        self.mocks["widget_get"].assert_any_call("calendar")

    def test_apply_layout_called_with_groups(self) -> None:
        print_receipt("receipts/test.json")
        call_args = self.mocks["apply_layout"].call_args
        widget_groups = call_args[0][0]
        # Two widgets, each producing one action
        assert len(widget_groups) == 2
        assert widget_groups[0] == [TextAction(content="hello\n")]
        assert widget_groups[1] == [TextAction(content="hello\n")]

    def test_print_actions_called(self) -> None:
        print_receipt("receipts/test.json")
        self.mocks["print_actions"].assert_called_once_with(
            self.mocks["system_cfg"], self.mocks["layout_result"]
        )


class TestDefaultConfigPath:
    """Default config_path is 'config.yaml'."""

    def test_default_config_path(self, _mock_pipeline: Any) -> None:
        from pathlib import Path

        print_receipt("receipts/test.json")
        _mock_pipeline["system_config"].assert_called_once_with(Path("config.yaml"))


class TestValidateSecretsRaises:
    """validate_secrets raising OSError propagates to caller."""

    def test_oserror_propagates(self) -> None:
        with (
            patch("core.engine.load_system_config", return_value={"printer": {}}),
            patch(
                "core.engine.load_receipt_config",
                return_value={"name": "x", "widgets": []},
            ),
            patch(
                "core.engine.validate_secrets",
                side_effect=OSError("Missing secrets: API_KEY"),
            ),
            patch("core.engine.build_context"),
            patch("core.engine.Widget"),
            patch("core.engine.apply_layout"),
            patch("core.engine.print_actions"),
            pytest.raises(OSError, match="Missing secrets"),
        ):
            print_receipt("receipts/test.json")


class TestWidgetFailureIsolation:
    """One widget failing does not block others."""

    def test_failing_widget_produces_placeholder_group(self) -> None:
        receipt_cfg: dict[str, Any] = {
            "name": "test",
            "widgets": [
                {"type": "good", "params": {}},
                {"type": "bad", "params": {}},
                {"type": "good", "params": {}},
            ],
        }

        good_widget = MagicMock()
        good_widget.render.return_value = [TextAction(content="ok\n")]
        good_cls = MagicMock(return_value=good_widget)

        bad_cls = MagicMock(side_effect=RuntimeError("boom"))

        def fake_get(widget_type: str) -> MagicMock:
            if widget_type == "bad":
                return bad_cls
            return good_cls

        fake_context = MagicMock(spec=Context)

        with (
            patch("core.engine.load_system_config", return_value={"printer": {}}),
            patch("core.engine.load_receipt_config", return_value=receipt_cfg),
            patch("core.engine.validate_secrets"),
            patch("core.engine.build_context", return_value=fake_context),
            patch("core.engine.Widget") as m_widget,
            patch("core.engine.apply_layout", return_value=[]) as m_layout,
            patch("core.engine.print_actions"),
        ):
            m_widget.get.side_effect = fake_get
            print_receipt("receipts/test.json")

            # apply_layout should receive 3 groups
            call_args = m_layout.call_args
            groups = call_args[0][0]
            assert len(groups) == 3
            # First and third are ok
            assert groups[0] == [TextAction(content="ok\n")]
            assert groups[2] == [TextAction(content="ok\n")]
            # Second is the placeholder
            assert len(groups[1]) == 1
            assert "bad" in groups[1][0].content
            assert "failed" in groups[1][0].content


class TestPrinterConnectionError:
    """OSError from print_actions is caught and logged, no crash."""

    def test_oserror_caught(self, caplog: pytest.LogCaptureFixture) -> None:
        receipt_cfg: dict[str, Any] = {"name": "test", "widgets": []}
        fake_context = MagicMock(spec=Context)

        with (
            patch("core.engine.load_system_config", return_value={"printer": {}}),
            patch("core.engine.load_receipt_config", return_value=receipt_cfg),
            patch("core.engine.validate_secrets"),
            patch("core.engine.build_context", return_value=fake_context),
            patch("core.engine.Widget"),
            patch("core.engine.apply_layout", return_value=[]),
            patch(
                "core.engine.print_actions",
                side_effect=OSError("Connection refused"),
            ),
        ):
            with caplog.at_level(logging.ERROR, logger="core.engine"):
                # Should NOT raise
                print_receipt("receipts/test.json")

            assert any("Printer connection failed" in r.message for r in caplog.records)

    def test_connection_error_caught(self, caplog: pytest.LogCaptureFixture) -> None:
        receipt_cfg: dict[str, Any] = {"name": "test", "widgets": []}
        fake_context = MagicMock(spec=Context)

        with (
            patch("core.engine.load_system_config", return_value={"printer": {}}),
            patch("core.engine.load_receipt_config", return_value=receipt_cfg),
            patch("core.engine.validate_secrets"),
            patch("core.engine.build_context", return_value=fake_context),
            patch("core.engine.Widget"),
            patch("core.engine.apply_layout", return_value=[]),
            patch(
                "core.engine.print_actions",
                side_effect=ConnectionError("Network unreachable"),
            ),
        ):
            with caplog.at_level(logging.ERROR, logger="core.engine"):
                print_receipt("receipts/test.json")

            assert any("Printer connection failed" in r.message for r in caplog.records)


class TestMissingReceiptFile:
    """FileNotFoundError from load_receipt_config propagates."""

    def test_file_not_found_propagates(self) -> None:
        with (
            patch("core.engine.load_system_config", return_value={"printer": {}}),
            patch(
                "core.engine.load_receipt_config",
                side_effect=FileNotFoundError("Receipt config file not found"),
            ),
            patch("core.engine.validate_secrets"),
            patch("core.engine.build_context"),
            patch("core.engine.Widget"),
            patch("core.engine.apply_layout"),
            patch("core.engine.print_actions"),
            pytest.raises(FileNotFoundError, match="not found"),
        ):
            print_receipt("nonexistent.json")
