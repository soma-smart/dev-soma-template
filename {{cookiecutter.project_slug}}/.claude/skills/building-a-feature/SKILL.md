---
name: building-a-feature
description: End-to-end runbook for delivering a feature — clarification questions, outside-in plan, outside-in TDD across use case → persistence → route, container wiring, mutation. Replaces the old orchestration/use-case/abstractions/transactions/idempotency skill bundle. Use this when the user asks for a new feature.
when_to_use: User asks for "a new feature", "a new use case", "a new endpoint", "let's implement <verb> <noun>". Pair with tdd-workflow at every step that produces logic.
---

# Building a feature — outside-in end to end

A new feature crosses all four layers. The discipline is **outside-in**: start from the feature description, write the failing outer test (use case with Fakes), let domain pieces emerge as the test demands them. NEVER pre-build value objects, entities, or Protocol methods that no test requires.

This skill is the runbook the main agent follows. There is no sub-agent dispatch — every step runs in the current conversation with `tdd-workflow`, `writing-domain-code`, `onboarding-soma` (naming + DI + observability) loaded as references.

## Flow

1. **Parse the prompt** — usually a one-liner.
2. **Ask clarification questions** using the question packs below.
3. **Produce the 5-section outside-in plan**.
4. **User validates**.
5. **Use case TDD** — outer test, then `ImportError` chain. (unit tests with Fakes)
6. **Persistence TDD** — SQLAlchemy model, repository binding, Alembic migration. (integration tests with testcontainers)
7. **Route TDD** — Pydantic schemas, FastAPI route, container factory, `Depends` wrapper. (1 happy + 1 critical e2e test)
8. **Container wiring** — register new factories in `infrastructure/container.py` and dependency wrappers.
9. **Mutate** — `just mutate` until kill rate ≥ 90%.
10. **Final lint** — `just lint`, GIVEN/WHEN/THEN check, domain purity check.

---

## 1. Parse the prompt

The user typically asks in one line:

> *« Je veux pouvoir créer une TodoList, une seule par personne, avec un nom et une description »*

That single line is NOT something you act on directly. The next step is asking the questions that ambiguities of that line raise.

---

## 2. Clarification questions — pick from these packs

Don't invent questions. Pick the relevant items from the packs below; each one is a known fork that changes observable behaviour. Skip a pack if the prompt already answers it.

### Pack A — Scope & inputs
- A1. What fields are on the input? (For each: max length, optional or required, validation rules?)
- A2. Which fields are derived (server-generated id, timestamp, owner from auth) vs sent by the client?
- A3. What is the user-facing output? (full entity, or just an id, or 204?)

### Pack B — Uniqueness & lifecycle
- B1. Is there a uniqueness rule? If yes, on which combination of fields? Scoped to whom (owner, tenant, global)?
- B2. Soft-delete or hard-delete? If soft, do soft-deleted rows count for uniqueness?
- B3. Can the entity be re-created after deletion?

### Pack C — Auth & multi-tenancy
- C1. Public, authenticated, or role-restricted? (which roles?)
- C2. Is the action attributed to an actor (`current_user`)? How does it arrive in the use case (DTO field, separate collaborator)?
- C3. Multi-tenant scope — does the rule apply per-tenant?

### Pack D — Events & side effects
- D1. Does the use case emit an event? If yes, the literal event name (`<aggregate>.<verb_past>`) and the payload semantics ("the consumer must be able to identify the new entity, its owner, …").
- D2. Does the use case call a downstream system (email, webhook)? If yes, through which existing abstraction?

### Pack E — Errors & HTTP
- E1. For each error path (duplicate, not found, validation failure), what HTTP status?
- E2. Is the endpoint idempotency-key-eligible? (POST/PUT/PATCH/DELETE writes are by default — see § Idempotency below.)

### Pack F — Out of scope
- F1. Anything explicitly NOT in this slice? (list endpoint, delete endpoint, admin variant)

Pick 4-6 questions. Ask them in a numbered list. The user answers in one message.

---

## 3. The 5-section outside-in plan

