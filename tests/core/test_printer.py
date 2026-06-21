"""Tests for core.printer — printer driver dispatch and connection logic."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from escpos.printer import Dummy

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
from core.printer import connect_printer, execute_actions, print_actions

# --- Fixtures ---


@pytest.fixture
def dummy_printer() -> Dummy:
    """Create a Dummy printer instance for testing."""
    return Dummy()


@pytest.fixture
def printer_config() -> dict[str, object]:
    """Sample system config with printer section."""
    return {
        "printer": {
            "host": "192.168.0.200",
            "port": 9100,
            "profile": "TM-T20II",
            "timeout": 10,
        }
    }


# --- TextAction dispatch ---


class TestTextActionDispatch:
    def test_text_is_sent_to_printer(self, dummy_printer: Dummy) -> None:
        actions = [TextAction(content="Hello, receipt!")]
        execute_actions(dummy_printer, actions)
        output = dummy_printer.output
        assert b"Hello, receipt!" in output

    def test_multiple_text_actions(self, dummy_printer: Dummy) -> None:
        actions = [
            TextAction(content="Line 1\n"),
            TextAction(content="Line 2\n"),
        ]
        execute_actions(dummy_printer, actions)
        output = dummy_printer.output
        assert b"Line 1\n" in output
        assert b"Line 2\n" in output


# --- SetAction dispatch ---


class TestSetActionDispatch:
    def test_set_calls_printer_set(self) -> None:
        printer = MagicMock()
        actions = [SetAction(align="center", bold=True, underline=1)]
        execute_actions(printer, actions)
        printer.set.assert_called_once_with(align="center", bold=True, underline=1)

    def test_set_only_passes_non_none_fields(self) -> None:
        printer = MagicMock()
        actions = [SetAction(bold=True)]
        execute_actions(printer, actions)
        printer.set.assert_called_once_with(bold=True)

    def test_set_with_all_fields(self) -> None:
        printer = MagicMock()
        actions = [
            SetAction(
                align="right",
                bold=False,
                underline=2,
                width=2,
                height=3,
                font="b",
                invert=True,
            )
        ]
        execute_actions(printer, actions)
        printer.set.assert_called_once_with(
            align="right",
            bold=False,
            underline=2,
            width=2,
            height=3,
            font="b",
            invert=True,
        )


# --- FeedAction dispatch ---


class TestFeedActionDispatch:
    def test_feed_calls_print_and_feed(self) -> None:
        printer = MagicMock()
        actions = [FeedAction(lines=3)]
        execute_actions(printer, actions)
        printer.print_and_feed.assert_called_once_with(3)

    def test_feed_default_lines(self) -> None:
        printer = MagicMock()
        actions = [FeedAction()]
        execute_actions(printer, actions)
        printer.print_and_feed.assert_called_once_with(1)


# --- CutAction dispatch ---


class TestCutActionDispatch:
    def test_cut_default_mode(self) -> None:
        printer = MagicMock()
        actions = [CutAction()]
        execute_actions(printer, actions)
        printer.cut.assert_called_once_with(mode="FULL")

    def test_cut_partial(self) -> None:
        printer = MagicMock()
        actions = [CutAction(mode="PART")]
        execute_actions(printer, actions)
        printer.cut.assert_called_once_with(mode="PART")


# --- QRAction dispatch ---


class TestQRActionDispatch:
    def test_qr_basic(self) -> None:
        printer = MagicMock()
        actions = [QRAction(content="https://example.com")]
        execute_actions(printer, actions)
        printer.qr.assert_called_once_with("https://example.com")

    def test_qr_with_options(self) -> None:
        printer = MagicMock()
        actions = [QRAction(content="data", size=8, native=True, center=True)]
        execute_actions(printer, actions)
        printer.qr.assert_called_once_with("data", size=8, native=True, center=True)


# --- BarcodeAction dispatch ---


class TestBarcodeActionDispatch:
    def test_barcode_required_fields(self) -> None:
        printer = MagicMock()
        actions = [BarcodeAction(code="123456789012", bc_type="EAN13")]
        execute_actions(printer, actions)
        printer.barcode.assert_called_once_with("123456789012", "EAN13")

    def test_barcode_with_optional_fields(self) -> None:
        printer = MagicMock()
        actions = [
            BarcodeAction(
                code="ABC123",
                bc_type="CODE128",
                height=100,
                width=3,
                pos="BELOW",
            )
        ]
        execute_actions(printer, actions)
        printer.barcode.assert_called_once_with(
            "ABC123", "CODE128", height=100, width=3, pos="BELOW"
        )


# --- ImageAction dispatch ---


class TestImageActionDispatch:
    def test_image_basic(self) -> None:
        printer = MagicMock()
        actions = [ImageAction(path="/tmp/logo.png")]
        execute_actions(printer, actions)
        printer.image.assert_called_once_with("/tmp/logo.png")

    def test_image_with_options(self) -> None:
        printer = MagicMock()
        actions = [ImageAction(path="/tmp/logo.png", center=True, impl="graphics")]
        execute_actions(printer, actions)
        printer.image.assert_called_once_with(
            "/tmp/logo.png", center=True, impl="graphics"
        )


# --- Unknown action type ---


class TestUnknownAction:
    def test_raises_value_error_for_unknown_action(self) -> None:
        @dataclass
        class FakeAction(ESCPOSAction):
            def __post_init__(self) -> None:
                self.action = "fake"

        printer = MagicMock()
        actions: list[ESCPOSAction] = [FakeAction()]
        with pytest.raises(ValueError, match="Unknown action type: FakeAction"):
            execute_actions(printer, actions)


# --- print_actions ensures close ---


class TestPrintActions:
    @patch("core.printer.connect_printer")
    def test_close_called_on_success(
        self, mock_connect: MagicMock, printer_config: dict[str, object]
    ) -> None:
        mock_printer = MagicMock()
        mock_connect.return_value = mock_printer
        actions = [TextAction(content="test")]

        print_actions(printer_config, actions)

        mock_printer.close.assert_called_once()

    @patch("core.printer.connect_printer")
    def test_close_called_on_exception(
        self, mock_connect: MagicMock, printer_config: dict[str, object]
    ) -> None:
        mock_printer = MagicMock()
        mock_printer.text.side_effect = RuntimeError("connection lost")
        mock_connect.return_value = mock_printer
        actions = [TextAction(content="test")]

        with pytest.raises(RuntimeError, match="connection lost"):
            print_actions(printer_config, actions)

        mock_printer.close.assert_called_once()


# --- connect_printer ---


class TestConnectPrinter:
    @patch("core.printer.Network")
    def test_constructs_with_config_values(
        self, mock_network_cls: MagicMock, printer_config: dict[str, object]
    ) -> None:
        mock_instance = MagicMock()
        mock_network_cls.return_value = mock_instance

        result = connect_printer(printer_config)

        mock_network_cls.assert_called_once_with(
            host="192.168.0.200",
            port=9100,
            timeout=10,
            profile="TM-T20II",
        )
        mock_instance.open.assert_called_once()
        assert result is mock_instance

    @patch("core.printer.Network")
    def test_uses_defaults_for_missing_optional_config(
        self, mock_network_cls: MagicMock
    ) -> None:
        mock_instance = MagicMock()
        mock_network_cls.return_value = mock_instance
        config = {"printer": {"host": "10.0.0.1"}}

        connect_printer(config)

        mock_network_cls.assert_called_once_with(
            host="10.0.0.1",
            port=9100,
            timeout=10,
            profile="default",
        )


# --- set_with_default is called after execution ---


class TestSetWithDefault:
    def test_set_with_default_called_after_actions(self) -> None:
        printer = MagicMock()
        actions = [TextAction(content="hello")]
        execute_actions(printer, actions)
        printer.set_with_default.assert_called_once()

    def test_set_with_default_called_even_with_empty_actions(self) -> None:
        printer = MagicMock()
        execute_actions(printer, [])
        printer.set_with_default.assert_called_once()
