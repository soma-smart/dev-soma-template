---
name: transactions-and-events
description: How to commit/rollback at the request boundary and how to publish domain events via the outbox.
when_to_use: A use case mutates more than one entity, raises errors after partial writes, or needs to publish an event. Editing infrastructure/outbox.py or infrastructure/jobs/outbox_relay.py.
---

# Transactions and events

## Transaction boundary (ADR 0004)

A single HTTP request = a single SQLAlchemy transaction.

`presentation/api/dependencies/common.py::get_session` opens both the session and the transaction. The transaction commits on a successful return and rolls back on **any** raised exception, including `DomainError`. That intentional behaviour means a use case that has done a partial write and then raises `UserAlreadyExistsError` (or any other domain error) leaves the database untouched.

What this implies for you:

* **Repositories call `flush()`, never `commit()`.** Flush surfaces integrity errors immediately so they can be translated into `DomainError`. Commit is the dependency wrapper's job.
* **Use cases never see transactions.** No `session.begin()`, no `commit()`, no `rollback()` in `application/`.
* **Multiple writes are atomic by default.** Two `repo.add(...)` calls in the same use case commit together or roll back together.

If a use case truly needs sub-transactional checkpointing (rare), use savepoints:

```python
async with session.begin_nested():
    ...   # this block can fail without aborting the outer transaction
```

## Publishing a domain event (ADR 0005)

Use cases publish through the abstract `EventBus`. The production binding is `SqlOutboxEventBus`: it writes a row to ``outbox_events`` inside the request transaction, then a separate relay forwards it to the real broker.

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
        self._users = users
        self._clock = clock
        self._ids = ids
        self._events = events

    async def execute(self, input: CreateUserInput) -> CreateUserOutput:
        # ... build the user, persist, etc.
        await self._users.add(user)
        await self._events.publish(
            "user.created",
            {"id": str(user.id), "email": str(user.email)},
        )
        return ...
```

Wire the dependency in `infrastructure/container.py` (`build_event_bus(session)`) and in `presentation/api/dependencies/<noun>.py` (`Depends(get_event_bus)`).

## The relay worker

`infrastructure/jobs/outbox_relay.py` ships as a polling-loop scaffold:

* Reads up to 100 unpublished rows ordered by `created_at`.
* Calls `_publish_event(event_name, payload)` per row — **stubbed; replace with your broker code**.
* Marks `published_at = now()` only after the broker durably ACKs.
* Sleeps 1s when nothing is pending; uses `signal.SIGTERM` / `SIGINT` to drain cleanly.

Run it as a separate container next to the API:

```bash
uv run python -m {{ cookiecutter.package_name }}.infrastructure.jobs.outbox_relay
```

Replacement requirements:

* **At-least-once**: only mark `published_at` after the broker has durably acknowledged.
* **Idempotent consumers**: events carry a unique ``id``; consumers deduplicate.
* **Backoff + alerting**: a row stuck unpublished for more than N minutes is a paging condition.

## Disabling the outbox

Projects that don't publish events yet can wire the `NullEventBus` (also in `infrastructure/outbox.py`). The migration `0002_init_outbox` can be reverted (`just migrate-down`) if no events ever flow.
