"""User-related FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.infrastructure.container import (
    build_create_user_use_case,
    build_user_repository,
)
from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import (
    get_clock,
    get_id_generator,
    get_session,
)


def get_user_repository(session: AsyncSession = Depends(get_session)) -> UserRepository:
    """Inject ``SqlAlchemyUserRepository`` bound to the request session."""
    return build_user_repository(session)


def get_create_user_use_case(
    users: UserRepository = Depends(get_user_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
) -> CreateUserUseCase:
    """Inject the ``CreateUserUseCase`` wired with its collaborators."""
    return build_create_user_use_case(users=users, clock=clock, ids=ids)
