"""Shared pytest configuration and fixtures.

The fixtures below are the canonical entry points for new tests:

* **Primitive fakes**: ``frozen_clock``, ``sequential_ids``, ``seeded_random``
  — deterministic doubles for the abstractions in ``application/``.
* **Repository fakes**: ``user_repository`` — in-memory ``UserRepository``
  acting as a Spy via its public ``users`` dict.
* **Use cases**: ``create_user_use_case`` — wired with the fakes above; ready
  to ``await create_user_use_case.execute(...)``.
* **App + client**: ``app`` (FastAPI with ``dependency_overrides`` set to the
  fakes) and ``client`` (synchronous ``TestClient``) — for e2e tests.

The integration layer adds a ``pg_session`` fixture (testcontainers Postgres)
in ``tests/integration/conftest.py``; it is opt-in via ``pytest -m integration``
and requires Docker on the host.

Adding a new feature should never require copying boilerplate from existing
tests — extend the fixture set instead.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.presentation.api.app import create_app
from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import get_session
from {{ cookiecutter.package_name }}.presentation.api.dependencies.users import get_create_user_use_case
from tests.fakes.clock import FrozenClock
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


# ─── Repository fakes ────────────────────────────────────────────────
@pytest.fixture
def user_repository() -> InMemoryUserRepository:
    return InMemoryUserRepository()


# ─── Use cases (composed) ────────────────────────────────────────────
@pytest.fixture
def create_user_use_case(
    user_repository: InMemoryUserRepository,
    frozen_clock: FrozenClock,
    sequential_ids: SequentialIdGenerator,
) -> CreateUserUseCase:
    return CreateUserUseCase(users=user_repository, clock=frozen_clock, ids=sequential_ids)


# ─── Stub session for health-check and DB-touching e2e tests ─────────
class StubAsyncSession:
    """Minimal AsyncSession-shaped double for tests that only exercise
    the ``execute(text("SELECT 1"))`` shape (e.g. readiness probe).

    Pass ``raises=`` to simulate a DB outage.
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises

    async def execute(self, _statement: object) -> None:
        if self._raises is not None:
            raise self._raises


@pytest.fixture
def stub_session() -> StubAsyncSession:
    return StubAsyncSession()


async def _stub_session_factory(stub: StubAsyncSession) -> AsyncIterator[AsyncSession]:
    yield stub  # type: ignore[misc]


# ─── FastAPI app + TestClient with fakes pre-wired ───────────────────
@pytest.fixture
def app(create_user_use_case: CreateUserUseCase, stub_session: StubAsyncSession) -> FastAPI:
    """FastAPI app with all production dependencies overridden by fakes.

    Tests that need an alternative wiring (e.g. simulate DB outage in
    ``/health/ready``) override the dependency themselves on the returned
    app instance.
    """
    app = create_app()
    app.dependency_overrides[get_create_user_use_case] = lambda: create_user_use_case

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async for s in _stub_session_factory(stub_session):
            yield s

    app.dependency_overrides[get_session] = _session_override
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Synchronous TestClient that does NOT enter the FastAPI lifespan.

    The production lifespan builds a real DB engine and instruments
    SQLAlchemy. Tests override ``get_session`` with a stub, so running the
    lifespan is unnecessary (and would require a real DB).
    """
    yield TestClient(app)
