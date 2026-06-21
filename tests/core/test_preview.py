"""Tests for core.preview — plain-text receipt preview renderer."""

from __future__ import annotations

from core.actions import (
    BarcodeAction,
    CutAction,
    FeedAction,
    ImageAction,
    QRAction,
    SetAction,
    TextAction,
)
from core.preview import render_preview


class TestTextActionLeftAlign:
    """TextAction with default left alignment passes content unchanged."""

    def test_single_line(self) -> None:
        actions = [TextAction(content="Hello world\n")]
        result = render_preview(actions)
        assert result == "Hello world\n"

    def test_no_padding_added(self) -> None:
        actions = [TextAction(content="short\n")]
        result = render_preview(actions)
        assert result == "short\n"


class TestTextActionCenterAlign:
    """TextAction with center alignment centers content within columns."""

    def test_centered_text(self) -> None:
        actions = [
            SetAction(align="center"),
            TextAction(content="Hi\n"),
        ]
        result = render_preview(actions, columns=10)
        lines = result.split("\n")
        # "Hi" centered in 10 columns = "    Hi    "
        assert lines[0] == "    Hi    "

    def test_centered_preserves_trailing_newline(self) -> None:
        actions = [
            SetAction(align="center"),
            TextAction(content="X\n"),
        ]
        result = render_preview(actions, columns=10)
        assert result.endswith("\n")


class TestTextActionRightAlign:
    """TextAction with right alignment right-justifies content."""

    def test_right_justified(self) -> None:
        actions = [
            SetAction(align="right"),
            TextAction(content="Hi\n"),
        ]
        result = render_preview(actions, columns=10)
        lines = result.split("\n")
        # "Hi" rjust(10) = "        Hi"
        assert lines[0] == "        Hi"


class TestSetActionAlignment:
    """SetAction changes alignment state for subsequent text."""

    def test_alignment_changes_mid_stream(self) -> None:
        actions = [
            TextAction(content="left\n"),
            SetAction(align="right"),
            TextAction(content="right\n"),
        ]
        result = render_preview(actions, columns=10)
        lines = result.split("\n")
        assert lines[0] == "left"
        assert lines[1] == "     right"


class TestSetActionBold:
    """SetAction bold=True makes text uppercase."""

    def test_bold_uppercases(self) -> None:
        actions = [
            SetAction(bold=True),
            TextAction(content="hello\n"),
        ]
        result = render_preview(actions)
        assert "HELLO" in result

    def test_bold_off_restores_case(self) -> None:
        actions = [
            SetAction(bold=True),
            TextAction(content="bold\n"),
            SetAction(bold=False),
            TextAction(content="normal\n"),
        ]
        result = render_preview(actions)
        lines = result.split("\n")
        assert lines[0] == "BOLD"
        assert lines[1] == "normal"


class TestFeedAction:
    """FeedAction produces blank lines."""

    def test_single_feed(self) -> None:
        actions = [FeedAction(lines=1)]
        result = render_preview(actions)
        assert result == "\n"

    def test_multiple_feed_lines(self) -> None:
        actions = [FeedAction(lines=3)]
        result = render_preview(actions)
        assert result == "\n\n\n"


class TestCutAction:
    """CutAction produces a visual cut line of '=' characters."""

    def test_default_columns(self) -> None:
        actions = [CutAction()]
        result = render_preview(actions)
        assert result == "=" * 48 + "\n"

    def test_custom_columns(self) -> None:
        actions = [CutAction()]
        result = render_preview(actions, columns=32)
        assert result == "=" * 32 + "\n"


class TestQRAction:
    """QRAction renders a placeholder with alignment."""

    def test_qr_placeholder_left(self) -> None:
        actions = [QRAction(content="https://example.com")]
        result = render_preview(actions)
        assert result == "[QR: https://example.com]\n"

    def test_qr_placeholder_center(self) -> None:
        actions = [
            SetAction(align="center"),
            QRAction(content="data"),
        ]
        result = render_preview(actions, columns=20)
        line = result.rstrip("\n")
        assert line == "[QR: data]".center(20)


class TestBarcodeAction:
    """BarcodeAction renders a placeholder."""

    def test_barcode_placeholder(self) -> None:
        actions = [BarcodeAction(code="123456789", bc_type="EAN13")]
        result = render_preview(actions)
        assert result == "[BARCODE: 123456789]\n"

    def test_barcode_right_aligned(self) -> None:
        actions = [
            SetAction(align="right"),
            BarcodeAction(code="ABC", bc_type="CODE39"),
        ]
        result = render_preview(actions, columns=20)
        line = result.rstrip("\n")
        assert line == "[BARCODE: ABC]".rjust(20)


class TestImageAction:
    """ImageAction renders a placeholder."""

    def test_image_placeholder(self) -> None:
        actions = [ImageAction(path="/tmp/logo.png")]
        result = render_preview(actions)
        assert result == "[IMAGE: /tmp/logo.png]\n"


class TestMultiLineText:
    """Multi-line TextAction — each line aligned independently."""

    def test_multiline_center(self) -> None:
        actions = [
            SetAction(align="center"),
            TextAction(content="AB\nCD\n"),
        ]
        result = render_preview(actions, columns=10)
        lines = result.split("\n")
        assert lines[0] == "AB".center(10)
        assert lines[1] == "CD".center(10)
        # trailing empty line from trailing \n
        assert lines[2] == ""

    def test_multiline_preserves_empty_lines(self) -> None:
        actions = [
            SetAction(align="right"),
            TextAction(content="A\n\nB\n"),
        ]
        result = render_preview(actions, columns=10)
        lines = result.split("\n")
        assert lines[0] == "A".rjust(10)
        # Empty line stays empty (not padded)
        assert lines[1] == ""
        assert lines[2] == "B".rjust(10)


class TestFullIntegration:
    """Full integration — set center+bold, text, set left, text, cut."""

    def test_combined_workflow(self) -> None:
        actions = [
            SetAction(align="center", bold=True),
            TextAction(content="TITLE\n"),
            SetAction(align="left", bold=False),
            TextAction(content="Body text\n"),
            CutAction(),
        ]
        result = render_preview(actions, columns=20)
        lines = result.split("\n")
        # Title centered and bold (already uppercase, but bold uppercases it)
        assert lines[0] == "TITLE".center(20)
        # Body left-aligned
        assert lines[1] == "Body text"
        # Cut line
        assert lines[2] == "=" * 20


class TestCustomColumns:
    """Custom columns width is respected throughout."""

    def test_narrow_columns(self) -> None:
        actions = [
            SetAction(align="center"),
            TextAction(content="Hi\n"),
            CutAction(),
        ]
        result = render_preview(actions, columns=6)
        lines = result.split("\n")
        assert lines[0] == "  Hi  "
        assert lines[1] == "======"
