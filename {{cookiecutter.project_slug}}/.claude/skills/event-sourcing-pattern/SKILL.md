---
name: event-sourcing-pattern
description: When and how to event-source an entity in this codebase. Covers the SOMA-recommended "lite ES" variant (4 files per entity, synchronous projection, strong consistency) and explicitly delineates when to upgrade to strict CQRS instead. Documents the five places where the pattern leaks (schema evolution, queries, GDPR, debugging, performance) and how each is handled.
when_to_use: An entity needs a complete audit trail, time-travel queries, or replay capability; you're considering whether to event-source a new entity; an existing CRUD entity is being refactored to ES; you're reviewing a PR that introduces an event store; somebody asked "should we event-source X?".
---

# Event sourcing pattern (SOMA variant)

The template is **CRUD by default**. Event sourcing is opt-in **per entity** when an audit trail, time travel, or replay capability is genuinely required by the domain. Most SOMA entities will never need it; do not adopt this pattern speculatively.

## Decision table — should this entity be event-sourced?

| Symptom | Verdict |
|---|---|
| Compliance/audit demands a full history of every change | **Event-source** |
| Domain has many state transitions worth modeling explicitly (workflow, lifecycle) | **Event-source** |
| You'll need "what did X look like on date Y" queries in production | **Event-source** |
| You expect to derive several projections from the same facts (admin / customer / analytics views) | **Event-source** AND graduate to strict CQRS — see end of doc |
| Simple CRUD profile / settings / configuration | **CRUD** (template default) |
| Catalog / reference data | **CRUD** |
| Reporting / read-mostly | **CRUD** |
| Domain still in exploration; the model changes every sprint | **CRUD** — versioning events you'll throw away is wasted effort |
| Right-to-be-forgotten is a frequent operation | **CRUD** (or accept the crypto-shredding overhead) |

When in doubt: **start CRUD**. The lite ES variant below makes a retrofit reasonable later; over-engineering up front is harder to undo than under-engineering.

## The SOMA "lite ES" variant — 4 files per entity

Strict CQRS ships a separate read model with an asynchronous projector. We don't. We use the **same `<entity>` table** as both the read model AND the projection of the events. Updates to the table happen **inside the same transaction** as the event append, so reads stay strongly consistent and the async-projector machinery is unnecessary.

This trades the option of multiple read models for half the code and zero eventual-consistency surface. The Graduation section at the end explains when to give that up.

### File 1 — `domain/events/<entity>.py`

The typed facts the entity emits. Each event is a frozen `ValueObject`.

```python
from dataclasses import dataclass
from datetime import datetime

from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject


@dataclass(frozen=True, slots=True)
class UserRegistered(ValueObject):
    user_id: str
    email: str
    name: str
    at: datetime


@dataclass(frozen=True, slots=True)
class UserEmailChanged(ValueObject):
    user_id: str
    old_email: str
    new_email: str
```

Events are **named after business facts** (`UserEmailChanged`), not technical operations (`UserUpdated`). The fact-orientation is the whole point — `update` could mean anything.

### File 2 — `infrastructure/persistence/event_store.py`

The append-only log. One generic table (`events`) shared across entities, with `aggregate_type` filtering.

```python
class EventStore:
    """Append-only log of domain events. Generic; shared across entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, *, aggregate_type: str, aggregate_id: UUID) -> list[DomainEvent]:
        rows = await self._session.execute(
            select(EventModel)
            .where(EventModel.aggregate_type == aggregate_type)
            .where(EventModel.aggregate_id == aggregate_id)
            .order_by(EventModel.sequence)
        )
        return [self._deserialize(row) for row in rows.scalars()]

    async def append(
        self,
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        events: list[DomainEvent],
        expected_version: int,
    ) -> None:
        current = await self._session.scalar(
            select(func.coalesce(func.max(EventModel.sequence), 0))
            .where(EventModel.aggregate_type == aggregate_type)
            .where(EventModel.aggregate_id == aggregate_id)
        )
        if current != expected_version:
            raise OptimisticConcurrencyError(...)
        for offset, event in enumerate(events, start=1):
            self._session.add(EventModel(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                sequence=expected_version + offset,
                event_type=type(event).__name__,
                event_version=getattr(event, "version", 1),
                payload=asdict(event),
            ))
        await self._session.flush()
```

### File 3 — `infrastructure/persistence/event_sourced_<entity>_repository.py`

