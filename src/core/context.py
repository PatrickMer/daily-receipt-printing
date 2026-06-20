"""Shared context injected into every widget's render call."""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    """Immutable snapshot of execution context shared across all widgets."""

    date: datetime.date
    time: datetime.time
    receipt_name: str


def build_context(receipt_name: str) -> Context:
    """Create a Context with the current date and time."""
    now = datetime.datetime.now()
    return Context(
        date=now.date(),
        time=now.time(),
        receipt_name=receipt_name,
    )
