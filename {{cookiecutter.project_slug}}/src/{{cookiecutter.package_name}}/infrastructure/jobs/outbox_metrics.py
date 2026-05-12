"""Prometheus metrics for the outbox relay.

Exposed by the relay process via ``prometheus_client.start_http_server`` —
see ``infrastructure/jobs/outbox_relay.run`` for the wiring. The gauges
are refreshed at the end of every drain tick by :func:`refresh_gauges`.

Alert thresholds (suggested defaults — wire in a PrometheusRule):

* ``outbox_events_pending > 1000`` for 5 minutes → producer-side backlog
* ``outbox_events_poisoned > 0`` → manual ops triage required
* ``outbox_oldest_pending_age_seconds > 300`` → relay or downstream lag
* ``rate(outbox_handler_failures_total[5m]) > 0.1`` → handler regression
"""

from __future__ import annotations

from datetime import UTC, datetime

from prometheus_client import Counter, Gauge
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.outbox_event import OutboxEventModel

outbox_events_pending = Gauge(
    "outbox_events_pending",
    "Number of outbox rows awaiting publication (status='pending').",
)
outbox_events_poisoned = Gauge(
    "outbox_events_poisoned",
    "Number of outbox rows that exhausted their retries (status='poisoned').",
)
outbox_oldest_pending_age_seconds = Gauge(
    "outbox_oldest_pending_age_seconds",
    "Age of the oldest pending outbox row in seconds — the primary lag signal.",
)
outbox_handler_failures_total = Counter(
    "outbox_handler_failures_total",
    "Cumulative count of handler failures, labelled by event_name.",
    ["event_name"],
)


async def refresh_gauges(session: AsyncSession) -> None:
    """Re-read the outbox stats and update the three gauges.

    Called once per drain tick. Three quick aggregate queries — cheap on
    indexed columns, fine to run every second.
    """
    pending_count = await session.scalar(
        select(func.count()).where(OutboxEventModel.status == "pending")
    )
    outbox_events_pending.set(int(pending_count or 0))

    poisoned_count = await session.scalar(
        select(func.count()).where(OutboxEventModel.status == "poisoned")
    )
    outbox_events_poisoned.set(int(poisoned_count or 0))

    oldest_created_at = await session.scalar(
        select(func.min(OutboxEventModel.created_at)).where(OutboxEventModel.status == "pending")
    )
    if oldest_created_at is None:
        outbox_oldest_pending_age_seconds.set(0)
    else:
        age = (datetime.now(tz=UTC) - oldest_created_at).total_seconds()
        outbox_oldest_pending_age_seconds.set(max(age, 0))