The Repo Protocol implementation. **This is the only file where "this entity is event-sourced" is visible.** Reads use the regular `<entity>` table (the projection); writes append events AND update the table in the same transaction.

```python
class EventSourcedUserRepository(UserRepository):
    def __init__(self, session: AsyncSession, event_store: EventStore) -> None:
        self._session = session
        self._events = event_store

    async def find_by_id(self, id: UserId) -> User | None:
        # Reads go through the projection table (= the regular `users` table).
        row = await self._session.get(UserModel, id.value)
        return self._to_user(row) if row else None

    async def find_by_email(self, email: Email) -> User | None:
        row = await self._session.scalar(
            select(UserModel).where(UserModel.email == str(email))
        )
        return self._to_user(row) if row else None

    async def save(self, user: User) -> None:
        # 1. Append events (audit trail / source of truth)
        await self._events.append(
            aggregate_type="User",
            aggregate_id=user.id.value,
            events=user._pending_events,
            expected_version=user._version,
        )
        # 2. Apply each event to the read-model table — same transaction.
        for event in user._pending_events:
            self._apply(event)
        user._pending_events.clear()
        user._version += len(user._pending_events)

    def _apply(self, event: DomainEvent) -> None:
        if isinstance(event, UserRegistered):
            self._session.add(UserModel(
                id=UUID(event.user_id),
                email=event.email,
                name=event.name,
                created_at=event.at,
            ))
        elif isinstance(event, UserEmailChanged):
            row = self._session.execute(
                update(UserModel)
                .where(UserModel.id == UUID(event.user_id))
                .values(email=event.new_email)
            )
        # ...
```

### File 4 — `alembic/versions/000X_init_events_table.py`

Generic events table; idempotent so multiple entities adopting ES don't conflict.

```python
def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("aggregate_type", sa.String(64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aggregate_type", "aggregate_id", "sequence"),
    )
    op.create_index(
        "ix_events_aggregate",
        "events",
        ["aggregate_type", "aggregate_id", "sequence"],
    )
```

## The domain entity changes too (not a separate file, but unavoidable)

The entity must track its pending events and expose its version. This is the **one place the ES discipline is visible to anyone authoring the domain** — the use case writer never sees it.

```python
class User(Entity[UserId]):
    def __init__(self, ...) -> None:
        super().__init__(...)
        self._pending_events: list[DomainEvent] = []
        self._version: int = 0

    @classmethod
    def register(cls, *, id: UserId, email: Email, name: str, now: datetime) -> "User":
        user = cls(id=id, email=email, name=name, created_at=now)
        user._record(UserRegistered(user_id=str(id.value), email=str(email), name=name, at=now))
        return user

    def change_email(self, new_email: Email) -> None:
        if self.email == new_email:
            return
        self._record(UserEmailChanged(
            user_id=str(self.id.value),
            old_email=str(self.email),
            new_email=str(new_email),
        ))
        self.email = new_email

    def _record(self, event: DomainEvent) -> None:
        self._pending_events.append(event)

    @classmethod
    def from_events(cls, events: list[DomainEvent]) -> "User":
        """Replay used by ``EventStore`` consumers — admin tools, projection rebuild."""
        user = None
        for event in events:
            if isinstance(event, UserRegistered):
                user = cls(
                    id=UserId(UUID(event.user_id)),
                    email=Email(event.email),
                    name=event.name,
                    created_at=event.at,
                )
            elif isinstance(event, UserEmailChanged):
                user.email = Email(event.new_email)
        user._version = len(events)
        return user
```

The use case is unchanged from the CRUD version — it calls `user.change_email(...)` and `users.save(user)`. Whether the impl is CRUD or ES is the container's decision.

## The five leaks (and how each is handled)

ES is not a transparent storage detail; this section is honest about where the abstraction breaks.

### 1. Adding a query method

Adding `find_active_in_country(country)` to the Repo Protocol:

* **CRUD impl**: trivial SQL.
* **ES impl**: trivial SQL **because the read model is the same table**. The lite ES variant pays nothing extra here. (Strict CQRS would force a new projection.)

This is the biggest win of the lite variant: query methods stay easy.

### 2. Adding a field to the entity

Adding `User.locale`:

* CRUD: column migration, default value. Done.
* Lite ES: column migration on `users` AND
  * Pick a versioning strategy for `UserRegistered`:
    * **Default value at deserialization**: simplest; `locale` defaults to `"en"` for old events. Loses the distinction "before this feature existed" vs "explicitly chose default".
    * **Versioned event class**: ship `UserRegisteredV2`. Both versions handled in `from_events` and `_apply`. More code, exact semantics.
  * Update `_apply(UserRegistered)` to populate the new column.
  * Update `from_events` if the field affects replayed state.

