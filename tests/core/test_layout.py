"""Tests for the layout engine."""

from __future__ import annotations

import datetime

import pytest

from core.actions import (
    CutAction,
    ESCPOSAction,
    FeedAction,
    SetAction,
    TextAction,
)
from core.context import Context
from core.layout import apply_layout


@pytest.fixture()
def context() -> Context:
    """Standard test context."""
    return Context(
        date=datetime.date(2026, 6, 21),
        time=datetime.time(8, 30),
        receipt_name="patrick",
    )


@pytest.fixture()
def widget_groups() -> list[list[ESCPOSAction]]:
    """Two simple widget groups for testing."""
    return [
        [TextAction(content="Widget 1 output\n")],
        [TextAction(content="Widget 2 output\n")],
    ]


class TestFullLayout:
    """Full layout with header, separators, and cut."""

    def test_full_layout_order(
        self,
        context: Context,
        widget_groups: list[list[ESCPOSAction]],
    ) -> None:
        config: dict = {
            "name": "patrick",
            "layout": {"header": True, "separator": True, "cut_at_end": True},
        }
        result = apply_layout(widget_groups, config, context)

        # Header: SetAction(center, bold), Text(name), Text(date), SetAction(reset)
        assert isinstance(result[0], SetAction)
        assert result[0].align == "center"
        assert result[0].bold is True
        assert isinstance(result[1], TextAction)
        assert "patrick" in result[1].content
        assert isinstance(result[2], TextAction)
        assert "2026" in result[2].content
        assert isinstance(result[3], SetAction)  # reset

        # Separator after header
        assert isinstance(result[4], TextAction)
        assert result[4].content == "-" * 48 + "\n"

        # Widget 1 output
        assert isinstance(result[5], TextAction)
        assert result[5].content == "Widget 1 output\n"

        # Separator between widgets
        assert isinstance(result[6], TextAction)
        assert result[6].content == "-" * 48 + "\n"

        # Widget 2 output
        assert isinstance(result[7], TextAction)
        assert result[7].content == "Widget 2 output\n"

        # No trailing separator after last widget

        # Cut: Feed + Cut
        assert isinstance(result[8], FeedAction)
        assert result[8].lines == 3
        assert isinstance(result[9], CutAction)

        # Total actions
        assert len(result) == 10


class TestHeaderOnly:
    """Header enabled, separator and cut disabled."""

    def test_header_only(
        self,
        context: Context,
        widget_groups: list[list[ESCPOSAction]],
    ) -> None:
        config: dict = {
            "name": "patrick",
            "layout": {"header": True, "separator": False, "cut_at_end": False},
        }
        result = apply_layout(widget_groups, config, context)

        # Header actions (4) + widget1 (1) + widget2 (1) = 6
        assert len(result) == 6
        assert isinstance(result[0], SetAction)
        assert isinstance(result[4], TextAction)
        assert result[4].content == "Widget 1 output\n"
        assert isinstance(result[5], TextAction)
        assert result[5].content == "Widget 2 output\n"

        # No separator, no cut
        assert not any(isinstance(a, CutAction) for a in result)
        assert not any(
            isinstance(a, TextAction) and a.content.startswith("---") for a in result
        )


class TestSeparatorBetweenWidgets:
    """Separator inserted between widget groups."""

    def test_separator_content(
        self,
        context: Context,
    ) -> None:
        groups: list[list[ESCPOSAction]] = [
            [TextAction(content="A\n")],
            [TextAction(content="B\n")],
            [TextAction(content="C\n")],
        ]
        config: dict = {
            "layout": {"header": False, "separator": True, "cut_at_end": False},
        }
        result = apply_layout(groups, config, context)

        # A, sep, B, sep, C = 5 actions
        assert len(result) == 5
        assert result[1].content == "-" * 48 + "\n"  # type: ignore[attr-defined]
        assert result[3].content == "-" * 48 + "\n"  # type: ignore[attr-defined]

    def test_no_trailing_separator(
        self,
        context: Context,
    ) -> None:
        groups: list[list[ESCPOSAction]] = [
            [TextAction(content="Only\n")],
        ]
        config: dict = {
            "layout": {"header": False, "separator": True, "cut_at_end": False},
        }
        result = apply_layout(groups, config, context)

        # Just the single widget output, no separator
        assert len(result) == 1
        assert result[0].content == "Only\n"  # type: ignore[attr-defined]


