---
name: transactions-and-events
description: How commit/rollback works at the request boundary (ADR 0004) and how use cases publish domain events through the SQL outbox + in-process handler registry (ADR 0005). The single source of truth for atomicity and event flow in this codebase.
when_to_use: A use case writes more than one entity; a use case raises errors after partial writes; a use case needs to publish a domain event; adding a handler for an event; editing infrastructure/outbox.py, infrastructure/jobs/outbox_relay.py, infrastructure/jobs/handlers.py or event_handlers.py.
---

# Transactions and events

## Transaction boundary — one HTTP request = one transaction (ADR 0004)

`presentation/api/dependencies/common.py::get_session` opens **both** an `AsyncSession` and an outer transaction:

```python
async with factory() as session, session.begin():
    yield session
```

The transaction **commits** when the route handler returns successfully, and **rolls back** on any raised exception — including `DomainError`. That is intentional: a use case that has done a partial write and then raises `UserAlreadyExistsError` leaves the database untouched, so the surface state matches the surface error.

### What this implies for repositories

Call `flush()`, **never** `commit()`. Flush surfaces integrity errors immediately so the repo can translate them into `DomainError`. Commit is the dependency wrapper's job.

The shipped `SqlAlchemyUserRepository.add()` is the canonical example:

```python
async def add(self, user: User, /) -> None:
    self._session.add(self._to_model(user))
    try:
        await self._session.flush()
    except IntegrityError as exc:
        raise UserAlreadyExistsError(email=str(user.email)) from exc
```

### What this implies for use cases

* **No `session.begin()`, no `commit()`, no `rollback()` in `application/`.** The use case never sees transactions.
* **Multiple writes are atomic by default.** Two `repo.add(...)` calls in the same use case commit together or roll back together.
* **Outbox events ride the same transaction.** Calling `events.publish(...)` writes to `outbox_events` via the same session, so the entity write and the event row are atomic. No orphan events, no events lost on rollback.
* **`_instrumented` cooperates** — when the use case raises a `DomainError`, the wrapper logs it at `WARNING` (with `code` + `context`) and re-raises; the dependency wrapper at the boundary then rolls back. No partial state survives.

### Sub-transactional checkpoints (rare)

If you genuinely need to let a sub-step fail without aborting the outer transaction, use a savepoint:

```python
async with session.begin_nested():
    ...   # this block can fail without aborting the outer transaction
```

The integration-test `pg_session` fixture uses the same mechanism via `join_transaction_mode="create_savepoint"` — read it if you want a worked example.

## Publishing a domain event (ADR 0005)

Use cases publish through the `EventBus` protocol. The production binding is `SqlOutboxEventBus`: it writes a row to `outbox_events` **inside the request transaction**. A separate `outbox_relay` worker polls unpublished rows and dispatches them to **in-process handlers** (no external broker by default — see the swap-point section below).

The shipped `CreateUserUseCase` is the canonical example — it emits `user.created` after `users.add(user)`.

### Adding a publisher to a use case

Take `EventBus` as a constructor parameter and publish AFTER the write succeeds:

```python
class RegisterOrderUseCase(UseCase[RegisterOrderInput, RegisterOrderOutput]):
    def __init__(self, *, orders: OrderRepository, clock: Clock, events: EventBus) -> None:
        self._orders = orders
        self._clock = clock
        self._events = events

    async def execute(self, input: RegisterOrderInput) -> RegisterOrderOutput:
        order = Order.place(...)
        await self._orders.add(order)
        await self._events.publish(
            "order.placed",
            {"order_id": str(order.id.value), "total_cents": order.total.value},
        )
        return RegisterOrderOutput(order_id=order.id)
```

Wire the new collaborator in `infrastructure/container.py` (extend `build_<use_case>`) and in `presentation/api/dependencies/<entity>.py` (chain `Depends(get_event_bus)`) — the User feature shows the exact shape.

### Event naming convention

`<aggregate>.<verb_past>` in dotted lowercase: `user.created`, `order.placed`, `payment.refunded`. The aggregate is the noun the event is about; the verb is past-tense (the event records a fact, not an intent). Avoid `user.creating` (intent) or `userCreated` (camel).

The payload is a flat `dict[str, Any]` of strings/ints/iso-dates — keep it small and stable, consumers depend on it.

### Producer-side idempotency

If a use case retries after a partial failure, the outbox row is part of the same transaction as the write — a retry that fails before commit produces neither the entity nor the event. Once the transaction commits, the row carries a unique `id`; the relay marks `published_at` only after every handler returns successfully. Handlers must dedupe on the row `id` if they have side-effects that cannot replay safely (sending an email, charging a card).

## Handling a domain event

Handlers live in `infrastructure/jobs/event_handlers.py` and register themselves via the `@handler("<event_name>")` decorator:

```python
from {{ cookiecutter.package_name }}.infrastructure.jobs.handlers import handler


@handler("user.created")
async def handle_user_created(payload: dict) -> None:
    """Send a welcome email, warm up a cache, …"""
    ...
```

Multiple handlers per event are allowed — they run sequentially in registration order. The shipped `handle_user_created` writes a structured log line as a placeholder; replace or extend with real side-effects.

### Handler contract

* **At-least-once.** A handler may run more than once for the same payload (relay crash before `published_at` is set ⇒ retry on next start). Make handlers idempotent — dedupe on `payload["<id_field>"]` or use an upsert.
* **Raise to signal failure.** Any exception leaves the row unpublished; the relay retries on the next tick. Do NOT swallow exceptions silently — that breaks the at-least-once guarantee.
* **No sync I/O.** Handlers are async; block-the-loop calls (`time.sleep`, sync HTTP) starve the relay.