After the user answers, produce a one-page plan with exactly these five sections.

> ⚠ **The "Tests that will be written" section is at use case (behavioural) level ONLY.** Adding bullets like "the `Name` VO rejects blank entries" or a "Domain (drill)" subsection is a leak — it pre-decides where validation lives (VO `__post_init__` vs entity factory vs use case body). That defeats outside-in TDD. The domain structure must emerge from the failing use case tests during the build, not be sketched in the plan.
>
> Bad: ❌ *"The `name` VO rejects blank or whitespace-only entries"*
>
> Good: ✅ *"GIVEN a blank name, WHEN creating, THEN the use case raises a validation error"*

### 1. Tests that will be written
Behavioural cases expressed in GIVEN/WHEN/THEN at the use case level. One bullet per branch the user cares about. Example:
- *GIVEN an authenticated user with no list, WHEN they create one with a valid name, THEN the list is persisted and a `todo_list.created` event is emitted.*
- *GIVEN an authenticated user already owning a list named "Shopping", WHEN they try to create another with the same name, THEN the use case raises `<NotPredeterminedError>` (the builder picks the exact class name).*

### 2. Abstractions needed — by role, never by name
List the *roles* of the collaborators. Do **NOT** write `TodoListRepository` or `find_active_by_owner_and_name`. The implementation step names everything.
- *A repository for the new entity (uniqueness check + persistence).*
- *The existing Clock and IdGenerator from `application/`.*
- *EventBus (existing).*

### 3. API surface — one line unless it gets weird
`<METHOD> <path>`, auth scheme, status codes per outcome, idempotency flag. Elaborate **only** when something non-obvious is at play.
- `POST /v1/todo-lists` — authenticated — 201 happy, 409 on duplicate, 422 on validation — idempotency-key eligible.

### 4. External contracts that ARE pre-decided
Pre-committed because third parties depend on them:
- Event: `todo_list.created` with `{ "id": "<uuid>", "owner_id": "<uuid>", "name": "<str>" }`.
- HTTP error mapping: `<NotPredeterminedDuplicateError>` → 409, validation errors → 422.

### 5. Behavioural questions to clarify
If anything is still ambiguous after the Q&A, list it here and stop. Otherwise: "none — ready to build".

### What does NOT go in the plan

- Class names (no "TodoList entity", no "TodoListId VO")
- Protocol method signatures (no "find_active_by_owner_and_name")
- Exception names or codes (the implementation picks them per `onboarding-soma` § naming)
- Entity field lists (a field is added when a test demands it)
- DTO field lists (same)

These are **internal** and emerge from the tests during implementation. Pre-deciding them is anti-TDD.

---

## 4. User validates

Show the plan. Wait for "go" or corrections. Address behavioural questions explicitly before any code is written.

---

## 5. Use case TDD (unit tests with Fakes)

Open `tests/unit/application/test_<verb>_<noun>_use_case.py` and write the test as if every class and method already existed. Run the test. Get an `ImportError`. That's correct — the next file you create is the missing import.

### Domain pieces emerge

| Emerges when… | Where | Base | User reference |
|---|---|---|---|
| The test stores entity instances in the Fake | `domain/entities/<name>.py` | `Entity[<Name>Id]` | `domain/entities/user.py` |
| The entity needs a typed identifier or a constrained scalar | `domain/value_objects/<name>.py` | `ValueObject` + `@dataclass(frozen=True, slots=True)` | `domain/value_objects/email.py`, `user_id.py` |
| The test calls `pytest.raises(<X>Error)` | `domain/exceptions/<bounded_context>.py` | `DomainError` | `domain/exceptions/user.py` |

For domain rules (no third-party, no `datetime.now()`, no `float`, no log), see `writing-domain-code`.

### Application pieces emerge

| Emerges when… | Where | Base |
|---|---|---|
| The Fake stores something — you need a Protocol to type-hint it | `application/repositories/<entity>.py` | `Repository[<Entity>, <Entity>Id]` Protocol — start empty; add business-named methods only when a test forces them. |
| The use case body needs a collaborator that doesn't exist yet (`EmailSender`, `Cache`, …) | `application/<role>.py` | `typing.Protocol` |

