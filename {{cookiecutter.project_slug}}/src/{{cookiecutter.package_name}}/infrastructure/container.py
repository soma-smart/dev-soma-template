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
from {{ cookiecutter.package_name }}.infrastructure.clock import SystemClock
from {{ cookiecutter.package_name }}.infrastructure.id_generator import Uuid4IdGenerator
from {{ cookiecutter.package_name }}.infrastructure.persistence.session import (
    build_engine,
    build_session_factory,
)
from {{ cookiecutter.package_name }}.infrastructure.random_source import SystemRandomSource
from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings


def build_clock() -> Clock:
    return SystemClock()


def build_id_generator() -> IdGenerator:
    return Uuid4IdGenerator()


def build_random_source() -> RandomSource:
    return SystemRandomSource()


def build_database(settings: Settings) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = build_engine(settings)
    return engine, build_session_factory(engine)
