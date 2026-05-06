# 5. Domain events go through a SQL outbox

Date: 2026-05-06

## Status

Accepted.

## Context

When a use case writes an entity **and** wants to publish a domain event ("user signed up", "order placed"), the naive implementation calls the broker directly inside the use case. Two failure modes follow:

1. The DB write succeeds, the broker call fails → consumers never see the event, the system is silently inconsistent.
2. The broker call succeeds, the DB write rolls back → consumers see an event for an entity that does not exist.

A reliable distributed message bus (Kafka transactional, two-phase commit) sidesteps the issue but ties the project to one broker and adds operational complexity.

## Decision

We adopt the **transactional outbox** pattern:

* `application/event_bus.py::EventBus` is the abstract publisher used by use cases.
* `infrastructure/outbox.py::SqlOutboxEventBus` is the production binding. It writes a row to ``outbox_events`` using the same `AsyncSession` as the entity write — both rows hit the DB inside the request transaction (ADR 0004).
* `infrastructure/jobs/outbox_relay.py` is a separate process. It polls `published_at IS NULL`, calls a project-specific `_publish_event(...)` function, and marks the row published only after the broker durably acknowledges.

The entity write and the outbox write commit or roll back together. Consumers see the event **iff** the entity exists. Delivery is at-least-once; consumers must deduplicate on the row `id`.

## Consequences

**Positive**:
- Atomic event publication. No silent inconsistency.
- Broker-agnostic: the relay's `_publish_event` is the only project-specific piece. Switch from RabbitMQ to Kafka without touching `application/`.
- Observability for free: the table is the audit trail. A row stuck unpublished for more than N minutes is a paging condition.

**Negative**:
- Polling latency. The relay polls every second; events are not strictly real-time. Acceptable for most business events; if sub-second matters, replace polling with Postgres `LISTEN/NOTIFY` or a CDC stream.
- Two writes per event (the entity row + the outbox row) — negligible cost.
- A cleanup policy is required: published rows accumulate. Each project decides retention (truncate after 30d, archive to cold storage, etc.) — out of scope for the template.