**Before declaring a new collaborator**, check the "Adding a new abstraction" section below. The existing protocols (`Clock`, `IdGenerator`, `RandomSource`, `EventBus`, `AuditLog`, `Repository`) cover most "I need a new port" thoughts.

### Repository Protocol method extension

The base `Repository[TEntity, TId]` Protocol ships only `add` and `find_by_id`. **Every other method is added by the test that needs it** (outside-in), named after the business question being asked, not the SQL operation.

```python
class TodoListRepository(Repository[TodoList, TodoListId], Protocol):
    """Persistence contract for the TodoList aggregate."""

    async def find_active_by_owner_and_name(
        self, owner_id: UserId, name: str
    ) -> TodoList | None:
        """Return the non-deleted list named ``name`` owned by ``owner_id``.

        Used by CreateTodoListUseCase for the uniqueness check before
        creation. Soft-deleted lists are ignored.
        """
        ...
```

For the naming rules and anti-pattern table, see `onboarding-soma` § "Repository method naming".

### The use case body

`application/use_cases/<verb>_<noun>.py`:

```python
from {{ cookiecutter.package_name }}.application.use_cases.base import UseCase


class <Action><Noun>UseCase(UseCase[<Action><Noun>Input, <Action><Noun>Output]):
    """One-line summary including the exceptions it may raise."""

    def __init__(self, *, <collab1>: <Type1>, <collab2>: <Type2>) -> None:
        self._<collab1> = <collab1>
        self._<collab2> = <collab2>

    async def execute(self, input: <Action><Noun>Input) -> <Action><Noun>Output:
        ...
```

User reference: `application/use_cases/ensure_user_exists.py`.

The `UseCase[TInput, TOutput]` generic surfaces input/output types at the class header. Cross-cutting concerns (OTel span, structured warning/error log on raise) are added by `_instrumented` in `infrastructure/container.py` — **never** inside the use case body.

### DTOs

`application/dtos/<noun>.py`:

```python
@dataclass(frozen=True, slots=True)
class <Action><Noun>Input:
    ...

@dataclass(frozen=True, slots=True)
class <Action><Noun>Output:
    ...
```

User reference: `application/dtos/user.py`.

### Next branches — each new business rule is a new outer red

After the happy-path test is green, each additional rule is a NEW outer test:

- "Refuses duplicates per owner" → adds a Protocol method + a `<Entity>AlreadyExistsError` + the check in the use case body.
- "Emits `<aggregate>.<verb_past>`" → adds `EventBus` to `__init__` + `await self._events.publish(...)` after the write.
- "Validates the input field" → either at the value object level (`<Field>Error` raised in `__post_init__`) or at the use case.

See `tdd-workflow` for the full red-green loop.

---

## 6. Persistence TDD (integration tests with testcontainers)

Once the use case is green at unit level, write the SQLAlchemy binding.

### Files to create

| Need | Where | User reference |
|---|---|---|
| SQLAlchemy ORM model | `infrastructure/persistence/models/<noun>.py` (suffix `…Model`) | `infrastructure/persistence/models/user.py` |
| Concrete repository | `infrastructure/persistence/<noun>_repository.py` (`SqlAlchemy<Noun>Repository`) with private `_to_entity` / `_to_model` | `infrastructure/persistence/user_repository.py` |
| Alembic migration | `just migration "add_<noun>"` then **read** the autogenerated revision before committing | `alembic/versions/0001_init_users.py` |

For migration rules, see `database-and-migrations`.

### Integration test pattern

`tests/integration/infrastructure/test_<noun>_repository.py`:

- At least: happy `add` + `find_by_id`, integrity violation translated to the right `DomainError`, missing-id returns `None`.
- One distinct test per edge case (no `parametrize`).
- Format: GIVEN / WHEN / THEN.
- Use the `pg_session` fixture from `tests/integration/conftest.py`.

Run `just test-integration` (Docker required — testcontainers spawns Postgres).

