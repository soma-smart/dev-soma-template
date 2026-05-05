"""Random source abstraction.

The domain never calls ``random.*`` directly. Tests inject a seeded source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class RandomSource(ABC):
    """Abstract source of randomness."""

    @abstractmethod
    def next_int(self, low: int, high: int) -> int:
        """Return an integer in the closed interval ``[low, high]``."""

    @abstractmethod
    def next_float(self) -> float:
        """Return a float in ``[0.0, 1.0)``."""
