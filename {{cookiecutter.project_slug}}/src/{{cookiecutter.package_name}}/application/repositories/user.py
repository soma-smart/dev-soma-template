"""``UserRepository`` abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod

from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class UserRepository(ABC):
    """Persistence contract for the ``User`` aggregate."""

    @abstractmethod
    async def add(self, user: User) -> None:
        """Persist a new user. Raises if a user with the same email exists."""

    @abstractmethod
    async def find_by_email(self, email: Email) -> User | None:
        """Return the user matching ``email`` or ``None``."""

    @abstractmethod
    async def find_by_id(self, user_id: UserId) -> User | None:
        """Return the user with the given identifier or ``None``."""
