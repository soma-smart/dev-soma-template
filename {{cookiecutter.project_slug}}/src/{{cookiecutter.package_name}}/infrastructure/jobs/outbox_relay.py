"""Outbox relay — forwards pending outbox rows to the configured broker.

Run as a separate process or container alongside the API:

    uv run python -m {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay

The default ``_publish_event`` is a stub that logs and marks the row as
published. Replace it with your broker integration (Kafka, SQS, Pub/Sub,
RabbitMQ, ...). Requirements for any replacement:

* **At-least-once**: only mark ``published_at`` after the broker has
  durably acknowledged the message.
* **Idempotency on the consumer side**: events carry a unique ``id``; the
  consumer must deduplicate.
* **Backoff + alerting**: a row stuck unpublished for more than N minutes
  is a paging condition.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.infrastructure.config.settings import get_settings
from {{ cookiecutter.package_name }}.infrastructure.container import build_database
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.outbox_event import OutboxEventModel

logger = structlog.get_logger(__name__)

POLL_INTERVAL_SECONDS = 1.0
BATCH_SIZE = 100


async def _publish_event(event_name: str, payload: dict[str, Any]) -> None:
    """STUB: replace with the actual broker publish call.

    Must raise on failure so the row is NOT marked as published. The
    relay loop catches and logs the exception, then retries on the next
    tick.
    """
    logger.info("outbox.publish_stub", event_name=event_name, payload=payload)


async def _drain_once(session: AsyncSession) -> int:
    """Process one batch. Returns the number of events published this tick."""
    pending = await session.execute(
        select(OutboxEventModel)
        .where(OutboxEventModel.published_at.is_(None))
        .order_by(OutboxEventModel.created_at)
        .limit(BATCH_SIZE)
    )
    rows = list(pending.scalars())
    published = 0
    for row in rows:
        try:
            await _publish_event(row.event_name, row.payload)
        except Exception:
            logger.exception("outbox.publish_failed", event_id=str(row.id), event_name=row.event_name)
            continue
        await session.execute(
            update(OutboxEventModel).where(OutboxEventModel.id == row.id).values(published_at=datetime.now(tz=UTC))
        )
        published += 1
    if rows:
        await session.commit()
    return published


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
    logger.info("outbox.relay_started", poll_interval_seconds=POLL_INTERVAL_SECONDS)

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
