"""In-memory ``UserRepository`` for unit tests."""

from __future__ import annotations

from collections.abc import Iterable

from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.exceptions.user import UserAlreadyExistsError
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


class InMemoryUserRepository(UserRepository):
    """Dict-backed user repository.

    Tests can also inspect ``self.users`` to assert side-effects, exactly the
    role a Spy would play, without pulling in ``unittest.mock``.
    """

    def __init__(self, seed: Iterable[User] = ()) -> None:
        self.users: dict[UserId, User] = {u.id: u for u in seed}

    async def add(self, user: User) -> None:
        if any(u.email == user.email for u in self.users.values()):
            raise UserAlreadyExistsError(email=str(user.email))
        self.users[user.id] = user

    async def find_by_email(self, email: Email) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def find_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)
