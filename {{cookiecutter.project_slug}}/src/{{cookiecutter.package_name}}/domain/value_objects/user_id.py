"""``UserId`` value object wrapping a ``UUID``."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserId:
    """Strongly-typed wrapper around a user identifier UUID."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)
