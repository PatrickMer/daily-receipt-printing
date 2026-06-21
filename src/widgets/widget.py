"""Widget abstract base class and autodiscovery registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from core.actions import ESCPOSAction
from core.context import Context


class Widget(ABC):
    """Base class for all receipt widgets.

    Subclasses must define ``widget_type`` (a string matching the receipt JSON
    ``"type"`` field) and implement :meth:`render`.  Registration happens
    automatically via :meth:`__init_subclass__`.
    """

    widget_type: ClassVar[str]
    required_secrets: ClassVar[list[str]] = []

    _registry: ClassVar[dict[str, type[Widget]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Skip abstract intermediate classes.
        if getattr(cls, "__abstractmethods__", None):
            return

        widget_type = getattr(cls, "widget_type", None)
        if widget_type is None:
            raise TypeError(f"{cls.__name__} must define 'widget_type'")

        if widget_type in Widget._registry:
            existing = Widget._registry[widget_type]
            raise ValueError(
                f"Duplicate widget_type '{widget_type}': "
                f"{cls.__name__} conflicts with {existing.__name__}"
            )

        Widget._registry[widget_type] = cls

    @abstractmethod
    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        """Render the widget into a sequence of ESC/POS actions.

        Args:
            params: Widget-specific parameters from the receipt JSON config.
            context: Shared execution context (date, time, receipt name).

        Returns:
            Ordered list of printer actions representing this widget's output.
        """
        ...

    @classmethod
    def get(cls, widget_type: str) -> type[Widget]:
        """Look up a widget class by its type string.

        Raises:
            KeyError: If no widget is registered for *widget_type*.
        """
        return cls._registry[widget_type]
