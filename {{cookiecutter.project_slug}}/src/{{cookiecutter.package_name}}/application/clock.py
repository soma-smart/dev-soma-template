"""Clock abstraction.

The domain and the use cases never call ``datetime.now()`` directly because it
breaks test determinism (FIRST: tests must be Repeatable). They depend on this
``Clock`` and the production binding lives in ``infrastructure/clock.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Abstract source of the current wall-clock time."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current time as a TZ-aware UTC datetime."""
