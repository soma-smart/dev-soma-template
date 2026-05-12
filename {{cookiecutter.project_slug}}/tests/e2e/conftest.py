"""E2E-layer conftest — FastAPI ``TestClient`` with Fakes pre-wired.

The ``app`` fixture overrides the production dependencies for the User
use case and the database session with the Fakes from the root
conftest. Tests that need a different wiring (e.g. simulate a DB outage
on ``/health/ready``) override the dependency on the returned app
instance directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.presentation.api.app import create_app
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import get_token_verifier
from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import get_session
from {{ cookiecutter.package_name }}.presentation.api.dependencies.users import get_create_user_use_case
from tests.fakes.auth import FakeTokenVerifier


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


@pytest.fixture
def app(
    create_user_use_case: CreateUserUseCase,
    stub_session: StubAsyncSession,
    token_verifier: FakeTokenVerifier,
) -> FastAPI:
    """FastAPI app with the User use case, DB session, and token verifier overridden by Fakes."""
    app = create_app()
    app.dependency_overrides[get_create_user_use_case] = lambda: create_user_use_case
    app.dependency_overrides[get_token_verifier] = lambda: token_verifier

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield stub_session  # type: ignore[misc]

    app.dependency_overrides[get_session] = _session_override
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Synchronous TestClient that does NOT enter the FastAPI lifespan.

    The production lifespan builds a real DB engine and instruments
    SQLAlchemy. Tests override ``get_session`` with a stub, so running
    the lifespan is unnecessary (and would require a real DB).
    """
    yield TestClient(app)
