"""Tests for widgets.widget — Widget ABC, registry, and __init_subclass__."""

from typing import Any, ClassVar

import pytest

from core.actions import ESCPOSAction, TextAction
from core.context import Context
from widgets.widget import Widget


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the widget registry around each test."""
    original = Widget._registry.copy()
    yield
    Widget._registry.clear()
    Widget._registry.update(original)


class TestWidgetRegistration:
    """Test automatic registration via __init_subclass__."""

    def test_concrete_subclass_registers(self):
        class FooWidget(Widget):
            widget_type: ClassVar[str] = "foo_test_unique_1"

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        assert Widget._registry["foo_test_unique_1"] is FooWidget

    def test_get_returns_registered_class(self):
        class BarWidget(Widget):
            widget_type: ClassVar[str] = "bar_test_unique_1"

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        assert Widget.get("bar_test_unique_1") is BarWidget

    def test_duplicate_widget_type_raises(self):
        class FirstWidget(Widget):
            widget_type: ClassVar[str] = "duplicate_test_unique"

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        with pytest.raises(ValueError, match="Duplicate widget_type"):

            class SecondWidget(Widget):
                widget_type: ClassVar[str] = "duplicate_test_unique"

                def render(
                    self, params: dict[str, Any], context: Context
                ) -> list[ESCPOSAction]:
                    return []

    def test_missing_widget_type_raises(self):
        with pytest.raises(TypeError, match="must define 'widget_type'"):

            class NoTypeWidget(Widget):
                def render(
                    self, params: dict[str, Any], context: Context
                ) -> list[ESCPOSAction]:
                    return []


class TestWidgetAbstract:
    """Test abstract enforcement."""

    def test_cannot_instantiate_widget_directly(self):
        with pytest.raises(TypeError):
            Widget()  # type: ignore[abstract]

    def test_subclass_with_new_abstractmethod_still_registers(self):
        """Subclasses that add new abstract methods still register.

        Note: __init_subclass__ runs before ABCMeta sets __abstractmethods__,
        so the abstract-skip check in Widget cannot detect newly-added abstract
        methods at class creation time. This test documents the actual behavior.
        """
        from abc import abstractmethod

        class AbstractMiddle(Widget):
            widget_type: ClassVar[str] = "abstract_middle_test"

            @abstractmethod
            def extra(self) -> None: ...

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        # The class IS registered (this is the actual behavior)
        assert "abstract_middle_test" in Widget._registry

    def test_concrete_subclass_of_intermediate_registers(self):
        from abc import abstractmethod

        class AbstractMiddle2(Widget):
            widget_type: ClassVar[str] = "middle2_type_test"

            @abstractmethod
            def extra(self) -> None: ...

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        class ConcreteChild(AbstractMiddle2):
            widget_type: ClassVar[str] = "concrete_child_test"

            def extra(self) -> None:
                pass

        # Both get registered
        assert Widget.get("middle2_type_test") is AbstractMiddle2
        assert Widget.get("concrete_child_test") is ConcreteChild


class TestWidgetGet:
    """Test the get() class method."""

    def test_get_nonexistent_raises_keyerror(self):
        with pytest.raises(KeyError):
            Widget.get("nonexistent_widget_type_xyz")

    def test_get_returns_correct_class(self):
        class LookupWidget(Widget):
            widget_type: ClassVar[str] = "lookup_test_unique"

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return [TextAction(content="hello")]

        result = Widget.get("lookup_test_unique")
        assert result is LookupWidget


class TestWidgetRender:
    """Test render method contract."""

    def test_render_returns_action_list(self):
        class RenderWidget(Widget):
            widget_type: ClassVar[str] = "render_test_unique"

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return [TextAction(content=params.get("text", "default"))]

        import datetime

        ctx = Context(
            date=datetime.date(2025, 6, 15),
            time=datetime.time(10, 0),
            receipt_name="test",
        )
        widget = RenderWidget()
        actions = widget.render({"text": "hi"}, ctx)
        assert len(actions) == 1
        assert isinstance(actions[0], TextAction)
        assert actions[0].content == "hi"


class TestWidgetRequiredSecrets:
    """Test the required_secrets class variable."""

    def test_default_required_secrets_is_empty(self):
        class SimpleWidget(Widget):
            widget_type: ClassVar[str] = "simple_secrets_test"

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        assert SimpleWidget.required_secrets == []

    def test_custom_required_secrets(self):
        class SecretWidget(Widget):
            widget_type: ClassVar[str] = "secret_widget_test"
            required_secrets: ClassVar[list[str]] = ["API_KEY", "TOKEN"]

            def render(
                self, params: dict[str, Any], context: Context
            ) -> list[ESCPOSAction]:
                return []

        assert SecretWidget.required_secrets == ["API_KEY", "TOKEN"]
