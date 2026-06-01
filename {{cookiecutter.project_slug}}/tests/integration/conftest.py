"""Integration-layer conftest — clean session per test on testcontainers PG.

``pg_url`` and ``pg_engine`` (session-scoped) live in ``tests/conftest.py``
because both integration and e2e consume them. This module owns the
per-test transaction-wrapped session that integration tests use.

When Docker is not reachable, the root ``pg_url`` fixture skips with a
clear message; this conftest only adds the test-scoped session on top.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


@pytest_asyncio.fixture
async def pg_session(pg_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a transaction that rolls back on exit.

    Mirrors the request-boundary semantics of ADR 0004: the test sees a
    real session with a real transaction; integrity errors surface as
    they would in production; the rollback at exit makes the next test
    start from a clean slate.

    ``join_transaction_mode='create_savepoint'`` makes the session open
    a SAVEPOINT for its writes inside the fixture's outer transaction.
    An ``IntegrityError`` then rolls back only the savepoint, leaving
    the outer transaction alive so the teardown rollback works without
    raising ``SAWarning: transaction already deassociated from connection``.
    """
    async with pg_engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        async with factory() as session:
            try:
                yield session
            finally:
                await trans.rollback()
