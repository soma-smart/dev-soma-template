"""``UserRepository`` protocol."""

from __future__ import annotations

from typing import Protocol

from {{ cookiecutter.package_name }}.application.repositories.base import Repository
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class UserRepository(Repository[User, UserId], Protocol):
    """Persistence contract for the ``User`` entity.

    ``add`` and ``find_by_id`` are inherited from ``Repository``. Implementations
    provide those plus the user-specific ``find_by_email``.
    """

    async def find_by_email(self, email: Email) -> User | None:
        """Return the user matching ``email`` or ``None``."""
        ...