User reference: `tests/integration/infrastructure/test_user_repository.py`.

### Translating IntegrityError to DomainError

Call `flush()`, **never** `commit()`. Flush surfaces integrity errors immediately so the repo can translate them into a `DomainError`. Commit is the dependency wrapper's job — see § Transactions below.

```python
async def add(self, todo_list: TodoList, /) -> None:
    self._session.add(self._to_model(todo_list))
    try:
        await self._session.flush()
    except IntegrityError as exc:
        raise TodoListAlreadyExistsError(...) from exc
```

### Aggregates with nested children (e.g. TodoList → TodoItem[])

When the aggregate root owns a collection of child entities, the
persistence pattern needs three pieces:

**1. Relationship on the ORM root**, with cascade + eager loading and
the column to sort children by:

```python
class TodoListModel(Base):
    ...
    items: Mapped[list[TodoItemModel]] = relationship(
        back_populates="todo_list",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TodoItemModel.position",
    )
```

`cascade="all, delete-orphan"` makes a removed child in the domain
collection translate to a DELETE on the row. `lazy="selectin"` triggers
a second query at access time, but it's batched (no N+1).

**2. `find_by_id` eager-loads** the children explicitly so the use case
gets the whole aggregate in one call:

```python
async def find_by_id(self, id: TodoListId) -> TodoList | None:
    stmt = (
        select(TodoListModel)
        .where(TodoListModel.id == id.value)
        .options(selectinload(TodoListModel.items))
    )
    model = (await self._session.execute(stmt)).scalar_one_or_none()
    return self._to_entity(model) if model is not None else None
```

**3. A `save(aggregate)` method on the repository** that reconciles the
domain entity with its stored representation — new children get
inserted, existing children get updated, the rest is handled by
cascade. The use case calls `await repo.save(todo_list)` after any
mutation:

```python
async def save(self, todo_list: TodoList) -> None:
    stmt = (
        select(TodoListModel)
        .where(TodoListModel.id == todo_list.id.value)
        .options(selectinload(TodoListModel.items))
    )
    model = (await self._session.execute(stmt)).scalar_one()
    # Update root-level fields the domain entity exposes.
    model.name = todo_list.name
    model.description = todo_list.description
    model.deleted_at = todo_list.deleted_at

    # Diff children: insert new, update existing.
    existing_by_id = {item.id: item for item in model.items}
    for domain_item in todo_list.items:
        existing = existing_by_id.get(domain_item.id.value)
        if existing is None:
            model.items.append(self._item_to_model(domain_item))
        else:
            existing.name = domain_item.name
            existing.description = domain_item.description
            existing.position = domain_item.position
            existing.completed_at = domain_item.completed_at
    await self._session.flush()
```

The `save` method is added to the Protocol; the Fake repository
implements it as a no-op (or a rebind) since its dict-based storage
already reflects in-memory mutations by reference.

---

## 7. Route TDD (e2e test)

Once persistence is green, expose the use case over HTTP.

### Files to create

| Need | Where | User reference |
|---|---|---|
| Pydantic schemas (request + response) | `presentation/api/schemas/<noun>.py` (suffix `…Schema`) | `presentation/api/schemas/user.py` |
| `Depends` wrappers around container factories | `presentation/api/dependencies/<noun>.py` | `presentation/api/dependencies/users.py` |
| Versioned router | `presentation/api/v1/<noun>.py` | `presentation/api/v1/users.py` |
| Wire the router | add `app.include_router(<noun>_v1.router)` in `presentation/api/app.py` | already there for users |

### Error → HTTP mapping

If the use case raises a **new** `DomainError`, register it in `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING`. The unit test `tests/unit/presentation/test_error_mapping.py` auto-discovers via `DomainError.__subclasses__()` and fails otherwise.

If you want a different HTTP status for the same error type in different endpoints, that means you actually want a new error type — extract one. Don't override per-use-case.

### HTTP status cheat sheet

