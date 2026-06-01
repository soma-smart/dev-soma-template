"""``UserRepository`` protocol."""

from __future__ import annotations

from typing import Protocol

from {{ cookiecutter.package_name }}.application.repositories.base import Repository
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class UserRepository(Repository[User, UserId], Protocol):
    """Persistence contract for the ``User`` entity.

    ``add`` and ``find_by_id`` are inherited from ``Repository``. The
    user-specific ``find_by_subject`` is the primary lookup path:
    ``EnsureUserExistsUseCase`` calls it on every authenticated request
    to map the JWT subject to the internal ``User`` row.
    """

    async def find_by_subject(self, subject: str) -> User | None:
        """Return the user whose IdP ``subject`` matches, or ``None``.

        ``subject`` is the value of the JWT ``sub`` claim — opaque,
        stable, and unique across users (a UNIQUE constraint enforces
        this at the DB level). Used by ``EnsureUserExistsUseCase`` to
        map a verified JWT to its persisted ``User`` row.
        """
        ...

    async def find_by_email(self, email: Email) -> User | None:
        """Return the user matching ``email`` or ``None``.

        Kept as a secondary lookup for admin / migration flows. Not used
        by the SSO auto-provisioning path — that one uses ``subject``.
        """
        ...
