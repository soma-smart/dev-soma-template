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

* Reads up to `BATCH_SIZE` (100) unpublished rows ordered by `created_at`.
* For each row, calls `_publish_event(event_name, payload)` which dispatches to registered handlers.
* Marks `published_at = now()` only when **every** handler returns successfully. A handler exception leaves the row alone for the next tick.
* Sleeps 1s when nothing is pending; traps `SIGTERM` / `SIGINT` to drain cleanly.

Run it as a separate container next to the API:

```bash
uv run python -m {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay
```

### Multi-replica caveat

Running multiple relay pods will dispatch every event on every pod — handlers must be idempotent OR the deployment must keep a single replica (`replicaCount: 1` in the values overlay). The default Helm chart ships a separate Deployment for the relay; pick the strategy that matches the handlers you ship.

### Backoff + alerting (to add before prod)

A row stuck unpublished for more than N minutes is a paging condition. The default loop has no exponential backoff on repeated handler failure — add one before going to prod, otherwise a perpetually-failing handler will poll the row every second forever.

## Disabling the outbox

Projects without events yet can wire the `NullEventBus` (also in `infrastructure/outbox.py`) instead of `SqlOutboxEventBus` in `build_event_bus`. The migration `0002_init_outbox` can be reverted with `just migrate-down` if no events ever flow.