| Domain meaning | HTTP |
|---|---|
| Generic bad request, malformed body that Pydantic did not catch | 400 |
| Missing resource (lookup returned `None`) | 404 |
| Conflict (duplicate, version mismatch) | 409 |
| Resource removed permanently | 410 |
| Validation failure on a well-shaped input (business rule) | 422 |
| Authentication missing | 401 |
| Authorization insufficient | 403 |
| Payment required | 402 |
| Resource locked (concurrent edit) | 423 |
| Rate limited | 429 |
| Downstream service unavailable | 503 |

### E2E test pattern

`tests/e2e/api/test_<verb>_<noun>_endpoint.py` — **1 happy + 1 critical error**. Do NOT re-test use case branches here; they are already covered at the unit level. The `client` fixture gives a `TestClient` with the in-memory Fakes pre-wired.

User reference: `tests/e2e/api/test_users_me_endpoint.py`.

---

## 8. Container wiring

`infrastructure/container.py`:

```python
def build_<noun>_repository(session: AsyncSession) -> <Noun>Repository:
    return SqlAlchemy<Noun>Repository(session)


def build_<action>_<noun>_use_case(
    *,
    <noun>s: <Noun>Repository,
    clock: Clock,
    ids: IdGenerator,
) -> <Action><Noun>UseCase:
    use_case = <Action><Noun>UseCase(<noun>s=<noun>s, clock=clock, ids=ids)
    return _instrumented(use_case, span_name="<action>_<noun>")
```

Every use case factory wraps with `_instrumented(span_name=...)`. For full DI rules, see `onboarding-soma` § DI container.

---

## 9. Mutate

```bash
just mutate           # mutmut on domain + application
just mutate-results   # latest report
```

Kill every surviving mutant by adding a focused test (outer if possible, inner if the mutation is inside a domain method). Target ≥ 90% kill rate.

---

## 10. Final lint

```bash
just lint        # ruff + ty + 4 architectural lints + format
just test-all    # unit + integration + e2e
just mutate      # mutmut on domain + application; CI enforces ≥ 90% kill rate
```

---

# Adding a new abstraction

When the use case needs a collaborator that doesn't exist yet.

## STOP — check the existing ones first

| Existing abstraction | Already covers — common mistakes |
|---|---|
| `Clock` (`application/clock.py`) | "What time is it?" Anything time-based. Never `datetime.now()` instead. |
| `IdGenerator` (`application/id_generator.py`) | New identifier generation. Don't write a `TokenGenerator` for opaque IDs — wrap or extend `IdGenerator`. |
| `RandomSource` (`application/random_source.py`) | Any random draw. Don't write a separate `JitterSource`. |
| `EventBus` (`application/event_bus.py`) | **Any** domain event leaving the use case asynchronously. Don't write a `MessagePublisher`. |
| `AuditLog` (`application/audit_log.py`) | Business-meaningful events ops/end-users will read. Don't write a `UserActivityRecorder`. |
| `<Entity>Repository` | All persistence for an entity. Add a method to the existing repo before writing a new abstraction. |

If the new collaborator fits one of these, the answer is: **add a method to the existing one**.

## When a new abstraction IS justified

The collaborator must satisfy all three:

1. **Real external dependency or system primitive.** Calls out of the process **OR** a non-deterministic primitive you must fake in tests.
2. **Not a refinement of an existing role.** "Send a password-reset email" is the existing `EmailSender`, not a new abstraction. "Hash a password with Argon2" *is* new — unrelated to messaging.
3. **The use case would survive a swap.** If you replaced the production binding tomorrow, the use cases must not change. If only one implementation will ever exist and it is library-specific, keep the code concrete in `infrastructure/` — no abstraction needed.

Common legitimate new abstractions:

| Need | Stereotype | Class name |
|---|---|---|
| Send email / SMS / Slack | `Sender` | `EmailSender`, `SmsSender` |
| Call a paid SaaS | `Gateway` | `StripeGateway` |
| Hash / sign / verify | primitive | `PasswordHasher`, `TokenSigner` |
| Read or write blobs | `Reader` / `Writer` | `BlobReader`, `BlobWriter` |
| Cache lookup | `Cache` | `<Entity>Cache` |
| Run something later | `Scheduler` | `Scheduler` |
| Read a feature flag | `Source` | `FeatureFlagSource` |

