"""Deterministic clock fake."""

from __future__ import annotations

from datetime import datetime

from {{ cookiecutter.package_name }}.application.clock import Clock


class FrozenClock(Clock):
    """A clock that always returns the same instant unless ``set(...)`` is called."""

    def __init__(self, at: datetime) -> None:
        self._now = at

    def now(self) -> datetime:
        return self._now

    def set(self, at: datetime) -> None:
        self._now = at