### Where the swap point is

`infrastructure/jobs/handlers.py::dispatch` is the ONE function to replace when you wire a real broker (Kafka, Pub/Sub, SQS, …). Its current body forwards to in-process handlers; the new body becomes `await broker.publish(event_name, payload)` and the registry stays only for local development or moves elsewhere. Nothing else in the relay or in use cases changes.

## The relay worker

`infrastructure/jobs/outbox_relay.py` is a polling loop:

* Reads up to `BATCH_SIZE` (100) due rows (`status='pending'` AND `next_attempt_at IS NULL OR <= now()`) ordered by `created_at`.
* Locks the picked rows via `SELECT FOR UPDATE SKIP LOCKED` so concurrent relay replicas process disjoint batches.
* For each row, calls `_publish_event(event_name, payload)` which dispatches to registered handlers.
* On success, transitions the row to `status='published'` with `published_at = now()`.
* On handler exception, increments `attempts`, records `last_error`, and schedules a retry via `next_attempt_at = now() + compute_next_attempt(attempts)`.
* After `MAX_ATTEMPTS` failures (default 10), the row becomes `status='poisoned'` and is no longer picked up.
* Sleeps 1s when nothing is pending; traps `SIGTERM` / `SIGINT` to drain cleanly.

The relay ships as a **separate Deployment** (`<release>-relay`) in the
Helm chart — same image as the API, command override. Toggle via
`relay.enabled` in values; scale via `relay.replicaCount`
(SKIP LOCKED is safe with >1). Locally, the devcontainer's
`docker-compose.yml` starts a `relay` sidecar that auto-restarts until
the schema is ready — events flow without manual setup.

To run the relay manually outside any orchestrator:

```bash
uv run python -m {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay
```

### Row lifecycle

```
INSERT
   │
   ▼
status=pending, attempts=0, next_attempt_at=NULL
   │
   ├── handler ok ─────────────▶ status=published, published_at=now()  (terminal)
   │
   └── handler raises ─────────▶ attempts++,
                                 last_attempt_at=now(),
                                 last_error=repr(exc),
                                 next_attempt_at=now()+backoff(attempts)
                                       │
                                       ├── attempts < MAX_ATTEMPTS ─▶ stays pending, retried after backoff
                                       │
                                       └── attempts >= MAX_ATTEMPTS ▶ status=poisoned  (terminal until manual replay)
```

### Backoff schedule

Defined in `infrastructure/jobs/backoff.py` — edit the file to tune:

| Attempts (post-failure) | Next attempt in |
|---|---|
| 1 | 1 second |
| 2 | 5 seconds |
| 3 | 30 seconds |
| 4 | 2 minutes |
| 5 | 10 minutes |
| 6 | 30 minutes |
| 7+ | 1 hour (capped) |

Total elapsed time before poison ≈ 3 hours at `MAX_ATTEMPTS=10`.

### Multi-replica safety

`SELECT FOR UPDATE SKIP LOCKED` on Postgres lets you scale the relay
out — each replica locks its batch, others skip locked rows. Bumping
`relay.replicaCount` in values is therefore safe. SQLite (used only by
unit tests) silently ignores the clause; integration tests run on real
Postgres so the lock semantics are exercised.

### Metrics

`infrastructure/jobs/outbox_metrics.py` exposes:

* `outbox_events_pending` (gauge) — backlog size
* `outbox_events_poisoned` (gauge) — count of dead-lettered rows
* `outbox_oldest_pending_age_seconds` (gauge) — primary lag signal
* `outbox_handler_failures_total{event_name}` (counter) — failure rate per event

The relay process exposes them via `prometheus_client.start_http_server`
on `Settings.relay_metrics_port` (default `9100`). The relay
ServiceMonitor scrapes the dedicated `<release>-relay` Service when
`metrics.enabled=true`. Gauges are refreshed at the end of every drain
tick.

Suggested alert thresholds (for a future `PrometheusRule` in the chart):

| Alert | Threshold | What it means |
|---|---|---|
| `OutboxBacklog` | `outbox_events_pending > 1000` for 5m | Producer is outpacing the relay, or relay is stuck |
| `OutboxLag` | `outbox_oldest_pending_age_seconds > 300` | A row has been pending >5min — relay or downstream is failing |
| `OutboxPoisoned` | `outbox_events_poisoned > 0` | Manual triage required |
| `OutboxHandlerErrors` | `rate(outbox_handler_failures_total[5m]) > 0.1` | A handler regression or downstream outage |

### Manual replay of a poisoned row

Until an admin endpoint ships, requeue a single row via SQL:

```sql
UPDATE outbox_events
SET status = 'pending',
    attempts = 0,
    last_attempt_at = NULL,
    next_attempt_at = NULL,
    last_error = NULL
WHERE id = '<row-uuid>';
```

The relay picks it up on the next tick. Investigate `last_error` before
clearing it — a row poisoned the same way twice usually means the
handler or the payload is the problem, not the downstream.

## Disabling the outbox

Projects without events yet can wire the `NullEventBus` (also in `infrastructure/outbox.py`) instead of `SqlOutboxEventBus` in `build_event_bus`. The migration `0002_init_outbox` can be reverted with `just migrate-down` if no events ever flow.
