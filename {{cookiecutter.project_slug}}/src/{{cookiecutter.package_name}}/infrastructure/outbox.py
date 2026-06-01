"""SQL-backed outbox event bus.

Persists events to the ``outbox_events`` table inside the request
transaction. A relay worker (see ``infrastructure/jobs/outbox_relay.py``)
forwards rows to the configured broker out-of-band, providing at-least-once
delivery semantics aligned with the entity write.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.application.event_bus import EventBus
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.outbox_event import OutboxEventModel


class SqlOutboxEventBus(EventBus):
    """``EventBus`` that enqueues events into the SQL outbox.

    The bus shares the request session, so the row hits the DB inside the
    same transaction as the entity write — no orphan events, no events
    lost when the write fails.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        """Append an outbox row to the current transaction."""
        self._session.add(
            OutboxEventModel(
                id=uuid4(),
                event_name=event_name,
                payload=payload,
                created_at=datetime.now(tz=UTC),
            )
        )


class NullEventBus(EventBus):
    """Default ``EventBus`` for projects that do not publish events yet."""

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:  # noqa: ARG002
        """Drop the event. The signature stays compatible for future swap."""
        return
