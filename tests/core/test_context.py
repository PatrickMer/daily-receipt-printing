"""Tests for core.context — Context dataclass and build_context factory."""

import datetime
from dataclasses import FrozenInstanceError

import pytest

from core.context import Context, build_context


class TestContextDirect:
    """Test direct construction of Context."""

    def test_basic_construction(self):
        d = datetime.date(2025, 6, 15)
        t = datetime.time(9, 30, 0)
        ctx = Context(date=d, time=t, receipt_name="morning")
        assert ctx.date == d
        assert ctx.time == t
        assert ctx.receipt_name == "morning"

    def test_frozen_cannot_set_date(self):
        ctx = Context(
            date=datetime.date.today(),
            time=datetime.time(12, 0),
            receipt_name="test",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.date = datetime.date(2000, 1, 1)  # type: ignore[misc]

    def test_frozen_cannot_set_time(self):
        ctx = Context(
            date=datetime.date.today(),
            time=datetime.time(12, 0),
            receipt_name="test",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.time = datetime.time(0, 0)  # type: ignore[misc]

    def test_frozen_cannot_set_receipt_name(self):
        ctx = Context(
            date=datetime.date.today(),
            time=datetime.time(12, 0),
            receipt_name="test",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.receipt_name = "other"  # type: ignore[misc]

    def test_equality(self):
        d = datetime.date(2025, 1, 1)
        t = datetime.time(8, 0, 0)
        ctx1 = Context(date=d, time=t, receipt_name="daily")
        ctx2 = Context(date=d, time=t, receipt_name="daily")
        assert ctx1 == ctx2

    def test_inequality(self):
        d = datetime.date(2025, 1, 1)
        t = datetime.time(8, 0, 0)
        ctx1 = Context(date=d, time=t, receipt_name="daily")
        ctx2 = Context(date=d, time=t, receipt_name="weekly")
        assert ctx1 != ctx2

    def test_missing_required_fields(self):
        with pytest.raises(TypeError):
            Context()  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            Context(date=datetime.date.today())  # type: ignore[call-arg]


class TestBuildContext:
    """Test the build_context factory function."""

    def test_returns_context_instance(self):
        ctx = build_context("my-receipt")
        assert isinstance(ctx, Context)

    def test_receipt_name_is_set(self):
        ctx = build_context("morning-news")
        assert ctx.receipt_name == "morning-news"

    def test_date_is_today(self):
        ctx = build_context("test")
        assert ctx.date == datetime.date.today()

    def test_time_is_close_to_now(self):
        before = datetime.datetime.now().time()
        ctx = build_context("test")
        after = datetime.datetime.now().time()
        # The context time should be between before and after
        assert before <= ctx.time <= after

    def test_date_type(self):
        ctx = build_context("test")
        assert isinstance(ctx.date, datetime.date)

    def test_time_type(self):
        ctx = build_context("test")
        assert isinstance(ctx.time, datetime.time)

    def test_empty_receipt_name(self):
        ctx = build_context("")
        assert ctx.receipt_name == ""
