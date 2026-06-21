"""Tests for core.runner — widget runner logic."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import pytest

from core.actions import ESCPOSAction, TextAction
from core.context import Context
from core.runner import run_widgets
from widgets.widget import Widget


@pytest.fixture()
def context() -> Context:
    """Provide a fixed Context for all tests."""
    return Context(
        date=datetime.date(2025, 6, 15),
        time=datetime.time(9, 0, 0),
        receipt_name="test",
    )


def _make_config(widgets: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal receipt config dict."""
    return {"name": "test", "widgets": widgets}


class _FakeWidgetA(Widget):
    """Fake widget returning two TextActions."""

    widget_type = "__test_a__"

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        return [TextAction(content="A1"), TextAction(content="A2")]


class _FakeWidgetB(Widget):
    """Fake widget that echoes a param."""

    widget_type = "__test_b__"

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        return [TextAction(content=f"B:{params.get('msg', '')}")]


class _FakeWidgetExploding(Widget):
    """Fake widget that always raises."""

    widget_type = "__test_exploding__"

    def render(self, params: dict[str, Any], context: Context) -> list[ESCPOSAction]:
        raise RuntimeError("boom")


class TestRunWidgetsHappyPath:
    """Multiple widgets render successfully and actions are concatenated."""

    def test_actions_concatenated(self, context: Context) -> None:
        config = _make_config(
            [
                {"type": "__test_a__", "params": {}},
                {"type": "__test_b__", "params": {"msg": "hello"}},
            ]
        )
        actions = run_widgets(config, context)

        assert len(actions) == 3
        assert isinstance(actions[0], TextAction)
        assert actions[0].content == "A1"
        assert actions[1].content == "A2"
        assert actions[2].content == "B:hello"


class TestRunWidgetsUnknownType:
    """Unknown widget type is logged, placeholder inserted, others still run."""

    def test_unknown_type_produces_placeholder(self, context: Context) -> None:
        config = _make_config(
            [
                {"type": "nonexistent_widget_xyz", "params": {}},
                {"type": "__test_a__", "params": {}},
            ]
        )
        actions = run_widgets(config, context)

        # First action should be error placeholder
        assert isinstance(actions[0], TextAction)
        assert "nonexistent_widget_xyz" in actions[0].content
        assert "failed" in actions[0].content

        # Second widget's actions should still be present
        assert actions[1].content == "A1"
        assert actions[2].content == "A2"

    def test_unknown_type_is_logged(
        self, context: Context, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config([{"type": "nonexistent_widget_xyz", "params": {}}])
        with caplog.at_level(logging.ERROR, logger="core.runner"):
            run_widgets(config, context)

        assert any("nonexistent_widget_xyz" in r.message for r in caplog.records)


class TestRunWidgetsRenderException:
    """Widget render raises — logged, placeholder inserted, others still run."""

    def test_exception_produces_placeholder(self, context: Context) -> None:
        config = _make_config(
            [
                {"type": "__test_a__", "params": {}},
                {"type": "__test_exploding__", "params": {}},
                {"type": "__test_b__", "params": {"msg": "ok"}},
            ]
        )
        actions = run_widgets(config, context)

        # Widget A actions
        assert actions[0].content == "A1"
        assert actions[1].content == "A2"
        # Exploding widget placeholder
        assert isinstance(actions[2], TextAction)
        assert "__test_exploding__" in actions[2].content
        assert "failed" in actions[2].content
        # Widget B still runs
        assert actions[3].content == "B:ok"

    def test_render_exception_is_logged(
        self, context: Context, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _make_config([{"type": "__test_exploding__", "params": {}}])
        with caplog.at_level(logging.ERROR, logger="core.runner"):
            run_widgets(config, context)

        assert any("__test_exploding__" in r.message for r in caplog.records)


class TestRunWidgetsEmptyList:
    """Empty widget list returns empty actions list."""

    def test_empty_widgets(self, context: Context) -> None:
        config = _make_config([])
        actions = run_widgets(config, context)
        assert actions == []

    def test_missing_widgets_key(self, context: Context) -> None:
        config: dict[str, Any] = {"name": "test"}
        actions = run_widgets(config, context)
        assert actions == []


class TestRunWidgetsEmptyParams:
    """Widget with no params key passes empty dict to render."""

    def test_no_params_key(self, context: Context) -> None:
        config = _make_config([{"type": "__test_b__"}])
        actions = run_widgets(config, context)

        # _FakeWidgetB uses params.get('msg', '') which returns '' for empty dict
        assert len(actions) == 1
        assert actions[0].content == "B:"

    def test_explicit_empty_params(self, context: Context) -> None:
        config = _make_config([{"type": "__test_b__", "params": {}}])
        actions = run_widgets(config, context)

        assert len(actions) == 1
        assert actions[0].content == "B:"
