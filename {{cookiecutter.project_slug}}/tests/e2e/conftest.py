"""E2E-layer conftest — FastAPI ``TestClient`` wired to REAL adapters.

The ``app`` fixture overrides only what cannot be exercised end-to-end
without a self-hosted dependency:

* ``get_session`` → a real ``AsyncSession`` bound to the testcontainers
  Postgres engine, wrapped in an outer transaction that rolls back at
  teardown (per-test isolation, same savepoint pattern as integration).
* ``get_token_verifier`` → a real ``JwtTokenVerifier`` configured for
  ``HS256`` against a known test secret. Tests mint legitimate JWTs via
  the ``mint_token`` fixture; the verifier checks the signature like in
  production. We deliberately do not stand up Keycloak here — the bake-
  time devcontainer Keycloak is for human dev, not for the test suite.

The use case factory, repository factory, event bus factory, and every
other production-wired dependency are exercised as-is. The InMemory
Fakes from ``tests/fakes/`` stay reserved for unit tests.

``StubAsyncSession`` is still exported for the single readiness-probe
test that simulates a DB outage by raising ``OperationalError`` on
``execute``. That use is intentional: we want to test the failure mode,
not a real DB outage.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable

import jwt
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from {{ cookiecutter.package_name }}.infrastructure.auth.jwt_verifier import JwtTokenVerifier
from {{ cookiecutter.package_name }}.presentation.api.app import create_app
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import (
    get_token_verifier,
)
from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import get_session

E2E_JWT_SECRET = "test-secret-do-not-use-in-real-environments"


class StubAsyncSession:
    """Minimal ``AsyncSession``-shaped double for the DB-outage readiness test.

    Pass ``raises=`` to simulate the database being unreachable.
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises

    async def execute(self, _statement: object) -> None:
        if self._raises is not None:
            raise self._raises


@pytest.fixture
def stub_session() -> StubAsyncSession:
    return StubAsyncSession()


@pytest_asyncio.fixture
async def e2e_session_factory(
    pg_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A session factory bound to a connection wrapped in an outer transaction.

    Each request gets its own ``AsyncSession`` from this factory; the
    route handler's ``session.begin()`` runs inside a SAVEPOINT thanks
    to ``join_transaction_mode='create_savepoint'``. At teardown the
    outer transaction is rolled back, wiping every write the test
    performed — including those that were ``COMMIT``ed by routes.
    """
    async with pg_engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield factory
        finally:
            await trans.rollback()


@pytest.fixture
def jwt_verifier() -> JwtTokenVerifier:
    """Real HS256 verifier configured with the e2e test secret."""
    return JwtTokenVerifier(algorithm="HS256", secret=E2E_JWT_SECRET)


@pytest.fixture
def mint_token() -> Callable[..., str]:
    """Return a function that mints a real HS256 JWT for the e2e suite.

    Signature: ``mint_token(subject, *, email='user@example.com',
    name='User', roles=())``. Pass ``email=None`` or ``name=None`` to
    simulate IdP tokens that omit those profile claims (Azure guest
    accounts, custom scopes, …).
    """

    def _mint(
        subject: str,
        *,
        email: str | None = "user@example.com",
        name: str | None = "User",
        roles: tuple[str, ...] = (),
    ) -> str:
        now = int(time.time())
        payload: dict[str, object] = {"sub": subject, "iat": now, "exp": now + 3600}
        if email is not None:
            payload["email"] = email
        if name is not None:
            payload["name"] = name
        if roles:
            payload["roles"] = list(roles)
        return jwt.encode(payload, E2E_JWT_SECRET, algorithm="HS256")

    return _mint


@pytest.fixture
def app(
    e2e_session_factory: async_sessionmaker[AsyncSession],
    jwt_verifier: JwtTokenVerifier,
) -> FastAPI:
    """FastAPI app with the real production wiring, minus DB + JWT seams."""
    app = create_app()

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with e2e_session_factory() as session, session.begin():
            yield session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_token_verifier] = lambda: jwt_verifier
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """``httpx.AsyncClient`` calling the ASGI app on the test's event loop.

    Using the async client (instead of starlette's sync ``TestClient``,
    which runs the app in an anyio portal thread) keeps the request
    handler on the same event loop as the test fixtures. That matters
    because the session and connection in ``e2e_session_factory`` are
    loop-bound — calling them from another loop raises
    ``Future attached to a different loop``.

    The FastAPI lifespan is intentionally NOT entered: the production
    lifespan builds a real config-driven engine and instruments
    SQLAlchemy. Tests inject their own engine via the overrides above.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
