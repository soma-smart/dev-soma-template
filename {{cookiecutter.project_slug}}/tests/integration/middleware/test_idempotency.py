"""Integration tests for :class:`IdempotencyMiddleware`.

These tests wire a tiny FastAPI app whose ``state.session_factory`` points
at the testcontainers Postgres engine; both the middleware AND the test
setup use that same factory so the middleware's writes are immediately
visible to the assertions. We deliberately don't use the
``join_transaction_mode='create_savepoint'`` ``pg_session`` fixture here:
the middleware opens its own real transaction, which is incompatible with
the savepoint trick.

We also drive the app with ``httpx.AsyncClient`` + ``ASGITransport``
rather than ``TestClient``: the latter spawns an anyio BlockingPortal
that runs the request in a separate event loop, which breaks the
session-scoped asyncpg engine's connection pool.

A ``_clean`` autouse fixture wipes ``idempotency_records`` around each
test so keys never leak.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.idempotency_record import IdempotencyRecord
from {{ cookiecutter.package_name }}.presentation.api.middleware.idempotency import IdempotencyMiddleware


@pytest.fixture
def session_factory(pg_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A session factory bound to the testcontainers engine (real commits)."""
    return async_sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def _clean(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    """Wipe idempotency_records around each test so keys never leak."""
    async with session_factory() as s:
        await s.execute(delete(IdempotencyRecord))
        await s.commit()
    yield
    async with session_factory() as s:
        await s.execute(delete(IdempotencyRecord))
        await s.commit()


@pytest.fixture
def calls() -> list[str]:
    return []


@pytest.fixture
def app(session_factory: async_sessionmaker[AsyncSession], calls: list[str]) -> FastAPI:
    """Tiny FastAPI app with the middleware wired and two counter endpoints."""
    app = FastAPI()
    app.state.session_factory = session_factory
    app.add_middleware(IdempotencyMiddleware, methods=frozenset({"POST"}), ttl_seconds=3600)

    @app.post("/echo")
    async def echo(payload: dict) -> dict:
        calls.append("echo")
        return {"received": payload, "call_number": len(calls)}

    @app.post("/other")
    async def other() -> dict:
        calls.append("other")
        return {"endpoint": "other"}

    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _row_for(session_factory: async_sessionmaker[AsyncSession], key: str) -> IdempotencyRecord | None:
    async with session_factory() as s:
        return await s.scalar(select(IdempotencyRecord).where(IdempotencyRecord.key == key))


async def _insert(session_factory: async_sessionmaker[AsyncSession], row: IdempotencyRecord) -> None:
    async with session_factory() as s:
        s.add(row)
        await s.commit()


@pytest.mark.integration
async def test_given_no_header_when_posting_then_handler_runs_and_no_row_is_persisted(
    client: AsyncClient,
    calls: list[str],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # GIVEN: no Idempotency-Key header

    # WHEN
    response = await client.post("/echo", json={"value": 1})

    # THEN
    assert response.status_code == 200
    assert response.json()["call_number"] == 1
    assert calls == ["echo"]
    async with session_factory() as s:
        count = await s.scalar(select(func.count()).select_from(IdempotencyRecord))
    assert count == 0


@pytest.mark.integration
async def test_given_first_request_when_retried_with_same_key_then_handler_runs_once(
    client: AsyncClient,
    calls: list[str],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # GIVEN
    key = str(uuid4())

    # WHEN
    first = await client.post("/echo", json={"value": 1}, headers={"Idempotency-Key": key})
    second = await client.post("/echo", json={"value": 1}, headers={"Idempotency-Key": key})

    # THEN
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert calls == ["echo"]  # handler ran exactly once
    row = await _row_for(session_factory, key)
    assert row is not None
    assert row.status == "completed"
    assert row.response_status == 200


@pytest.mark.integration
async def test_given_completed_key_when_retried_on_different_path_then_returns_422(
    client: AsyncClient,
    calls: list[str],
) -> None:
    # GIVEN
    key = str(uuid4())
    first = await client.post("/echo", json={"value": 1}, headers={"Idempotency-Key": key})
    assert first.status_code == 200

    # WHEN
    second = await client.post("/other", headers={"Idempotency-Key": key})

    # THEN
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "IDEMPOTENCY_KEY_MISMATCH"
    assert calls == ["echo"]


@pytest.mark.integration
async def test_given_in_progress_key_when_retried_then_returns_409(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # GIVEN: a row sitting in 'in_progress' (a previous attempt crashed
    # between INSERT and UPDATE; the row stays in_progress until TTL).
    key = str(uuid4())
    now = datetime.now(tz=UTC)
    await _insert(
        session_factory,
        IdempotencyRecord(
            key=key,
            status="in_progress",
            method="POST",
            path="/echo",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        ),
    )

    # WHEN
    response = await client.post("/echo", json={"value": 1}, headers={"Idempotency-Key": key})

    # THEN
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_IN_PROGRESS"


@pytest.mark.integration
async def test_given_expired_key_when_retried_then_handler_runs_again(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    calls: list[str],
) -> None:
    # GIVEN: a completed row whose TTL has already elapsed
    key = str(uuid4())
    now = datetime.now(tz=UTC)
    await _insert(
        session_factory,
        IdempotencyRecord(
            key=key,
            status="completed",
            method="POST",
            path="/echo",
            response_status=200,
            response_body={"old": True},
            response_headers={},
            created_at=now - timedelta(hours=25),
            completed_at=now - timedelta(hours=25),
            expires_at=now - timedelta(seconds=1),
        ),
    )

    # WHEN
    response = await client.post("/echo", json={"value": 1}, headers={"Idempotency-Key": key})

    # THEN
    assert response.status_code == 200
    assert "old" not in response.json()
    assert calls == ["echo"]
    row = await _row_for(session_factory, key)
    assert row is not None
    assert row.status == "completed"
    assert row.response_body == response.json()


@pytest.mark.integration
async def test_given_get_request_with_header_when_called_then_handler_always_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # GIVEN: middleware configured for POST only; a GET endpoint hit twice with the same key
    counter = {"hits": 0}
    app = FastAPI()
    app.state.session_factory = session_factory
    app.add_middleware(IdempotencyMiddleware, methods=frozenset({"POST"}), ttl_seconds=3600)

    @app.get("/snapshot")
    async def snapshot() -> dict:
        counter["hits"] += 1
        return {"hits": counter["hits"]}

    key = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # WHEN
        first = await client.get("/snapshot", headers={"Idempotency-Key": key})
        second = await client.get("/snapshot", headers={"Idempotency-Key": key})

    # THEN: GET is not in the configured set, both runs hit the handler
    assert first.json() == {"hits": 1}
    assert second.json() == {"hits": 2}
    row = await _row_for(session_factory, key)
    assert row is None
