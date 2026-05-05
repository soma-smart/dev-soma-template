"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
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
    return build_clock()


def get_id_generator() -> IdGenerator:
    return build_id_generator()


def get_random_source() -> RandomSource:
    return build_random_source()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Open an async session for the lifetime of the request."""
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
