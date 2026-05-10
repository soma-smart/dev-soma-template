---
name: transactions-and-events
description: How commit/rollback works at the request boundary (ADR 0004) and how use cases publish domain events through the SQL outbox (ADR 0005). The single source of truth for atomicity in this codebase.
when_to_use: A use case writes more than one entity; a use case raises errors after partial writes; a use case needs to publish a domain event; editing infrastructure/outbox.py or infrastructure/jobs/outbox_relay.py.
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
* **`_instrumented` cooperates** — when the use case raises a `DomainError`, the wrapper logs it at `WARNING` (with `code` + `context`) and re-raises; the dependency wrapper at the boundary then rolls back. No partial state survives.

### Sub-transactional checkpoints (rare)

If you genuinely need to let a sub-step fail without aborting the outer transaction, use a savepoint:

```python
async with session.begin_nested():
    ...   # this block can fail without aborting the outer transaction
```

The integration-test `pg_session` fixture uses the same mechanism via `join_transaction_mode="create_savepoint"` — read it if you want a worked example.

## Publishing a domain event (ADR 0005)

Use cases publish through the abstract `EventBus`. The production binding is `SqlOutboxEventBus`: it writes a row to `outbox_events` **inside the request transaction**. The entity write and the outbox row commit or roll back together — consumers see an event iff the entity exists.

A separate `outbox_relay` worker polls unpublished rows and forwards them to the real broker out of band, providing at-least-once delivery.

### Adding events to a use case

The shipped `CreateUserUseCase` does not currently emit events. To make a use case emit one, take an `EventBus` constructor parameter:

```python
class CreateUserUseCase(UseCase[CreateUserInput, CreateUserOutput]):
    def __init__(
        self,
        *,
        users: UserRepository,
        clock: Clock,
        ids: IdGenerator,
        events: EventBus,
    ) -> None:
        ...

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        # ... build the user, persist
        await self._users.add(user)
        await self._events.publish(
            "user.created",
            {"id": str(user.id), "email": str(user.email)},
        )
        return ...
```

Then in `infrastructure/container.py`, extend the existing factory:

```python
def build_create_user_use_case(
    *,
    users: UserRepository,
    clock: Clock,
    ids: IdGenerator,
    events: EventBus,                       # new parameter
) -> CreateUserUseCase:
    use_case = CreateUserUseCase(users=users, clock=clock, ids=ids, events=events)
    return _instrumented(use_case, span_name="create_user")
```

And in `presentation/api/dependencies/users.py`, add a `get_event_bus` (or reuse one in `common.py`) and chain it:

```python
def get_event_bus(session: AsyncSession = Depends(get_session)) -> EventBus:
    return build_event_bus(session)


def get_create_user_use_case(
    users: UserRepository = Depends(get_user_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
    events: EventBus = Depends(get_event_bus),     # new
) -> CreateUserUseCase:
    return build_create_user_use_case(users=users, clock=clock, ids=ids, events=events)
```

### Event naming convention

`<aggregate>.<verb_past>` in dotted lowercase: `user.created`, `order.shipped`, `payment.refunded`. The aggregate is the noun the event is about; the verb is past-tense (the event records a fact, not an intent). Avoid `user.creating` (intent) or `userCreated` (camel).

The payload is a flat `dict[str, Any]` of strings/ints/dates — keep it small and stable, consumers depend on it.

### Producer-side idempotency

If a use case retries after a partial failure, the outbox row is part of the same transaction as the write — a retry that fails before commit produces neither the entity nor the event. Once the transaction commits, the row carries a unique `id`; the relay marks `published_at` only after the broker durably ACKs. Consumers must dedupe on the row `id` (the `id` is propagated as the event identifier).

## The relay worker

`infrastructure/jobs/outbox_relay.py` ships as a polling-loop scaffold:

* Reads up to `BATCH_SIZE` (100) unpublished rows ordered by `created_at`.
* Calls `_publish_event(event_name, payload)` per row — **stubbed; replace with your broker code**.
* Marks `published_at = now()` only after the broker durably ACKs.
* Sleeps 1s when nothing is pending; traps `SIGTERM` / `SIGINT` to drain cleanly.

Run it as a separate container next to the API:

```bash
uv run python -m {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay
```

When swapping `_publish_event` for the real broker, the contract is:

* **At-least-once.** Mark `published_at` only after a durable ACK from the broker.
* **Idempotent consumers.** The event `id` is unique; consumers must dedupe on it.
* **Backoff + alerting.** A row stuck unpublished for more than N minutes is a paging condition. The default loop has no backoff — add it before going to prod.

## Disabling the outbox

Projects without events yet can wire the `NullEventBus` (also in `infrastructure/outbox.py`) instead of `SqlOutboxEventBus` in `build_event_bus`. The migration `0002_init_outbox` can be reverted with `just migrate-down` if no events ever flow.
