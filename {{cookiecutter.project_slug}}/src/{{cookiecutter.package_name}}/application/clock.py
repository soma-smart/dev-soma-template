"""Clock abstraction.

The domain and the use cases never call ``datetime.now()`` directly because it
breaks test determinism (FIRST: tests must be Repeatable). They depend on this
``Clock`` protocol; the production binding lives in ``infrastructure/clock.py``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Structural contract for a source of the current wall-clock time."""

    def now(self) -> datetime:
        """Return the current time as a TZ-aware UTC datetime."""
        ...
