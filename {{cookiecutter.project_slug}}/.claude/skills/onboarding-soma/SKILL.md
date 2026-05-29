---
name: onboarding-soma
description: The SOMA manual — Clean Architecture layers, naming conventions, DI container, observability patterns, and the User reference feature. Single source of truth for "how SOMA code is shaped". Use on a fresh session or any time you need to decide where code lives, what to name it, how to wire it, or how to log it.
when_to_use: First session on this repo. "Where does X go?", "what should I name this?", "how do I inject this?", "where should I log?". Editing infrastructure/container.py, infrastructure/observability/, presentation/api/dependencies/. Reviewing layer/naming questions in a PR.
---

# {{ cookiecutter.project_name }} — The SOMA manual

This skill is the consolidated reference for SOMA conventions. It absorbs what used to be four separate skills (layers, naming, DI, observability) plus the project orientation. Use the table of contents to jump.

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [The four layers](#2-the-four-layers)
3. [Where does X go?](#3-where-does-x-go)
4. [The User reference feature](#4-the-user-reference-feature)
5. [Naming conventions (Uncle Bob strict)](#5-naming-conventions-uncle-bob-strict)
6. [The DI container](#6-the-di-container)
7. [Observability patterns](#7-observability-patterns)
8. [Hard rules digest](#8-hard-rules-digest)
9. [Five commands you need first](#9-five-commands-you-need-first)
10. [Where to look next](#10-where-to-look-next)

---

## 1. What this project is

A Python service following **Clean Architecture (Uncle Bob, strict)**:

```
src/{{ cookiecutter.package_name }}/
├── domain/          # entities, value objects, exceptions — stdlib only
├── application/     # use cases + abstractions (Clock, IdGenerator, Repository, EventBus, AuditLog)
├── infrastructure/  # SQLAlchemy, structlog, OTel, DI container — concretes
└── presentation/    # FastAPI routes, schemas, error handlers, middleware
```

Imports flow inward only:

```
presentation  ──→  application  ──→  domain
infrastructure  ─→  application  ──→  domain
```

`presentation` never imports `infrastructure` directly. Concretes are wired through `Depends` against the abstractions in `application/`.

---

## 2. The four layers

| Layer | Responsibility | Imports allowed |
|---|---|---|
| `domain/` | The business model. Entities, value objects, business exceptions. **Pure Python, deterministic.** No third-party libs. No `datetime.now()` / `uuid.uuid4()` / `random.*` — use the abstractions instead. | Python stdlib types only (and other `domain/` modules). |
| `application/` | Orchestration. Use cases composing collaborators to satisfy a request. Defines the **abstractions** (`Clock`, `IdGenerator`, `Repository`, `EventBus`, …) that infrastructure implements. | `domain/` only. |
| `infrastructure/` | Concretes. SQLAlchemy bindings, structlog, OpenTelemetry, HTTP clients, the DI container, configuration, the outbox relay. Translates between the world and the application abstractions. | `domain/`, `application/`, third-party libs. |
| `presentation/` | Delivery. FastAPI routes, Pydantic schemas, error handlers, middleware, health endpoints. Wires concrete dependencies through `Depends` against abstractions. | `application/`, `domain/` (types), third-party (FastAPI, Pydantic). **Never imports `infrastructure/` directly** — concretes flow in via the DI container. |

The dependency rule: **every arrow points inward** (`presentation` → `application` → `domain`; `infrastructure` → `application` → `domain`).

### The Protocol layer = business contract, not technical mapping

A Protocol in `application/` is not a thin wrapper over a SQL table or an HTTP client. Its **method names describe business questions** ("is this name free for this owner?", "give me the unfinished item with this id"), and its **docstrings are the contract** that the persistence binding follows. Two consequences:

- Adding a new method to a Repository Protocol is a deliberate act — done by the use case that needs the question answered, not pre-emptively. See §5 Repository method naming below.
- The persistence binding never invents methods — it implements exactly what the Protocol declares, exactly as the docstring describes.

### Enforcement

The architectural rules are not aspirational. They are checked mechanically:

- `scripts/checks/no_third_party_in_domain.py` — pre-commit + Claude hook + CI
- `scripts/checks/no_naive_datetime.py` — same
- `ty` strict in `ci-quality.yml` — catches type-level layer violations
- Dependency rule expressed as Mermaid in `docs/architecture.md` and rationale in [ADR 0001](../../../docs/adr/0001-clean-architecture.md).

---

## 3. Where does X go?

| Thing | Layer | Folder |
|---|---|---|
| Business rule, invariant | `domain/` | `entities/` or `value_objects/` |
| Value object (Money, Email, Quantity, an ID type, ...) | `domain/` | `value_objects/` (frozen dataclass + `__post_init__`) |
| Entity with identity (User, Order, ...) | `domain/` | `entities/` (regular class, identity-based equality via `Entity[TId]`) |
| Business exception | `domain/` | `exceptions/` (subclass `DomainError`) |
| Use case (orchestration) | `application/` | `use_cases/` (1 file = 1 use case, `…UseCase` suffix, inherits `UseCase[TInput, TOutput]`, public `execute()` method) |
| Abstract repository | `application/` | `repositories/` (inherits `Repository[TEntity, TId]`) |
| `Clock`, `IdGenerator`, `RandomSource`, `EventBus`, `AuditLog` | `application/` | top-level module (`clock.py`, `id_generator.py`, …) |
| New cross-cutting abstraction (`EmailSender`, `Cache`, …) | `application/` | top-level module — but check `building-a-feature` § "Adding a new abstraction" first |
| `…Input` / `…Output` DTOs | `application/` | `dtos/` (frozen dataclass) |
| SQLAlchemy ORM model | `infrastructure/` | `persistence/models/` (suffix `…Model`) |
| Concrete repository | `infrastructure/` | `persistence/<entity>_repository.py` (prefix by mechanism: `SqlAlchemy…`) |
| HTTP client wrapping a SaaS | `infrastructure/` | `http_clients/<vendor>.py` |
| OTel + structlog setup | `infrastructure/` | `observability/` |
| Pydantic `Settings` | `infrastructure/` | `config/settings.py` |
| DI container (factories) | `infrastructure/` | `container.py` |
| Outbox bus + model | `infrastructure/` | `outbox.py`, `persistence/models/outbox_event.py` |
| Background workers | `infrastructure/` | `jobs/<role>.py` (e.g., `outbox_relay.py`) |
| FastAPI app factory | `presentation/` | `api/app.py` |
| Versioned router | `presentation/` | `api/v1/<resource>.py` |
| Pydantic request/response schema | `presentation/` | `api/schemas/` (suffix `…Schema`) |
| Middleware | `presentation/` | `api/middleware/` |
| `Depends` factory wiring the container | `presentation/` | `api/dependencies/` |
| `DomainError` → HTTP status mapping | `presentation/` | `api/error_handlers.py` (`ERROR_HTTP_MAPPING`) |
| Fake of an abstraction (test double) | `tests/fakes/` | `tests/fakes/<role>.py` (or `tests/fakes/repositories/<entity>.py`) |
| Alembic revision | `alembic/versions/` | `<NNNN>_<short_name>.py` (with non-empty `downgrade()`) |

### Where does X NOT go?

| Anti-pattern | Why | Where it should live instead |
|---|---|---|
| `import sqlalchemy` in `application/use_cases/` | leaks persistence into orchestration | repository abstraction in `application/repositories/`, concrete in `infrastructure/` |
| `import fastapi` in `application/` | leaks delivery into orchestration | use case takes a DTO; FastAPI lives in `presentation/` |
| `import pydantic` in `domain/` | third-party in domain | value objects use `@dataclass(frozen=True, slots=True)` |
| `datetime.now()` in `domain/application/` | non-determinism breaks tests | inject `Clock`, call `clock.now()` |
| `uuid.uuid4()` in `domain/application/` | same | inject `IdGenerator`, call `ids.new()` |
| `raise HTTPException(...)` in `application/` | mixes HTTP into orchestration | raise a `DomainError` subclass; map to HTTP in `presentation/api/error_handlers.py` |
| `from {pkg}.infrastructure...` in `presentation/` | bypasses DI | inject via `Depends(get_*)` from `presentation/api/dependencies/` |
| `logger.info(...)` in `domain/application/` | logging is an infrastructure concern | log at the boundary (`infrastructure/`, middleware, error handler) |
| `float` for monetary or precise quantities in `domain/` | precision loss | `decimal.Decimal` |
| `class UserManager`, `class UserHelper`, `class UserService` | meaningless suffixes | apply naming below — pick a role stereotype |

---

## 4. The User reference feature

The codebase ships a working SSO-backed user-provisioning flow that
threads all four layers end to end:

- `GET /v1/users/me` — the only user endpoint. The handler depends on
  `get_or_provision_user`, which chains JWT verification with
  `EnsureUserExistsUseCase`. On the first authenticated request for a
  JWT subject, a `User` row is created from the JWT claims (``email``
  + ``name``); subsequent calls return the existing row.

**Read these files** before adding your first feature — copy the
pattern (there is intentionally NO `POST /v1/users` — provisioning
happens lazily via SSO):

| Layer | File |
|---|---|
| domain | `domain/value_objects/email.py`, `domain/value_objects/user_id.py` |
| domain | `domain/entities/user.py` (carries the `subject` field — IdP `sub` claim) |
| domain | `domain/exceptions/user.py` (`UserAlreadyExistsError`, `UserNotFoundError`) |
| domain | `domain/exceptions/auth.py` (`MissingProfileClaimsError` — JWT lacks email/name) |
| application | `application/auth/current_user.py` (`CurrentUser` VO, JWT claims projection) |
| application | `application/repositories/user.py` (Protocol — `find_by_subject` is the primary lookup) |
| application | `application/dtos/user.py` (`EnsureUserExistsInput` / `EnsureUserExistsOutput`) |
| application | `application/use_cases/ensure_user_exists.py` (idempotent find-or-create) |
| infrastructure | `infrastructure/persistence/models/user.py` (`UserModel` — `subject` UNIQUE) |
| infrastructure | `infrastructure/persistence/user_repository.py` (`SqlAlchemyUserRepository`) |
| infrastructure | `infrastructure/auth/jwt_verifier.py` (HS256/RS256, JWKS) |
| infrastructure | `infrastructure/container.py` (`build_user_repository`, `build_ensure_user_exists_use_case`) |
| presentation | `presentation/api/schemas/user.py` (`UserReadSchema`) |
| presentation | `presentation/api/dependencies/users.py` (`get_or_provision_user` chain) |
| presentation | `presentation/api/dependencies/auth.py` (`HTTPBearer` / `OAuth2AuthorizationCodeBearer` scheme, role checks) |
| presentation | `presentation/api/v1/users.py` (`GET /v1/users/me` router) |
| presentation | `presentation/api/error_handlers.py` (the `ERROR_HTTP_MAPPING` entries) |
| tests | `tests/unit/domain/test_user.py` + `test_email.py` |
| tests | `tests/unit/use_cases/test_ensure_user_exists.py` |
| tests | `tests/integration/infrastructure/test_user_repository.py` |
| tests | `tests/e2e/api/test_users_me_endpoint.py` |
| tests | `tests/fakes/repositories/user.py` (`InMemoryUserRepository`) + `tests/fakes/auth.py` (`FakeTokenVerifier`) |

Migration: `alembic/versions/0001_init.py` (initial schema — creates `users`
alongside `outbox_events` and `idempotency_records`; `users.subject` is UNIQUE).

If the project does not need a user notion at all, remove the feature
cleanly (entity, use case, repo binding, route, schema, migration,
tests). The auth chain (`get_current_user`, `require_roles`) is
independent and stays useful for projects that protect routes without
mapping to a persisted `User` row.

---

## 5. Naming conventions (Uncle Bob strict)

### Universal rules

- **Intention-revealing.** No abbreviations: `usr`, `cnt`, `tmp`, `repo` (in identifiers), `cfg`, `mgr`. Exceptions: well-known short forms (`db`, `id`, `url`, `http`).
- **No type encodings.** No `I` prefix on interfaces. No Hungarian (`strName`). No `m_` prefix.
- **One word per concept** — pick a verb and stick with it project-wide.
- **Booleans**: `is_*`, `has_*`, `can_*`. Never negative (`is_not_empty` → negate `is_empty` at the call site).
- **Names should not lie.** A field called `users` returns a `list[User]`, not a `dict[UserId, User]`. A method `get_user` returns one user, not raises if missing — `find_user` is the one that may return `None`.

### Verb cheat sheet (one word per concept)

| Concept | Verb | Counter-examples (avoid mixing) |
|---|---|---|
| Local lookup, must succeed | `get_<noun>` | `fetch_user`, `retrieve_user` |
| Lookup that may miss | `find_<noun>` | `lookup_user`, `try_get_user` |
| I/O-bound load (DB, HTTP) | `load_<noun>` | `read_user_from_db` |
| Add a new entity to a collection / store | `add(<entity>)` | `insert_user`, `register_user` (when "register" carries no business meaning) |
| Domain registration with a process | `register_<noun>` | use only when registration is a real domain step |
| Create-and-return a fresh instance | `create_<noun>` | use cases follow this for `CreateOrderUseCase`, `CreateTodoListUseCase`, … |
| Remove without history | `delete_<noun>` | |
| Mark inactive while keeping the row | `archive_<noun>` / `deactivate_<noun>` | |
| Pull collection by criterion | `find_<noun>s_by_<field>` | not `get_users_where`, not `list_users_for` |
| Test exists | `<noun>_exists(...)` returning `bool` | not `has_user` if it implies ownership |

### Banned generic class names

`Manager`, `Processor`, `Handler` (except framework types like `RequestHandler`), `Service` (everything is a service in Clean Architecture — too generic), `Helper`, `Util`, `Data`, `Info`, `Common`, `Misc`, `Worker` (allowed only when paired with a job runner: `OutboxRelayWorker`).

If you find yourself reaching for one of these, the actual role is hiding under it — pick a stereotype below.

### Role-stereotype whitelist

When naming a **Protocol** (the application-layer contract), prefer one of these suffixes — they replace the `Port` suffix:

| Stereotype | Use |
|---|---|
| `…Repository` | Persistence of an entity (CRUD + queries) |
| `…Gateway` | Façade over an external SaaS (Stripe, SendGrid, …) |
| `…Bus` | Pub/sub or message routing |
| `…Sender` / `…Publisher` / `…Subscriber` | Outbound / inbound message roles |
| `…Generator` | Produces values (often unique) |
| `…Source` | Pure data provider (random, config, time series) |
| `…Provider` | Lazy resource provider |
| `…Reader` / `…Writer` | I/O over a medium |
| `…Factory` | Builds complex objects |
| `…Strategy` | Interchangeable algorithm |
| `…Validator` | Input validation |
| `…Cache` | Cache storage |
| `…Log` | Writes structured log entries |
| `Clock` / `Lock` / `Mutex` | System primitives (single word) |

`…Port` is the **last-resort** suffix when none of the above fits. Document why in the docstring.

### Concrete implementations

Prefix by mechanism. Reads as "this is the X-flavoured implementation of role Y":

| Abstract role | Production binding | Test Fake |
|---|---|---|
| `UserRepository` | `SqlAlchemyUserRepository` | `InMemoryUserRepository` |
| `Clock` | `SystemClock` | `FrozenClock` |
| `IdGenerator` | `Uuid4IdGenerator` | `SequentialIdGenerator` |
| `RandomSource` | `SystemRandomSource` | `SeededRandomSource` |
| `EmailSender` | `SendGridEmailSender` | `InMemoryEmailSender` |
| `EventBus` | `SqlOutboxEventBus` | `InMemoryEventBus` (when written) |

### Suffixes that ARE kept on purpose

- **Use cases** — `…UseCase` (`EnsureUserExistsUseCase`, `CreateOrderUseCase` — never bare `CreateOrder`). Deliberate role marker, makes the layer obvious.
- **Errors** — `…Error` (`UserAlreadyExistsError`). `…Exception` only on stdlib subclasses.
- **Pydantic schemas (presentation)** — `…Schema` (`UserCreateSchema`, `ErrorResponseSchema`).
- **SQLAlchemy models (infrastructure)** — `…Model` (`UserModel`). Disambiguates from the domain `User`.

### Repository method naming — methods are business questions

The base `Repository[TEntity, TId]` Protocol ships only the two truly generic methods: `add(entity)` and `find_by_id(id)`. Every other method on a sub-Protocol (e.g. `TodoListRepository`, `UserRepository`) is **added by the use case that needs it**, and its **name must describe a business question, not a SQL operation**. The docstring is the contract — it explains the filter semantics so the persistence binding can implement the right `WHERE` without guessing.

#### Anti-pattern table

| ❌ Tech-flat | ✅ Business-shaped | Why |
|---|---|---|
| `get_by_owner(owner_id)` | `list_owned_by(owner_id)` | Verb says "give me all", and `list_*` signals a collection result, not a single row |
| `get_by_id_and_owner(id, owner_id)` | `find_owned_by(owner_id, id)` | The "owned-by" check is the business intent, not a `WHERE owner_id = ? AND id = ?` filter |
| `get_by_name(name)` | `find_active_by_owner_and_name(owner_id, name)` | The active filter is part of the contract (excludes soft-deleted); also scopes by owner because globally unique names rarely make sense |
| `update_email(id, new_email)` | `record_email_change(user, new_email)` | The operation has a business meaning (audit trail, event emission) that the method name should evoke |
| `delete(id)` | `archive(id)` (soft) or `purge(id)` (hard) | Distinguishes two real domain operations under one CRUD verb |
| `check_exists(email)` | `is_email_taken(email)` | Question business, not technical check |
| `count(filter)` | `count_pending_for_owner(owner_id)` | Names the subset being counted; readers don't need to inspect the filter |
| `find_recent(limit)` | `find_recently_active_by_owner(owner_id, since)` | "Recent" without a window is undefined; "by_owner" makes the scope explicit |

#### The contract = the docstring

The Protocol's docstring on each method is the **only** brief the persistence binding has. It must cover:

- What the method returns when the row doesn't exist (`None` vs. empty list vs. raise)
- Which rows are filtered out (soft-deleted? archived? draft state?)
- Whether the result is ordered (and by what)
- Which other Protocol method, if any, this one complements

Example of a complete contract:

```python
class TodoListRepository(Repository[TodoList, TodoListId], Protocol):
    """Persistence contract for the TodoList aggregate.

    Methods carry the ubiquitous language of TodoList ownership and lifecycle.
    """

    async def find_active_by_owner_and_name(
        self, owner_id: UserId, name: str
    ) -> TodoList | None:
        """Return the non-deleted list named ``name`` owned by ``owner_id``.

        Used by CreateTodoListUseCase for the uniqueness check before creation.
        Soft-deleted lists are ignored — re-creating a list with the same name
        after deletion is permitted. Returns ``None`` when no active list matches.
        """
        ...
```

If a use case needs `find_by_id` (without a state filter), use the inherited one. The moment the question carries a state filter ("the active one with this id"), prefer a named method.

#### Bad smell: a Repository that looks like an ORM

If the Repo has methods like `find_by_X(value)` for every field, you've recreated a generic `Repository[Entity].query(field=value)`. That's a sign the use cases are too thin. Push business intent INTO the Repo method names.

### Variables and function arguments

- `email`, not `email_address` — context already says it's an address.
- `user`, not `user_object` — `_object` is noise.
- `user_id` is good; `id` alone is fine inside a class method when the type is clear.
- Plural for collections: `users: list[User]`, never `user_list`.
- Use the **Protocol** type for parameters, the **concrete** for locals when the difference matters: `def create(self, repo: UserRepository) -> None:` but `repo = SqlAlchemyUserRepository(session)`.

### File and folder names

- Snake_case Python files.
- **Plural** for collections: `use_cases/`, `entities/`, `repositories/`, `value_objects/`, `dtos/`.
- **Singular** for concept modules: `clock.py`, `container.py`, `app.py`, `outbox.py`.

#### Group by aggregate when the kind folder has 3+ files for it

Each Clean-Architecture layer is split first by **kind** (use_cases, entities, value_objects, dtos, repositories, schemas, models, …) — that part is non-negotiable. When the same **aggregate** has **3 or more** files inside one kind folder, group them into a sub-folder named after the aggregate (snake_case), and **drop the aggregate prefix from the filenames inside**.

```
application/use_cases/
  ensure_user_exists.py                # 1 use case for User → flat
  todo_list/                           # 4 use cases for TodoList → grouped
    __init__.py
    create.py
    get.py
    list.py
    delete.py

domain/value_objects/
  email.py
  user_id.py
  todo_list/
    __init__.py
    name.py
    description.py
    todo_list_id.py

application/dtos/
  user.py                              # one DTO module → flat
  todo_list/                           # 3+ DTOs → grouped
    create_input.py
    update_input.py
    view.py

presentation/api/schemas/
  user.py
  todo_list/
    create_request.py
    update_request.py
    view_response.py
```

Where it usually does **not** apply (one file per aggregate is the norm):

- `domain/entities/<aggregate>.py` — one entity per aggregate.
- `application/repositories/<aggregate>.py` — one Protocol per aggregate.
- `presentation/api/v1/<aggregate>s.py` — one router per aggregate.
- `infrastructure/persistence/models/<aggregate>.py` — one ORM model per aggregate.

Thresholds:

- **< 3 files** for the aggregate in that kind → keep them flat with the aggregate in the filename (`create_user.py`).
- **≥ 3 files** → create the sub-folder. Promote existing files into it in the same edit (no half-state).
- The threshold is per kind folder, not project-wide. `domain/value_objects/todo_list/` can exist while `application/use_cases/` keeps `todo_list/` flat if there are only 2 use cases.

Aggregate sub-folders ship an `__init__.py`. Names inside follow the **verb-only** convention (`create.py`, `get.py`) so the import reads `from .use_cases.todo_list import create` — the aggregate is carried by the folder.

### Tests

- File: `test_<sut_name>.py` mirroring the source layout (`tests/unit/use_cases/test_ensure_user_exists.py`).
- Function: `test_given_<context>_when_<action>_then_<expectation>`.
- Body format (GIVEN / WHEN / THEN comments): see `tdd-workflow`.

### Constants

- `SCREAMING_SNAKE_CASE` for module-level constants (`DEFAULT_RETENTION_DAYS = 30`).
- Group related constants in a `constants.py` per module (`presentation/api/constants.py`).
- Class-level constants (a `ClassVar`) when they belong to one type — e.g. `DomainError.code`.
- Magic numbers in code are flagged by `ruff PLR2004`. Lift them to a named constant.

---

## 6. The DI container

The container is **pure factory functions** in `infrastructure/container.py`. No DI framework, no magic — just functions that build concrete instances. FastAPI `Depends` wraps each factory in `presentation/api/dependencies/`. Tests override at the `Depends` layer with `app.dependency_overrides`.

This is the **only** seam between `application/` (abstractions) and `infrastructure/` (concretes). Anywhere else, importing from `infrastructure/` in `presentation/` is a layer violation.

### Factories shipped

| Factory | Returns |
|---|---|
| `build_clock()` | `Clock` (production: `SystemClock`) |
| `build_id_generator()` | `IdGenerator` (`Uuid4IdGenerator`) |
| `build_random_source()` | `RandomSource` (`SystemRandomSource`) |
| `build_database(settings)` | `(AsyncEngine, async_sessionmaker)` |
| `build_user_repository(session)` | `UserRepository` (`SqlAlchemyUserRepository`) |
| `build_event_bus(session)` | `EventBus` (`SqlOutboxEventBus`) |
| `build_ensure_user_exists_use_case(*, users, clock, ids, events)` | `EnsureUserExistsUseCase` wrapped with `_instrumented` |

Matching `Depends` in `presentation/api/dependencies/`: `get_settings_dependency`, `get_session`, `get_clock`, `get_id_generator`, `get_random_source` (in `common.py`); `get_user_repository`, `get_ensure_user_exists_use_case`, `get_or_provision_user` (in `users.py`); `get_current_user`, `require_roles`, the security scheme (in `auth.py`).

### Adding a new factory

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

Every use case factory **must** wrap with `_instrumented(span_name=...)`. The wrapper:

- opens an OTel span around `execute`
- logs `DomainError` raises at `WARNING` with `code` + `context`
- logs unexpected exceptions at `ERROR` with the full stack trace
- re-raises in all cases (the presentation layer maps the exception to HTTP)

This is **the** reason `application/` never imports structlog or OpenTelemetry: the wrapper bolts cross-cutting concerns on from the outside.

Factory rules:

- **Pure** — no I/O, no globals (settings flow in as a parameter when needed).
- **Synchronous** unless it has to be async — only `get_session` is async.
- **Composable** — a use case factory takes the repo factory's output as a typed parameter, not a raw `AsyncSession`. The `Depends` wrapper handles the chain.

### Adding the `Depends` wrapper

`presentation/api/dependencies/<noun>.py`:

```python
def get_<noun>_repository(
    session: AsyncSession = Depends(get_session),
) -> <Noun>Repository:
    return build_<noun>_repository(session)


def get_<action>_<noun>_use_case(
    <noun>s: <Noun>Repository = Depends(get_<noun>_repository),
    clock: Clock = Depends(get_clock),
    ids: IdGenerator = Depends(get_id_generator),
) -> <Action><Noun>UseCase:
    return build_<action>_<noun>_use_case(<noun>s=<noun>s, clock=clock, ids=ids)
```

### Tests override at the `Depends` layer

The e2e fixture in `tests/e2e/conftest.py::app` already pre-wires the in-memory Fakes for User. Most e2e tests need no override. For custom ones:

```python
async def failing_session() -> AsyncIterator[AsyncSession]:
    yield StubAsyncSession(raises=OperationalError("db down", params=None, orig=None))


def test_given_db_unreachable_when_calling_ready_then_returns_503(app, client) -> None:
    # GIVEN
    app.dependency_overrides[get_session] = failing_session

    # WHEN
    response = client.get("/health/ready")

    # THEN
    assert response.status_code == 503
```

Override the `Depends` you want to swap, leave everything else inherited from the fixture.

### Anti-patterns

| Wrong | Right |
|---|---|
| `from {pkg}.infrastructure.persistence.user_repository import SqlAlchemyUserRepository` in a route | `Depends(get_user_repository)` |
| `Depends(SqlAlchemyUserRepository)` directly | depend on `get_user_repository` |
| `build_*_use_case` returns the use case **without** `_instrumented(...)` | always wrap; observability stays out of `application/` |
| Use case takes `Settings` as a constructor parameter | factories read from `Settings`, the use case takes the abstractions only |
| Test mutates a fixture in place across tests | overrides go on the per-test `app.dependency_overrides` |
| `Depends(lambda: build_user_repository(...))` inline in a route | declare a `get_user_repository` in `presentation/api/dependencies/` |

---

## 7. Observability patterns

Four observability surfaces, each with strict rules about where it can appear.

### 7.1 Structured logs (structlog)

#### Where you can log

| Layer | Allowed? | Why |
|---|---|---|
| `domain/` | NO | The domain is silent. Surface state changes via typed exceptions. |
| `application/` | NO | Use cases stay pure for testability. Cross-cutting log lines are added by `_instrumented`. |
| `infrastructure/` | YES | Boundary I/O is logged where it happens. |
| `presentation/` | YES | Error handlers and request middleware emit access logs and error events. |

If a use case feels like it "needs a log", the right answer is almost always:

- a typed `DomainError` (business event) — the wrapper logs it at WARNING automatically.
- an `AuditLog.record(...)` call (user-facing event) — see `application/audit_log.py`.

#### Logger API

```python
import structlog

logger = structlog.get_logger(__name__)

logger.info("user.created", user_id=str(user.id), email=str(user.email))
logger.warning("payment.declined", reason=reason, attempt=attempt)
logger.exception("unexpected_error", path=path)
```

- **Event-style.** First positional arg is a dot-separated event name (`<noun>.<verb_past>`), same convention as domain events.
- **Structured kwargs, never f-strings.** The renderer JSON-encodes in prod, pretty-prints in dev.
- **Sensitive keys redacted automatically.** The `_redact_secrets` processor replaces any key matching `password`, `token`, `authorization`, `secret`, `api_key` (case-insensitive substring) with `***`.

#### Format switch — dev vs prod

`LOG_FORMAT` env var:

| Value | Renderer | Use |
|---|---|---|
| `console` (default in dev) | `structlog.dev.ConsoleRenderer` with colours | terminal-readable |
| `json` (default in prod) | `structlog.processors.JSONRenderer` | one JSON line per event |

### 7.2 Tracing (OpenTelemetry)

#### Auto-instrumentation, shipped

The `configure_tracing` call at app startup wires:

- `opentelemetry-instrumentation-fastapi` — one span per HTTP request, W3C TraceContext propagation
- `opentelemetry-instrumentation-sqlalchemy` — DB spans
- `opentelemetry-instrumentation-asyncpg` — connection-level spans
- `opentelemetry-instrumentation-httpx` — outgoing HTTP calls + trace headers propagation
- `opentelemetry-instrumentation-logging` — `trace_id` and `span_id` injected into structlog events

No code in `application/` or `domain/` touches OTel.

#### Use case spans — via the container, not a decorator

Every use case built by the container goes through `_instrumented(use_case, span_name="...")`. **Do NOT** put `@traced` on the use case class — that would force `application/` to import from `infrastructure/observability/`, a layer violation.

#### Custom spans inside infrastructure

`@traced` is fine **inside `infrastructure/`**:

```python
from {{ cookiecutter.package_name }}.infrastructure.observability import traced


@traced("user_repository.find_inactive")
async def find_inactive(self, before: datetime) -> list[User]:
    ...
```

Add attributes via `trace.get_current_span().set_attribute(...)` only when the value is **bounded and meaningful** — do not dump full payloads.

#### Exporter switching

| `OTEL_EXPORTER_OTLP_ENDPOINT` | Behaviour |
|---|---|
| unset | spans go to stdout via `ConsoleSpanExporter` — dev default, CI default |
| set to a URL | OTLP gRPC export to the configured collector |

The devcontainer ships an OTel collector at `http://otel-collector:4317` that forwards to Jaeger; UI on `http://localhost:16686`.

### 7.3 Metrics (Prometheus)

`prometheus-fastapi-instrumentator` exposes `/metrics` (not in the OpenAPI schema). Out of the box:

- HTTP request count + duration histogram + in-progress gauge, per `(method, handler, status)`
- Process metrics (CPU, memory, fds, uptime)

`/metrics` and `/health/*` are excluded from instrumentation. The Helm chart ships a `ServiceMonitor` (gated by `metrics.enabled`).

Custom metrics go in `infrastructure/observability/metrics.py`. Define counters / histograms at module load, label them by low-cardinality tuples, increment from infrastructure code.

### 7.4 Request correlation

Every HTTP request gets `X-Request-ID`:

- If the caller sent one, it is preserved.
- Otherwise `RequestIdMiddleware` generates a UUID4 hex.

The id is bound to the structlog context, so every log line during the request carries `request_id=<uuid>`. The response echoes it back.

`AccessLogMiddleware` emits one `http.request` event per non-health-check request with method, path, status, duration_ms, client.

### Observability anti-patterns

| Wrong | Right |
|---|---|
| `print(...)` | use structlog; `print` is caught by ruff `T20` |
| `logging.getLogger(__name__).info(...)` | `structlog.get_logger(__name__).info(...)` |
| `logger.info(f"user {user.id} created")` | `logger.info("user.created", user_id=str(user.id))` |
| Logging inside a use case "for visibility" | raise a typed `DomainError` or call `AuditLog.record(...)` |
| `@traced` on a use case class | wrap in the container with `_instrumented` |
| Span attribute with the full request payload | bounded, low-cardinality values only |

---

## 8. Hard rules digest

1. **TDD red first.** Every line of production code is justified by a failing test. See `tdd-workflow`.
2. **No mocks in unit tests** — only Fakes from `tests/fakes/`.
3. **No third-party imports in `src/<pkg>/domain/`** — not even `datetime.now()`, `uuid.uuid4()`, `random.*`.
4. **No log in `domain/` or `application/`**.
5. **No HTTP types in `application/` or `domain/`** — exceptions are `DomainError` subclasses.
6. **GIVEN/WHEN/THEN strict** in unit and integration tests.
7. **Conventional commits**, no `--no-verify`, no force push.
8. **Function ≤ 25 lines.** Cyclomatic complexity ≤ 10.
9. **`Decimal` for money**, **TZ-aware datetimes** stored UTC.
10. **No `Manager`, `Helper`, `Util`, `Service`** generic class names.

---

## 9. Five commands you need first

The project uses `just` as command runner — pre-installed in the devcontainer. Type `just` to list every recipe.

```bash
just install     # uv sync --group dev
just dev         # FastAPI with auto-reload
just test        # fast unit tests (-x -q)
just test-all    # unit + integration + e2e (Docker required for integration)
just mutate      # mutation testing on domain + application
```

---

## 10. Where to look next

- **`CLAUDE.md`** at the repo root — the routing table from prompts to skills (auto-loaded every session).
- **`docs/architecture.md`** — Mermaid diagrams of the layers + a request sequence diagram.
- **`docs/adr/`** — ADRs documenting the structural choices (clean architecture, TDD + mutation, fakes-only, transaction boundary, outbox).
- **`docs/runbooks/`** — operator playbooks: `backups-and-restore.md`, `disaster-recovery.md`, `verification-log.md`. Open these before debugging an incident.
- **`.claude/skills/`** — other skills:
  - `tdd-workflow` — outside-in TDD, Fakes, GIVEN/WHEN/THEN, mutmut
  - `building-a-feature` — end-to-end runbook (plan → use case → persistence → route → wiring)
  - `writing-domain-code` — domain purity + exceptions
  - `database-and-migrations` — Alembic, schema changes
  - `adding-auth` — JWT + role guard
  - `event-sourcing-pattern` — when to ES, how to bootstrap
  - `writing-a-helm-change` — chart edits + lint
  - `reviewing-a-pr-soma-style` — PR review checklist
