"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.clock import Clock
from {{ cookiecutter.package_name }}.application.id_generator import IdGenerator
from {{ cookiecutter.package_name }}.application.random_source import RandomSource
from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings, get_settings
from {{ cookiecutter.package_name }}.infrastructure.container import (
    build_clock,
    build_id_generator,
    build_random_source,
)


def get_settings_dependency() -> Settings:
    """Inject the cached ``Settings`` singleton."""
    return get_settings()


def get_clock() -> Clock:
    """Inject the production ``Clock``."""
    return build_clock()


def get_id_generator() -> IdGenerator:
    """Inject the production ``IdGenerator``."""
    return build_id_generator()


def get_random_source() -> RandomSource:
    """Inject the production ``RandomSource``."""
    return build_random_source()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Open an async session AND a transaction for the lifetime of the request.

    The transaction commits when the route handler returns successfully and
    rolls back if any exception bubbles up — including ``DomainError``,
    which is intentional: the use case did not satisfy its post-condition,
    so partial writes must not leak. See ADR 0004.
    """
    factory = request.app.state.session_factory
    async with factory() as session, session.begin():
        yield session
