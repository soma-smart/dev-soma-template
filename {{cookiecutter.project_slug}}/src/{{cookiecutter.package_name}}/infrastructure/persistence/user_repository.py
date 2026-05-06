"""SQLAlchemy implementation of ``UserRepository``."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.exceptions.user import UserAlreadyExistsError
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.user import UserModel


class SqlAlchemyUserRepository(UserRepository):
    """``UserRepository`` backed by SQLAlchemy 2.0 async."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        """Persist ``user``, raising ``UserAlreadyExistsError`` on uniqueness violation."""
        self._session.add(self._to_model(user))
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise UserAlreadyExistsError(email=str(user.email)) from exc

    async def find_by_email(self, email: Email) -> User | None:
        """Return the user matching ``email`` or ``None``."""
        stmt = select(UserModel).where(UserModel.email == str(email))
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(model) if model is not None else None

    async def find_by_id(self, id: UserId) -> User | None:
        """Return the user with the given identifier or ``None``."""
        model = await self._session.get(UserModel, id.value)
        return self._to_entity(model) if model is not None else None

    @staticmethod
    def _to_model(user: User) -> UserModel:
        return UserModel(
            id=user.id.value,
            email=str(user.email),
            name=user.name,
            created_at=user.created_at,
        )

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=UserId(model.id),
            email=Email(model.email),
            name=model.name,
            created_at=model.created_at,
        )
