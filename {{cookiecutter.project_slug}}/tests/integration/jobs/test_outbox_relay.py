"""Integration tests for the outbox relay roundtrip.

These tests prove the full chain works against a real Postgres:

    publish to SqlOutboxEventBus  →  outbox_events row committed
        →  _drain_once picks the row (status='pending', due)
        →  registered in-process handler runs
        →  status transitions to 'published' / 'poisoned' according to outcome

Pure GIVEN/WHEN/THEN, one edge case per test, no parametrize.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.infrastructure.jobs.backoff import MAX_ATTEMPTS
from {{ cookiecutter.package_name }}.infrastructure.jobs.handlers import _HANDLERS, handler
from {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay import _drain_once
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.outbox_event import OutboxEventModel


@pytest.fixture
def isolated_handlers() -> list[str]:
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


def _row(**overrides: object) -> OutboxEventModel:
    """Build an outbox row with sane defaults; tests override what they exercise."""
    base: dict[str, object] = {
        "id": uuid4(),
        "event_name": "user.created",
        "payload": {"user_id": str(UUID(int=42))},
        "created_at": datetime.now(tz=UTC),
    }
    base.update(overrides)
    return OutboxEventModel(**base)  # type: ignore[arg-type]


async def _refresh(pg_session: AsyncSession, row_id: UUID) -> OutboxEventModel:
    return (await pg_session.execute(select(OutboxEventModel).where(OutboxEventModel.id == row_id))).scalar_one()


@pytest.mark.integration
async def test_given_outbox_row_when_draining_then_drain_returns_one_published(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    pg_session.add(_row())
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 1


@pytest.mark.integration
async def test_given_outbox_row_when_draining_then_handler_receives_the_payload(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    pg_session.add(_row(payload={"user_id": str(UUID(int=42)), "email": "alice@example.com"}))
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)

    # THEN
    assert received == [{"user_id": str(UUID(int=42)), "email": "alice@example.com"}]


@pytest.mark.integration
async def test_given_outbox_row_when_draining_then_row_reaches_published_terminal_state(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    row = _row()
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)
    refreshed = await _refresh(pg_session, row.id)

    # THEN: terminal state is one observable (status + published_at marker + attempts)
    assert (refreshed.status, refreshed.published_at is not None, refreshed.attempts) == (
        "published", True, 0,
    )


@pytest.mark.integration
async def test_given_handler_raises_when_draining_then_drain_returns_zero(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def boom(payload: dict) -> None:
        raise RuntimeError("downstream outage")

    pg_session.add(_row())
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0


@pytest.mark.integration
async def test_given_handler_raises_when_draining_then_row_stays_pending_with_retry_metadata(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def boom(payload: dict) -> None:
        raise RuntimeError("downstream outage")

    row = _row()
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)
    refreshed = await _refresh(pg_session, row.id)

    # THEN: failure state is one observable (status + counters + retry markers)
    assert (
        refreshed.status,
        refreshed.published_at,
        refreshed.attempts,
        refreshed.last_attempt_at is not None,
        refreshed.next_attempt_at is not None,
    ) == ("pending", None, 1, True, True)


@pytest.mark.integration
async def test_given_handler_raises_when_draining_then_row_captures_the_error_message(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def boom(payload: dict) -> None:
        raise RuntimeError("downstream outage")

    row = _row()
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)
    refreshed = await _refresh(pg_session, row.id)

    # THEN
    assert "downstream outage" in (refreshed.last_error or "")


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
async def test_given_already_published_row_when_draining_then_drain_returns_zero(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    pg_session.add(_row(published_at=datetime.now(tz=UTC), status="published"))
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0


@pytest.mark.integration
async def test_given_already_published_row_when_draining_then_handler_is_not_invoked(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    pg_session.add(_row(published_at=datetime.now(tz=UTC), status="published"))
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)

    # THEN
    assert received == []


@pytest.mark.integration
async def test_given_row_with_future_next_attempt_when_draining_then_drain_returns_zero(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    pg_session.add(_row(
        attempts=2,
        last_attempt_at=datetime.now(tz=UTC),
        next_attempt_at=datetime.now(tz=UTC) + timedelta(minutes=5),
    ))
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0


@pytest.mark.integration
async def test_given_row_with_future_next_attempt_when_draining_then_handler_is_not_invoked(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    pg_session.add(_row(
        attempts=2,
        last_attempt_at=datetime.now(tz=UTC),
        next_attempt_at=datetime.now(tz=UTC) + timedelta(minutes=5),
    ))
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)

    # THEN
    assert received == []


@pytest.mark.integration
async def test_given_row_with_future_next_attempt_when_draining_then_row_is_unchanged(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    row = _row(
        attempts=2,
        last_attempt_at=datetime.now(tz=UTC),
        next_attempt_at=datetime.now(tz=UTC) + timedelta(minutes=5),
    )
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)
    refreshed = await _refresh(pg_session, row.id)

    # THEN: still pending, attempts counter not incremented
    assert (refreshed.status, refreshed.attempts) == ("pending", 2)


@pytest.mark.integration
async def test_given_row_with_due_next_attempt_when_draining_then_drain_returns_one(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    pg_session.add(_row(
        attempts=2,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(minutes=10),
        next_attempt_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    ))
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 1


@pytest.mark.integration
async def test_given_row_with_due_next_attempt_when_draining_then_handler_runs_once(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    pg_session.add(_row(
        attempts=2,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(minutes=10),
        next_attempt_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    ))
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)

    # THEN
    assert len(received) == 1


@pytest.mark.integration
async def test_given_row_with_due_next_attempt_when_draining_then_row_becomes_published(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    row = _row(
        attempts=2,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(minutes=10),
        next_attempt_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    )
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)
    refreshed = await _refresh(pg_session, row.id)

    # THEN
    assert refreshed.status == "published"


@pytest.mark.integration
async def test_given_row_reaches_max_attempts_when_handler_fails_then_drain_returns_zero(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def boom(payload: dict) -> None:
        raise RuntimeError("permanently broken")

    pg_session.add(_row(
        attempts=MAX_ATTEMPTS - 1,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(hours=1),
        next_attempt_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    ))
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0


@pytest.mark.integration
async def test_given_row_reaches_max_attempts_when_handler_fails_then_row_is_poisoned(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def boom(payload: dict) -> None:
        raise RuntimeError("permanently broken")

    row = _row(
        attempts=MAX_ATTEMPTS - 1,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(hours=1),
        next_attempt_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    )
    pg_session.add(row)
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)
    refreshed = await _refresh(pg_session, row.id)

    # THEN: poisoned terminal state (status + attempts at cap + no further retry)
    assert (refreshed.status, refreshed.attempts, refreshed.next_attempt_at) == (
        "poisoned", MAX_ATTEMPTS, None,
    )


@pytest.mark.integration
async def test_given_poisoned_row_when_draining_then_drain_returns_zero(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    @handler("user.created")
    async def noop(payload: dict) -> None:
        return None

    pg_session.add(_row(
        attempts=MAX_ATTEMPTS,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(hours=1),
        status="poisoned",
    ))
    await pg_session.flush()

    # WHEN
    published = await _drain_once(pg_session)

    # THEN
    assert published == 0


@pytest.mark.integration
async def test_given_poisoned_row_when_draining_then_handler_is_not_invoked(
    pg_session: AsyncSession,
    isolated_handlers: list[str],
) -> None:
    # GIVEN
    received: list[dict] = []

    @handler("user.created")
    async def collect(payload: dict) -> None:
        received.append(payload)

    pg_session.add(_row(
        attempts=MAX_ATTEMPTS,
        last_attempt_at=datetime.now(tz=UTC) - timedelta(hours=1),
        status="poisoned",
    ))
    await pg_session.flush()

    # WHEN
    await _drain_once(pg_session)

    # THEN
    assert received == []
