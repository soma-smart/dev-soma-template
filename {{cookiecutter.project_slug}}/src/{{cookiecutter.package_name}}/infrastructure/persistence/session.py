"""Async SQLAlchemy engine and session factory.

The engine is configured from ``Settings`` and lives for the process lifetime.
Sessions are created per-request and closed by the FastAPI dependency.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings


def build_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine from the application settings."""
    return create_async_engine(
        settings.db_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build a session factory bound to the engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Open an async session and ensure it is closed on exit."""
    async with factory() as session:
        yield session
