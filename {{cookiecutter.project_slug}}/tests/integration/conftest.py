"""Integration-layer conftest — testcontainers Postgres + clean session per test.

These fixtures are opt-in via ``pytest -m integration``. They require a
reachable Docker daemon: testcontainers spawns a fresh Postgres for the
test session, the schema is created once, each test runs inside its own
transaction that rolls back on exit so isolation is perfect without
paying a re-create cost.

When Docker is not reachable (typical inside a devcontainer that does
not mount the host docker.sock), the session skips integration tests
with a clear message instead of erroring. Run them on the host or in
CI (``ci-quality.yml::test-integration``).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from {{ cookiecutter.package_name }}.infrastructure.persistence.models import Base


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Spawn one Postgres 17 container for the whole test session.

    Skips integration tests cleanly when the Docker daemon is not
    reachable instead of letting testcontainers raise a noisy stack.
    The Docker SDK probes the daemon as soon as ``PostgresContainer``
    is instantiated, so we wrap both construction and ``start()``.
    """
    try:
        container = PostgresContainer("postgres:17")
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker daemon not reachable; integration tests skipped: {exc}")
    try:
        sync_url = container.get_connection_url()
        # testcontainers defaults to psycopg2; rewrite to asyncpg.
        yield sync_url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    finally:
        with contextlib.suppress(Exception):
            container.stop()


@pytest_asyncio.fixture(scope="session")
async def pg_engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Build the async engine and create the schema once per session."""
    engine = create_async_engine(pg_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a session inside a transaction that rolls back on exit.

    Mirrors the request-boundary semantics of ADR 0004: the test sees a
    real session with a real transaction; integrity errors surface as
    they would in production; the rollback at exit makes the next test
    start from a clean slate.
    """
    async with pg_engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(bind=conn, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            try:
                yield session
            finally:
                await trans.rollback()
