"""Root conftest — primitives shared by all three test layers.

Two distinct families of fixtures live here:

* **In-memory Fakes** — `frozen_clock`, `sequential_ids`, `seeded_random`,
  `user_repository`, `event_bus`, `token_verifier`, `ensure_user_exists_use_case`.
  Used exclusively by `tests/unit/` (the use cases and the pure helpers). Fakes
  never leak into integration or e2e — those layers exercise the real adapters.
* **Testcontainers Postgres** — `pg_url` and `pg_engine` (session-scoped). Both
  `tests/integration/` and `tests/e2e/` consume them; the per-test transaction
  wrapping is provided by each layer's own conftest (`pg_session` for
  integration, `e2e_session_factory` for e2e).
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.postgres import PostgresContainer

from {{ cookiecutter.package_name }}.application.use_cases.ensure_user_exists import (
    EnsureUserExistsUseCase,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.models import Base

from tests.fakes.auth import FakeTokenVerifier
from tests.fakes.clock import FrozenClock
from tests.fakes.event_bus import InMemoryEventBus
from tests.fakes.id_generator import SequentialIdGenerator
from tests.fakes.random_source import SeededRandomSource
from tests.fakes.repositories.user import InMemoryUserRepository

DEFAULT_TEST_INSTANT = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


# ─── Primitive fakes ─────────────────────────────────────────────────
@pytest.fixture
def frozen_clock() -> FrozenClock:
    return FrozenClock(at=DEFAULT_TEST_INSTANT)


@pytest.fixture
def sequential_ids() -> SequentialIdGenerator:
    return SequentialIdGenerator(start=1)


@pytest.fixture
def seeded_random() -> SeededRandomSource:
    return SeededRandomSource(seed=0)


# ─── Repository fake (also acts as Spy via .users) ───────────────────
@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


# ─── Event bus fake (also acts as Spy via .published) ────────────────
@pytest.fixture
def event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()


# ─── Token verifier fake (also acts as Spy via .calls) ───────────────
@pytest.fixture
def token_verifier() -> FakeTokenVerifier:
    return FakeTokenVerifier()


# ─── Use case composed for unit tests ────────────────────────────────
@pytest.fixture
def ensure_user_exists_use_case(
    user_repository: InMemoryUserRepository,
    frozen_clock: FrozenClock,
    sequential_ids: SequentialIdGenerator,
    event_bus: InMemoryEventBus,
) -> EnsureUserExistsUseCase:
    return EnsureUserExistsUseCase(
        users=user_repository,
        clock=frozen_clock,
        ids=sequential_ids,
        events=event_bus,
    )


# ─── Testcontainers Postgres (shared by integration + e2e) ───────────
@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Spawn one Postgres 17 container for the whole test session.

    Skips integration and e2e tests cleanly when the Docker daemon is not
    reachable, instead of letting testcontainers raise a noisy stack.
    The Docker SDK probes the daemon as soon as ``PostgresContainer`` is
    instantiated, so we wrap both construction and ``start()``.
    """
    try:
        container = PostgresContainer("postgres:17")
        container.start()
    except Exception as exc:
        pytest.skip(f"Docker daemon not reachable; integration/e2e tests skipped: {exc}")
    try:
        sync_url = container.get_connection_url()
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