The skill `database-and-migrations` covers the column part; this skill covers the event versioning part.

### 3. GDPR right-to-be-forgotten

* CRUD: `DELETE FROM users WHERE id = ?`. 5 seconds.
* Lite ES: events are immutable. Pick a strategy:
  * **Crypto-shredding**: PII fields in events encrypted with a per-user key. Delete the key → events become unintelligible. Setup overhead but legally clean.
  * **Tombstone event**: emit `UserForgotten`, scrubs the projection (UPDATE users SET email=NULL, name='[forgotten]'). The original events remain but downstream consumers honor the tombstone. Audit trail acknowledges erasure occurred.
  * **True deletion**: DELETE the events. Breaks append-only; audit trail loses the user. Last resort.

Pick the strategy at the bounded context level, not per request. Document it in `docs/runbooks/`.

### 4. Debugging "the projection shows the wrong value"

In lite ES the projection is updated synchronously, so there is no projector lag. If the projection disagrees with the events, it's a bug in `_apply` or in `from_events`, not a race. Investigation:

```sql
-- The events:
SELECT sequence, event_type, payload FROM events
WHERE aggregate_type = 'User' AND aggregate_id = '<uuid>'
ORDER BY sequence;

-- The projection:
SELECT * FROM users WHERE id = '<uuid>';
```

If they don't match: check the repo's `_apply` is exhaustive over event types AND the entity's `from_events` matches what `_apply` writes. The two must stay in sync — a fixture test that compares "applied via repo" against "replayed via from_events" catches drift before prod.

### 5. Performance — replay cost grows with event count

Lite ES `find_by_id` reads the `users` row (O(1)). No replay needed for reads. Only `from_events` (used by admin tools, projection rebuild) walks the full event list.

If `from_events` becomes a hot path (rare), add **snapshots** — but the SOMA recommendation is to delay this until you see real numbers. Premature snapshot logic is the second-worst kind of complexity in ES, right after premature versioning.

## Migrating an existing CRUD entity to lite ES

Steps (per entity, not bulk):

1. **Decide explicitly.** The decision table at the top must yield "event-source".
2. **Scaffold the four ES files** for that entity, following the file layout in this skill: the `events` table-row helper, the aggregate repository (`EventSourced<Entity>Repository`) that hydrates from events, the projection table (read model), and the projection updater. The main agent writes these directly — there is no dedicated sub-agent.
3. **Rewrite the domain entity** to track `_pending_events` and emit events from each mutation method. Scaffolding cannot do this for you — the events are business facts that need careful naming.
4. **Wire the new repo in `container.py`**: swap `build_user_repository` to construct the `EventSourcedUserRepository` instead of `SqlAlchemyUserRepository`.
5. **Backfill events from existing rows**:
   ```sql
   INSERT INTO events (aggregate_type, aggregate_id, sequence, event_type, payload, created_at)
   SELECT 'User', id, 1, 'UserRegistered',
          json_build_object('user_id', id::text, 'email', email, 'name', name, 'at', created_at),
          created_at
   FROM users;
   ```
6. **Test the round trip**: integration test that builds a User via use case, then `from_events(events_table_rows)` returns the same User.
7. **Ship**, monitor for `OptimisticConcurrencyError` spikes (sign of bad version tracking).

## Cross-link with the outbox

The `events` table is **local audit / replay**. The `outbox_events` table is **inter-service notification**. They serve different purposes and can coexist:

* The lite ES repo writes to `events` (audit trail).
* If the entity also publishes notifications to downstream services, the use case `await events_bus.publish(...)` writes to `outbox_events` as before.
* Both writes happen in the same request transaction → atomic.

A future evolution: the `outbox_relay` could project events into a SOMA-wide event archive (S3/BigQuery), giving cross-service audit + analytics without forcing strict CQRS in any service.

## When to graduate to strict CQRS

Switch to a separate async projection (the "7-file" variant) when:

* You need **more than one read model** for the same events (admin view + customer view + analytics view).
* The read model needs to live in a different store (Elasticsearch for full-text, ClickHouse for analytics) than the write side.
* The write throughput needs to scale independently of the read throughput.

Until those constraints bite, lite ES is the better default — it keeps strong consistency and avoids the projector pod.
