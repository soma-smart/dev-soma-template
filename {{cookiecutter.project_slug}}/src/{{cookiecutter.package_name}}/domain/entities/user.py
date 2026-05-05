"""``User`` entity."""

from __future__ import annotations

from datetime import datetime

from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class User:
    """A registered user.

    Identity-based equality on ``id``. Mutations that change observable state
    must go through named methods, never direct attribute assignment.
    """

    def __init__(self, *, id: UserId, email: Email, name: str, created_at: datetime) -> None:
        self.id = id
        self.email = email
        self.name = name
        self.created_at = created_at

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"
