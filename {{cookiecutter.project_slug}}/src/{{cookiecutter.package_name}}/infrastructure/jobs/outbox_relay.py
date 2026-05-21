"""Outbox relay — forwards pending outbox rows to in-process handlers.

Run as a separate process or container alongside the API:

    uv run python -m {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay

The relay dispatches each due ``pending`` row to the handler registry in
:mod:`{{ cookiecutter.package_name }}.infrastructure.jobs.handlers`. The whole
template runs handlers IN-PROCESS: no external broker is wired by default
(ADR 0005). When the project goes multi-service, replace the body of
``handlers.dispatch`` with a real broker publish call — the relay does not
change.

Guarantees:

* **At-least-once**: a row transitions to ``status='published'`` only after
  every handler returns successfully. A handler exception increments
  ``attempts`` and schedules a retry per :mod:`backoff`.
* **Dead-letter**: after ``MAX_ATTEMPTS`` failures the row transitions to
  ``status='poisoned'`` and is no longer polled — the
  ``outbox_events_poisoned`` gauge fires the alert.
* **Multi-replica safe**: ``SELECT ... FOR UPDATE SKIP LOCKED`` lets
  multiple relay replicas process disjoint batches without dedup.
* **Idempotency on the handler side**: handlers MUST tolerate replay; an
  earlier successful side-effect can re-occur on a relay crash before
  ``commit()`` set the status.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from datetime import UTC, datetime
from typing import Any

import structlog
from prometheus_client import start_http_server
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.infrastructure.config.settings import get_settings
from {{ cookiecutter.package_name }}.infrastructure.container import build_database
from {{ cookiecutter.package_name }}.infrastructure.jobs import (
    event_handlers,  # noqa: F401 — import side-effect: register decorators
)
from {{ cookiecutter.package_name }}.infrastructure.jobs.backoff import MAX_ATTEMPTS, compute_next_attempt
from {{ cookiecutter.package_name }}.infrastructure.jobs.handlers import dispatch
from {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_metrics import (
    outbox_handler_failures_total,
    refresh_gauges,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.outbox_event import OutboxEventModel

logger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 100
_LAST_ERROR_MAX_LENGTH = 500


async def _publish_event(event_name: str, payload: dict[str, Any]) -> None:
    """Forward one event to every handler registered for ``event_name``.

    Raises if any handler raises. This function is the swap point for wiring
    a real broker: replace ``await dispatch(...)`` with
    ``await broker.publish(...)``.
    """
    await dispatch(event_name, payload)


async def _drain_once(session: AsyncSession) -> int:
    """Process one batch. Returns the number of events successfully published.

    Locks the picked rows via ``SELECT FOR UPDATE SKIP LOCKED`` so concurrent
    relays do not double-process. On Postgres the locks are released by the
    ``commit()`` at the end. On SQLite (used only by unit tests; integration
    runs on real Postgres) the clause is silently ignored — single-writer
    semantics suffice in that case.
    """
    now = datetime.now(tz=UTC)
    pending = await session.execute(
        select(OutboxEventModel)
        .where(
            OutboxEventModel.status == "pending",
            or_(
                OutboxEventModel.next_attempt_at.is_(None),
                OutboxEventModel.next_attempt_at <= now,
            ),
        )
        .order_by(OutboxEventModel.created_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    rows = list(pending.scalars())
    published = 0
    for row in rows:
        try:
            await _publish_event(row.event_name, row.payload)
        except Exception as exc:
            _record_failure(row, exc, now=datetime.now(tz=UTC))
            outbox_handler_failures_total.labels(event_name=row.event_name).inc()
            logger.warning(
                "outbox.publish_failed",
                event_id=str(row.id),
                event_name=row.event_name,
                attempts=row.attempts,
                status=row.status,
            )
            continue
        _record_success(row, now=datetime.now(tz=UTC))
        published += 1

    await session.commit()
    await refresh_gauges(session)
    return published


def _record_success(row: OutboxEventModel, *, now: datetime) -> None:
    row.status = "published"
    row.published_at = now
    row.last_attempt_at = now


def _record_failure(row: OutboxEventModel, exc: BaseException, *, now: datetime) -> None:
    row.attempts += 1
    row.last_attempt_at = now
    row.last_error = repr(exc)[:_LAST_ERROR_MAX_LENGTH]
    if row.attempts >= MAX_ATTEMPTS:
        row.status = "poisoned"
        row.next_attempt_at = None
    else:
        row.next_attempt_at = now + compute_next_attempt(row.attempts)


async def run() -> None:
    """Polling loop. Stops cleanly on SIGTERM/SIGINT."""
    stop = asyncio.Event()

    def _handle_signal() -> None:
        logger.info("outbox.shutdown_signal")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    settings = get_settings()
    engine, factory = build_database(settings)
    start_http_server(settings.relay_metrics_port)
    logger.info(
        "outbox.relay_started",
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
        metrics_port=settings.relay_metrics_port,
    )

    try:
        while not stop.is_set():
            async with factory() as session:
                published = await _drain_once(session)
            if published == 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=POLL_INTERVAL_SECONDS)
    finally:
        await engine.dispose()
        logger.info("outbox.relay_stopped")


if __name__ == "__main__":
    asyncio.run(run())
