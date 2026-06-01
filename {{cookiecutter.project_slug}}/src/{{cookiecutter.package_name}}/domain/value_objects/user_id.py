"""``UserId`` value object wrapping a ``UUID``."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject


@dataclass(frozen=True, slots=True)
class UserId(ValueObject):
    """Strongly-typed wrapper around a user identifier UUID."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)
