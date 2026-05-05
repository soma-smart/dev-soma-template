"""Production binding for the ``Clock`` abstraction."""

from __future__ import annotations

from datetime import UTC, datetime

from {{ cookiecutter.package_name }}.application.clock import Clock


class SystemClock(Clock):
    """Clock backed by the operating system."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)