class TestCustomColumns:
    """Custom column width affects separator."""

    def test_custom_columns_32(
        self,
        context: Context,
        widget_groups: list[list[ESCPOSAction]],
    ) -> None:
        config: dict = {
            "layout": {
                "header": False,
                "separator": True,
                "cut_at_end": False,
                "columns": 32,
            },
        }
        result = apply_layout(widget_groups, config, context)

        separators = [
            a for a in result if isinstance(a, TextAction) and "-" * 10 in a.content
        ]
        assert len(separators) == 1
        assert separators[0].content == "-" * 32 + "\n"


class TestNoLayoutConfig:
    """No layout key in config — uses all defaults."""

    def test_defaults_applied(
        self,
        context: Context,
        widget_groups: list[list[ESCPOSAction]],
    ) -> None:
        config: dict = {"name": "patrick"}
        result = apply_layout(widget_groups, config, context)

        # Defaults: header=True, separator=True, cut_at_end=True, columns=48
        # Header (4) + sep (1) + widget1 (1) + sep (1) + widget2 (1) + feed (1) + cut (1) = 10
        assert len(result) == 10
        assert isinstance(result[0], SetAction)
        assert isinstance(result[-1], CutAction)

        # Separator uses 48 columns
        sep_actions = [
            a
            for a in result
            if isinstance(a, TextAction) and a.content == "-" * 48 + "\n"
        ]
        assert len(sep_actions) == 2  # after header + between widgets


class TestEmptyWidgetGroups:
    """Empty widget groups are skipped."""

    def test_empty_groups_skipped(
        self,
        context: Context,
    ) -> None:
        groups: list[list[ESCPOSAction]] = [
            [TextAction(content="A\n")],
            [],  # empty
            [TextAction(content="B\n")],
            [],  # empty
        ]
        config: dict = {
            "layout": {"header": False, "separator": True, "cut_at_end": False},
        }
        result = apply_layout(groups, config, context)

        # A, sep, B = 3 (empty groups ignored)
        assert len(result) == 3
        assert result[0].content == "A\n"  # type: ignore[attr-defined]
        assert result[1].content == "-" * 48 + "\n"  # type: ignore[attr-defined]
        assert result[2].content == "B\n"  # type: ignore[attr-defined]

    def test_all_empty_groups(
        self,
        context: Context,
    ) -> None:
        groups: list[list[ESCPOSAction]] = [[], [], []]
        config: dict = {
            "layout": {"header": False, "separator": True, "cut_at_end": False},
        }
        result = apply_layout(groups, config, context)
        assert result == []


class TestCutOnly:
    """Cut at end appends feed + cut."""

    def test_cut_actions(
        self,
        context: Context,
    ) -> None:
        groups: list[list[ESCPOSAction]] = [
            [TextAction(content="Content\n")],
        ]
        config: dict = {
            "layout": {"header": False, "separator": False, "cut_at_end": True},
        }
        result = apply_layout(groups, config, context)

        assert len(result) == 3
        assert isinstance(result[0], TextAction)
        assert isinstance(result[1], FeedAction)
        assert result[1].lines == 3
        assert isinstance(result[2], CutAction)


class TestHeaderDateFormatting:
    """Header date is formatted correctly."""

    def test_date_format(self) -> None:
        ctx = Context(
            date=datetime.date(2026, 1, 5),
            time=datetime.time(10, 0),
            receipt_name="test_user",
        )
        groups: list[list[ESCPOSAction]] = []
        config: dict = {
            "layout": {"header": True, "separator": False, "cut_at_end": False},
        }
        result = apply_layout(groups, config, ctx)

        # Header: Set, name, date, reset
        assert len(result) == 4
        date_action = result[2]
        assert isinstance(date_action, TextAction)
        assert date_action.content == "Monday, January 05, 2026\n"

    def test_receipt_name_in_header(self) -> None:
        ctx = Context(
            date=datetime.date(2026, 12, 25),
            time=datetime.time(9, 0),
            receipt_name="My Daily Receipt",
        )
        groups: list[list[ESCPOSAction]] = []
        config: dict = {
            "layout": {"header": True, "separator": False, "cut_at_end": False},
        }
        result = apply_layout(groups, config, ctx)

        name_action = result[1]
        assert isinstance(name_action, TextAction)
        assert name_action.content == "My Daily Receipt\n"
