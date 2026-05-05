"""Dependency injection container.

Pure factory functions (no framework). FastAPI ``Depends`` wraps these in
``presentation/api/dependencies/``. CLI entry points and workers can call
these directly.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.random_source import RandomSource
from {{ cookiecutter.package_name }}.application.repositories.user import UserRepository
from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.infrastructure.clock import SystemClock
from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings
from {{ cookiecutter.package_name }}.infrastructure.id_generator import Uuid4IdGenerator
from {{ cookiecutter.package_name }}.infrastructure.persistence.session import (
    build_engine,
    build_session_factory,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.user_repository import SqlAlchemyUserRepository
from {{ cookiecutter.package_name }}.infrastructure.random_source import SystemRandomSource


def build_clock() -> Clock:
    """Return the production ``Clock`` binding."""
    return SystemClock()


def build_id_generator() -> IdGenerator:
    """Return the production ``IdGenerator`` binding."""
    return Uuid4IdGenerator()


def build_random_source() -> RandomSource:
    """Return the production ``RandomSource`` binding."""
    return SystemRandomSource()


def build_database(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Build the engine and session factory from the application settings."""
    engine = build_engine(settings)
    return engine, build_session_factory(engine)


def build_user_repository(session: AsyncSession) -> UserRepository:
    """Build the SQLAlchemy-backed ``UserRepository`` for a given session."""
    return SqlAlchemyUserRepository(session)


def build_create_user_use_case(
    *,
    users: UserRepository,
    clock: Clock,
    ids: IdGenerator,
) -> CreateUserUseCase:
    """Construct ``CreateUserUseCase`` from its collaborators."""
    return CreateUserUseCase(users=users, clock=clock, ids=ids)
