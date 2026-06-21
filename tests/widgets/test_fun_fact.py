"""Tests for widgets.fun_fact — Useless Facts API widget."""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests as req

from core.actions import SetAction, TextAction
from core.context import Context
from widgets.fun_fact import _FALLBACK_FACTS, FunFactWidget, _select_fallback


@pytest.fixture()
def widget() -> FunFactWidget:
    """Fresh FunFactWidget instance."""
    return FunFactWidget()


@pytest.fixture()
def context() -> Context:
    """Context on 2026-06-21 at 08:00."""
    return Context(
        date=datetime.date(2026, 6, 21),
        time=datetime.time(8, 0),
        receipt_name="test",
    )


def _make_api_response(
    text: str = "Ducks can sleep with one eye open.",
) -> dict[str, Any]:
    """Build a realistic Useless Facts API response."""
    return {
        "id": "abc123",
        "text": text,
        "source": "https://example.com",
        "language": "en",
    }


class TestFunFactHappyPath:
    """Happy path — API returns a fact, text is wrapped."""

    @patch("widgets.fun_fact.requests.get")
    def test_api_success_returns_wrapped_fact(
        self,
        mock_get: MagicMock,
        widget: FunFactWidget,
        context: Context,
    ) -> None:
        """API returns a fact that is rendered as wrapped text."""
        fact_text = "A duck's quack doesn't echo, and no one knows why."
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_api_response(fact_text)
        mock_get.return_value = resp

        actions = widget.render({}, context)

        assert isinstance(actions[0], SetAction)
        assert actions[0].bold is True
        assert isinstance(actions[1], TextAction)
        assert actions[1].content == "Fun Fact\n"
        assert isinstance(actions[2], SetAction)
        assert actions[2].bold is False
        assert isinstance(actions[3], TextAction)
        # Text may be wrapped, so compare without internal newlines
        assert fact_text == actions[3].content.replace("\n", " ").strip()

    @patch("widgets.fun_fact.requests.get")
    def test_api_called_with_correct_params(
        self,
        mock_get: MagicMock,
        widget: FunFactWidget,
        context: Context,
    ) -> None:
        """API is called with language=en and 10s timeout."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_api_response()
        mock_get.return_value = resp

        widget.render({}, context)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["language"] == "en"
        assert call_kwargs[1]["timeout"] == 10


class TestFunFactAPITimeout:
    """API timeout falls back to hardcoded fact."""

    @patch("widgets.fun_fact.requests.get")
    def test_timeout_uses_fallback(
        self,
        mock_get: MagicMock,
        widget: FunFactWidget,
        context: Context,
    ) -> None:
        """requests.Timeout triggers fallback fact."""
        mock_get.side_effect = req.Timeout("Connection timed out")

        actions = widget.render({}, context)

        assert len(actions) == 4
        fact_action = actions[3]
        assert isinstance(fact_action, TextAction)
        # Should be one of the fallback facts
        expected = _select_fallback(context.date.isoformat())
        actual_unwrapped = fact_action.content.replace("\n", " ").strip()
        assert expected == actual_unwrapped


class TestFunFactConnectionError:
    """Connection error falls back to hardcoded fact."""

    @patch("widgets.fun_fact.requests.get")
    def test_connection_error_uses_fallback(
        self,
        mock_get: MagicMock,
        widget: FunFactWidget,
        context: Context,
    ) -> None:
        """requests.ConnectionError triggers fallback fact."""
        mock_get.side_effect = req.ConnectionError("DNS resolution failed")

        actions = widget.render({}, context)

        assert len(actions) == 4
        fact_action = actions[3]
        assert isinstance(fact_action, TextAction)
        expected = _select_fallback(context.date.isoformat())
        actual_unwrapped = fact_action.content.replace("\n", " ").strip()
        assert expected == actual_unwrapped


class TestFunFactMalformedResponse:
    """Malformed API response (missing 'text' key) falls back."""

    @patch("widgets.fun_fact.requests.get")
    def test_missing_text_key_uses_fallback(
        self,
        mock_get: MagicMock,
        widget: FunFactWidget,
        context: Context,
    ) -> None:
        """Response without 'text' key triggers fallback."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"id": "abc", "source": "x", "language": "en"}
        mock_get.return_value = resp

        actions = widget.render({}, context)

        assert len(actions) == 4
        fact_action = actions[3]
        assert isinstance(fact_action, TextAction)
        expected = _select_fallback(context.date.isoformat())
        actual_unwrapped = fact_action.content.replace("\n", " ").strip()
        assert expected == actual_unwrapped


class TestFunFactCustomColumns:
    """Custom columns param controls text wrapping width."""

    @patch("widgets.fun_fact.requests.get")
    def test_text_wrapped_to_custom_width(
        self,
        mock_get: MagicMock,
        widget: FunFactWidget,
        context: Context,
    ) -> None:
        """With columns=20, long text is wrapped at 20 chars."""
        long_fact = (
            "This is a very long fact that should be wrapped at twenty characters."
        )
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = _make_api_response(long_fact)
        mock_get.return_value = resp

        actions = widget.render({"columns": 20}, context)

        fact_action = actions[3]
        assert isinstance(fact_action, TextAction)
        # Each line (except possibly the last) should be <= 20 chars
        lines = fact_action.content.rstrip("\n").split("\n")
        for line in lines:
            assert len(line) <= 20


class TestFunFactFallbackDeterministic:
    """Fallback selection is deterministic per date."""

    def test_same_date_same_fallback(self) -> None:
        """The same date always produces the same fallback fact."""
        date_str = "2026-06-21"
        fact1 = _select_fallback(date_str)
        fact2 = _select_fallback(date_str)
        assert fact1 == fact2
        assert fact1 in _FALLBACK_FACTS

    def test_different_dates_can_produce_different_fallbacks(self) -> None:
        """Different dates may produce different fallback facts."""
        results = set()
        for day in range(1, 31):
            date_str = f"2026-06-{day:02d}"
            results.add(_select_fallback(date_str))
        # With 30 dates and 10 fallbacks, we should see more than 1 unique fact
        assert len(results) > 1


class TestFunFactMetadata:
    """Widget type and required_secrets metadata."""

    def test_widget_type_is_fun_fact(self) -> None:
        assert FunFactWidget.widget_type == "fun-fact"

    def test_required_secrets_empty(self) -> None:
        assert FunFactWidget.required_secrets == []
