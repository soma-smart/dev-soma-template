"""Integration tests for the outbox relay roundtrip.

These tests prove the full chain works against a real Postgres:

    publish to SqlOutboxEventBus  →  outbox_events row committed
        →  _drain_once picks the row
        →  registered in-process handler runs
        →  published_at is set on success / left NULL on handler failure

Pure GIVEN/WHEN/THEN, one edge case per test, no parametrize.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.infrastructure.jobs.handlers import _HANDLERS, handler
from {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay import _drain_once
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.outbox_event import OutboxEventModel


@pytest.fixture
def isolated_handlers() -> "list[str]":
    """Snapshot the handler registry, yield, restore.

    The integration tests register their own handlers; we restore the
    original registry afterwards so subsequent tests are not polluted.
    """
    saved = {k: list(v) for k, v in _HANDLERS.items()}
    _HANDLERS.clear()
    yield list(saved.keys())
    _HANDLERS.clear()
    for k, v in saved.items():
        _HANDLERS[k] = v


@pytest.mark.integration
async def test_given_outbox_row_when_draining_then_handler_runs_and_row_is_marked_published(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    row = OutboxEventModel(
        id=uuid4(),
        event_name="user.created",
        payload={"user_id": str(UUID(int=42)), "email": "alice@example.com"},
        created_at=datetime.now(tz=UTC),
    )
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 1
    assert received == [{"user_id": str(UUID(int=42)), "email": "alice@example.com"}]
    result = await pg_session.execute(select(OutboxEventModel).where(OutboxEventModel.id == row.id))
    refreshed = result.scalar_one()
    assert refreshed.published_at is not None


@pytest.mark.integration
async def test_given_handler_raises_when_draining_then_row_stays_unpublished(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def boom(payload: dict) -> None:  # noqa: ARG001
        raise RuntimeError("downstream outage")

    row = OutboxEventModel(
        id=uuid4(),
        event_name="user.created",
        payload={"user_id": str(UUID(int=42))},
        created_at=datetime.now(tz=UTC),
    )
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0
    result = await pg_session.execute(select(OutboxEventModel).where(OutboxEventModel.id == row.id))
    refreshed = result.scalar_one()
    assert refreshed.published_at is None


@pytest.mark.integration
async def test_given_no_pending_rows_when_draining_then_returns_zero(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN: no rows inserted

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0


@pytest.mark.integration
async def test_given_already_published_row_when_draining_then_does_not_replay(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    row = OutboxEventModel(
        id=uuid4(),
        event_name="user.created",
        payload={"user_id": str(UUID(int=42))},
        created_at=datetime.now(tz=UTC),
        published_at=datetime.now(tz=UTC),
    )
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0
    assert received == []
