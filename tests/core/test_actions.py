"""Tests for core.actions — ESCPOSAction dataclasses."""

import pytest

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

# --- Base class tests ---


class TestESCPOSActionBase:
    """The abstract base class cannot be instantiated directly."""

    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            ESCPOSAction()  # type: ignore[abstract]


# --- SetAction tests ---


class TestSetAction:
    def test_defaults(self):
        action = SetAction()
        assert action.action == "set"
        assert action.align is None
        assert action.bold is None
        assert action.underline is None
        assert action.width is None
        assert action.height is None
        assert action.font is None
        assert action.invert is None

    def test_all_fields(self):
        action = SetAction(
            align="center",
            bold=True,
            underline=2,
            width=2,
            height=3,
            font="b",
            invert=True,
        )
        assert action.action == "set"
        assert action.align == "center"
        assert action.bold is True
        assert action.underline == 2
        assert action.width == 2
        assert action.height == 3
        assert action.font == "b"
        assert action.invert is True

    def test_partial_fields(self):
        action = SetAction(align="right", bold=False)
        assert action.align == "right"
        assert action.bold is False
        assert action.font is None


# --- TextAction tests ---


class TestTextAction:
    def test_basic_text(self):
        action = TextAction(content="Hello, World!")
        assert action.action == "text"
        assert action.content == "Hello, World!"

    def test_empty_string(self):
        action = TextAction(content="")
        assert action.action == "text"
        assert action.content == ""

    def test_content_is_required(self):
        with pytest.raises(TypeError):
            TextAction()  # type: ignore[call-arg]


# --- FeedAction tests ---


class TestFeedAction:
    def test_default_lines(self):
        action = FeedAction()
        assert action.action == "feed"
        assert action.lines == 1

    def test_custom_lines(self):
        action = FeedAction(lines=5)
        assert action.lines == 5


# --- ImageAction tests ---


class TestImageAction:
    def test_required_path(self):
        action = ImageAction(path="/tmp/image.png")
        assert action.action == "image"
        assert action.path == "/tmp/image.png"
        assert action.center is None
        assert action.impl is None

    def test_all_fields(self):
        action = ImageAction(path="logo.bmp", center=True, impl="graphics")
        assert action.path == "logo.bmp"
        assert action.center is True
        assert action.impl == "graphics"

    def test_path_is_required(self):
        with pytest.raises(TypeError):
            ImageAction()  # type: ignore[call-arg]


# --- QRAction tests ---


class TestQRAction:
    def test_required_content(self):
        action = QRAction(content="https://example.com")
        assert action.action == "qr"
        assert action.content == "https://example.com"
        assert action.size is None
        assert action.native is None
        assert action.center is None

    def test_all_fields(self):
        action = QRAction(content="data", size=8, native=True, center=True)
        assert action.size == 8
        assert action.native is True
        assert action.center is True

    def test_content_is_required(self):
        with pytest.raises(TypeError):
            QRAction()  # type: ignore[call-arg]


# --- BarcodeAction tests ---


class TestBarcodeAction:
    def test_required_fields(self):
        action = BarcodeAction(code="123456789", bc_type="EAN13")
        assert action.action == "barcode"
        assert action.code == "123456789"
        assert action.bc_type == "EAN13"
        assert action.height is None
        assert action.width is None
        assert action.pos is None

    def test_all_fields(self):
        action = BarcodeAction(
            code="ABC", bc_type="CODE128", height=100, width=3, pos="BELOW"
        )
        assert action.height == 100
        assert action.width == 3
        assert action.pos == "BELOW"

    def test_missing_required_fields(self):
        with pytest.raises(TypeError):
            BarcodeAction()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            BarcodeAction(code="123")  # type: ignore[call-arg]


# --- CutAction tests ---


class TestCutAction:
    def test_default_mode(self):
        action = CutAction()
        assert action.action == "cut"
        assert action.mode == "FULL"

    def test_partial_mode(self):
        action = CutAction(mode="PART")
        assert action.mode == "PART"


# --- Inheritance / polymorphism tests ---


class TestActionInheritance:
    def test_all_subclasses_are_escpos_actions(self):
        actions = [
            SetAction(),
            TextAction(content="x"),
            FeedAction(),
            ImageAction(path="p"),
            QRAction(content="q"),
            BarcodeAction(code="c", bc_type="t"),
            CutAction(),
        ]
        for a in actions:
            assert isinstance(a, ESCPOSAction)

    def test_action_field_not_in_init(self):
        """The 'action' field is set by __post_init__, not via __init__."""
        # SetAction(action="custom") should raise because action is init=False
        with pytest.raises(TypeError):
            SetAction(action="custom")  # type: ignore[call-arg]