## Add one — checklist

1. **Abstract** — `application/<role>.py` — `typing.Protocol`, zero third-party imports.
2. **Production binding** — `infrastructure/<role>.py` — prefix by mechanism (`SendGridEmailSender`).
3. **Fake** — `tests/fakes/<role>.py` — inspectable state, faithful invariants.
4. **Container factory** — `infrastructure/container.py` — `build_<role>(settings)`.
5. **`Depends` wrapper** — `presentation/api/dependencies/<noun>.py`.
6. **Settings** — `infrastructure/config/settings.py` — `SecretStr` for credentials.
7. **Conftest fixture** if reused — `tests/conftest.py`.
8. **Integration test** if the production binding does I/O — `tests/integration/infrastructure/test_<role>.py`.
9. **ADR** only when the choice is committing (e.g. "Outbox-backed EventBus over direct broker call").

---

# Testing external HTTP adapters

For an adapter that calls a SaaS we **cannot self-host** (Stripe, Twilio, OpenAI, Auth0, a partner webhook…), testcontainers doesn't help. The canonical pattern for the template is **`respx`** in integration tests. Unit tests still use a Fake (`tests/fakes/<role>.py`); `respx` is *only* for the integration test that exercises the real adapter against intercepted HTTP.

## Why respx, not VCR or pytest-httpx

- **Explicit response shapes** — the test declares what the external API is supposed to return. When the SaaS changes its contract, the test fails on the diff and you see it in PR review. VCR re-records silently and masks the drift.
- **Outbound assertions** — `respx_mock["my_route"].calls.last.request.json()` lets you check the payload your adapter sends, which is the primary thing an integration test for an outbound adapter should verify.
- **Route matchers** — respx has richer route definition than pytest-httpx (URL patterns, header matchers, named routes). For a template that ships generic patterns, the more expressive API ages better.

The honest tradeoff: respx tests don't catch API additions (a new optional field the SaaS started returning that your code now silently ignores). Mitigation belongs in a contract-test workflow that hits the real sandbox on a cron, orthogonal to PR-time tests.

## Already embarked

`respx` is in the template's dev dependencies — use it for any adapter
you write with `httpx`.

## Edge case: third-party libs that bypass httpx

`respx` only intercepts `httpx`. Some third-party libraries make their
own HTTP calls through `urllib` / `requests` / `aiohttp` and respx
cannot see them. The template's `PyJWKClient` (RS256 JWKS fetcher,
shipped by PyJWT) is one such case — it uses `urllib`. The right tool
there is `monkeypatch` on the lib's fetcher boundary:

```python
from jwt import PyJWKClient

def test_...(monkeypatch: pytest.MonkeyPatch) -> None:
    jwks = {"keys": [...]}
    monkeypatch.setattr(PyJWKClient, "fetch_data", lambda _self: jwks)
```

The reference test
`tests/integration/infrastructure/auth/test_jwt_verifier.py::test_given_valid_rs256_token_when_verifying_then_fetches_jwks_and_returns_current_user`
shows the full pattern. Rule of thumb: **if your code uses `httpx`,
respx ; if the lib you depend on uses anything else, monkeypatch the
fetcher.** Never silently let HTTP escape in a test.

## Pattern

