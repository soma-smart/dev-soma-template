"""``User`` entity."""

from __future__ import annotations

from datetime import datetime

from {{ cookiecutter.package_name }}.domain.entities.base import Entity
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class User(Entity[UserId]):
    """A registered user.

    Identity-based equality (``__eq__`` / ``__hash__``) is inherited from
    ``Entity[UserId]``. Mutations go through named methods, never direct
    attribute assignment.

    ``subject`` is the stable identifier issued by the IdP (the JWT
    ``sub`` claim). It is unique per user and used by
    ``EnsureUserExistsUseCase`` to map a JWT to its persisted ``User``
    row on every authenticated request. ``id`` remains an internal UUID
    so an IdP migration does not break references.
    """

    def __init__(
        self,
        *,
        id: UserId,
        subject: str,
        email: Email,
        name: str,
        created_at: datetime,
    ) -> None:
        self.id = id
        self.subject = subject
        self.email = email
        self.name = name
        self.created_at = created_at

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, subject={self.subject!r})"
