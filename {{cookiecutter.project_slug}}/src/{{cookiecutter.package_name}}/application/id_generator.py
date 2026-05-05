"""Identifier generator abstraction.

The domain never calls ``uuid.uuid4()`` directly: it depends on this
``IdGenerator``. Production uses ``Uuid4IdGenerator``; tests use
``SequentialIdGenerator`` to make outputs deterministic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class IdGenerator(ABC):
    """Abstract generator of unique identifiers."""

    @abstractmethod
    def new(self) -> UUID:
        """Return a new globally unique identifier."""