```python
# tests/integration/infrastructure/test_stripe_payment_gateway.py
import httpx
import pytest
import respx

from {{ cookiecutter.package_name }}.application.dtos.payment import ChargeInput
from {{ cookiecutter.package_name }}.infrastructure.gateways.stripe_payment_gateway import (
    StripePaymentGateway,
)


@pytest.mark.integration
@respx.mock(base_url="https://api.stripe.com")
async def test_given_valid_charge_when_charging_then_posts_payload_and_returns_charge_id(
    respx_mock: respx.MockRouter,
) -> None:
    # GIVEN: the Stripe sandbox accepts the charge
    route = respx_mock.post("/v1/charges").mock(
        return_value=httpx.Response(200, json={"id": "ch_123", "status": "succeeded"})
    )
    gateway = StripePaymentGateway(api_key="sk_test_xxx", client=httpx.AsyncClient())

    # WHEN
    charge_id = await gateway.charge(ChargeInput(amount_cents=4200, currency="EUR"))

    # THEN: returns the upstream id
    assert charge_id == "ch_123"
    # THEN: sent the expected payload (this is the actual contract being verified)
    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer sk_test_xxx"
    assert route.calls.last.request.content == b"amount=4200&currency=EUR"
```

Two assertions in one test on purpose: the integration test for an outbound adapter is verifying **both** the response parsing AND the request shaping — those are the same contract.

## Failure cases

Each independent failure path is its own test (one test, one reason to fail):

- The SaaS returns a known error code → adapter raises the typed `DomainError`. Mock returns `httpx.Response(402, json={"error": ...})`, test asserts on the raised exception.
- The SaaS is unreachable → `httpx.ConnectError`. respx supports `route.mock(side_effect=httpx.ConnectError("boom"))`. Adapter must wrap it in a `DomainError` (e.g. `PaymentGatewayUnavailableError`).
- The response is malformed → mock returns invalid JSON. Adapter must raise, not silently return `None`.

## Where the Fake lives

Unit tests for the use case never touch respx — they get a `FakeStripePaymentGateway` from `tests/fakes/payment_gateway.py` injected via the container override. The Fake stores submitted charges in a list and accepts `accept_charge(id="ch_test")` / `reject_with(error_code="card_declined")` knobs. The integration test above is the **only** place the real `StripePaymentGateway` runs.

---

# Transactions and events

## Transaction boundary — one HTTP request = one transaction

`presentation/api/dependencies/common.py::get_session` opens both an `AsyncSession` and an outer transaction:

```python
async with factory() as session, session.begin():
    yield session
```

The transaction **commits** when the route handler returns successfully, and **rolls back** on any raised exception — including `DomainError`. So a use case that has done a partial write and then raises leaves the database untouched.

### What this implies for repositories

Call `flush()`, **never** `commit()`. See § 6 above.

### What this implies for use cases

- **No `session.begin()`, no `commit()`, no `rollback()` in `application/`.** The use case never sees transactions.
- **Multiple writes are atomic by default.**
- **Outbox events ride the same transaction.** Calling `events.publish(...)` writes to `outbox_events` via the same session, so the entity write and the event row are atomic.
- **`_instrumented` cooperates** — when the use case raises a `DomainError`, the wrapper logs it at `WARNING` and re-raises; the dependency wrapper rolls back.

### Sub-transactional checkpoints (rare)

If you need a sub-step to fail without aborting the outer transaction:

```python
async with session.begin_nested():
    ...   # this block can fail without aborting the outer transaction
```

## Publishing a domain event

Use cases publish through the `EventBus` protocol. Production binding: `SqlOutboxEventBus` — writes to `outbox_events` **inside the request transaction**. A separate `outbox_relay` worker polls unpublished rows and dispatches to handlers.

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

### Event naming convention

`<aggregate>.<verb_past>` in dotted lowercase: `user.created`, `order.placed`, `payment.refunded`. Aggregate is the noun the event is about; verb is past-tense (the event records a fact, not an intent). Avoid `user.creating` (intent) or `userCreated` (camel).

The payload is a flat `dict[str, Any]` of strings/ints/iso-dates — keep it small and stable, consumers depend on it.

### Handlers

Handlers live in `infrastructure/jobs/event_handlers.py` and register themselves via the `@handler("<event_name>")` decorator:

```python
from {{ cookiecutter.package_name }}.infrastructure.jobs.handlers import handler


@handler("user.created")
async def handle_user_created(payload: dict) -> None:
    """Send a welcome email, warm up a cache, …"""
    ...
```

Multiple handlers per event are allowed — they run sequentially. **At-least-once delivery**: make handlers idempotent.

