"""``UserRepository`` abstraction."""

from __future__ import annotations

from abc import abstractmethod

from {{ cookiecutter.package_name }}.application.repositories.base import Repository
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class UserRepository(Repository[User, UserId]):
    """Persistence contract for the ``User`` entity.

    ``add`` and ``find_by_id`` are inherited from ``Repository``. Subclasses
    need only implement them plus the user-specific ``find_by_email``.
    """

    @abstractmethod
    async def find_by_email(self, email: Email) -> User | None:
        """Return the user matching ``email`` or ``None``."""
