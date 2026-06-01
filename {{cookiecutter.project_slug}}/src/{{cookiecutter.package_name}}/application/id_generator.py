"""Identifier generator abstraction.

The domain never calls ``uuid.uuid4()`` directly: it depends on this
``IdGenerator`` protocol. Production uses ``Uuid4IdGenerator``; tests use
``SequentialIdGenerator`` to make outputs deterministic.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class IdGenerator(Protocol):
    """Structural contract for a generator of unique identifiers."""

    def new(self) -> UUID:
        """Return a new globally unique identifier."""
        ...