### Where the swap point is

`infrastructure/jobs/handlers.py::dispatch` is the ONE function to replace when you wire a real broker (Kafka, Pub/Sub, SQS, …). Nothing else in the relay or in use cases changes.

### The relay worker

`infrastructure/jobs/outbox_relay.py` polls `outbox_events`, dispatches to handlers, marks rows published. Multi-replica safe via `SELECT FOR UPDATE SKIP LOCKED`. Backoff schedule with poison after 10 attempts. Metrics: `outbox_events_pending`, `outbox_oldest_pending_age_seconds`, `outbox_handler_failures_total{event_name}`.

For full row lifecycle, backoff schedule, alerting thresholds, and manual replay queries, see `docs/adr/0005-outbox-event-bus.md`.

---

# Idempotency

The `IdempotencyMiddleware` lets clients retry POST/PUT/PATCH/DELETE without double-effects. Clients add the header `Idempotency-Key: <random-uuid>` on retry-eligible writes.

## Outcomes on retry

| Retry with same key… | Server response |
|---|---|
| ...same method + same path, original completed | Original 2xx/4xx response replayed (handler does NOT run again) |
| ...same method + same path, original still in-flight | `409 IDEMPOTENCY_IN_PROGRESS` (retry later) |
| ...different method or path | `422 IDEMPOTENCY_KEY_MISMATCH` |
| ...key TTL elapsed (default 24h) | Treated as a fresh request, handler runs |

## Configuration

| Setting | Default | What it does |
|---|---|---|
| `IDEMPOTENCY_ENABLED` | `true` | Master switch |
| `IDEMPOTENCY_METHODS` | `POST,PUT,PATCH,DELETE` | Methods that opt in |
| `IDEMPOTENCY_TTL_SECONDS` | `86400` (24h) | After this delay a row is recycled |

## Limitations (intentional)

- **No body hash check** — two retries with the same key but different bodies receive the cached response of the first.
- **No automatic cleanup** — ship a CronJob: `DELETE FROM idempotency_records WHERE expires_at < now() - interval '7 days'`.
- **Streaming responses are not cached**.
- **Per-process scoping** — the cache key is the bare `Idempotency-Key` string.
- **Not exercisable via the e2e ``client`` fixture.** The middleware reads `app.state.session_factory` which is wired by the FastAPI lifespan; the e2e fixture deliberately bypasses the lifespan to avoid a real DB engine. So `tests/e2e/api/...` cannot verify replay semantics — they only confirm the endpoint routes correctly. The middleware itself is covered by `tests/integration/middleware/test_idempotency.py` (real Postgres via testcontainers). When you add a new write endpoint, do NOT write an e2e test that sends two requests with the same `Idempotency-Key` expecting the second to be replayed — the middleware will log `idempotency.no_session_factory` and pass through.

## Client-side patterns

- Generate one UUID v4 **per logical action**.
- Do NOT regenerate on retry.
- Discard the key after success.

## Mistakes to avoid

- **Treating the cached response as authoritative state.** A replay returns the *original* response.
- **Using a deterministic key.** Two unrelated requests with the same composite get falsely deduplicated.
- **Returning the cached row from the use case layer.** The middleware handles replay at the presentation boundary.
- **Forgetting the cleanup CronJob in production.**

---

# Anti-patterns for the whole flow

- **Pre-deciding domain pieces in the plan.** Class names, Protocol method names, exception names, entity fields — all emerge from tests.
- **Skipping the question packs.** "I'll just build it" produces a feature whose business rules are wrong, then needs redo.
- **Writing the use case body before the outer test compiles.** That's not TDD; that's typing code while occasionally running tests.
- **Adding a new abstraction without checking the existing ones first.** Most "I need a new port" is a use of an existing one.
- **Writing the persistence binding before the use case is green.** The Protocol contract is the brief; you can't implement what isn't there.
- **Re-testing use case branches at e2e level.** 1 happy + 1 critical only. Branch coverage lives at the unit level.
- **Skipping mutation.** Line coverage without mutation kill rate is a comforting lie.
