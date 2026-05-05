"""DTOs for user use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateUserInput:
    """Input DTO for ``CreateUserUseCase``."""

    email: str
    name: str


@dataclass(frozen=True, slots=True)
class CreateUserOutput:
    """Output DTO for ``CreateUserUseCase``."""

    id: UUID
    email: str
    name: str
    created_at: datetime
