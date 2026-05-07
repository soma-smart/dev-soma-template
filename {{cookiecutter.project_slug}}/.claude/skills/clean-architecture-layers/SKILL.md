---
name: clean-architecture-layers
description: Authoritative rules for layer boundaries, what each layer is responsible for, the import direction, and where every kind of file goes. Use whenever you need to decide where new code lives or whether an import is allowed.
when_to_use: Designing a new feature; reviewing an import; refactoring across layers; "where does this go?" questions; deciding if a class is in the right module.
---

# Clean Architecture layers

## What each layer is for

| Layer | Responsibility | Imports allowed |
|---|---|---|
| `domain/` | The business model. Entities, value objects, business exceptions. **Pure Python, deterministic.** No third-party libs. No `datetime.now()` / `uuid.uuid4()` / `random.*` — use the abstractions instead. | Python stdlib types only (and other `domain/` modules). |
| `application/` | Orchestration. Use cases composing collaborators to satisfy a request. Defines the **abstractions** (`Clock`, `IdGenerator`, `Repository`, `EventBus`, …) that infrastructure implements. | `domain/` only. |
| `infrastructure/` | Concretes. SQLAlchemy bindings, structlog, OpenTelemetry, HTTP clients, the DI container, configuration, the outbox relay. Translates between the world and the application abstractions. | `domain/`, `application/`, third-party libs. |
| `presentation/` | Delivery. FastAPI routes, Pydantic schemas, error handlers, middleware, health endpoints. Wires concrete dependencies through `Depends` against abstractions. | `application/`, `domain/` (types), third-party (FastAPI, Pydantic). **Never imports `infrastructure/` directly** — concretes flow in via the DI container. |

The dependency rule: **every arrow points inward** (`presentation` → `application` → `domain`; `infrastructure` → `application` → `domain`). For the deeper rules on what `domain/` may contain, see `writing-domain-code`.

## Where does X go?

| Thing | Layer | Folder |
|---|---|---|
| Business rule, invariant | `domain/` | `entities/` or `value_objects/` |
| Value object (Money, Email, Quantity, an ID type, ...) | `domain/` | `value_objects/` (frozen dataclass + `__post_init__`) |
| Entity with identity (User, Order, ...) | `domain/` | `entities/` (regular class, identity-based equality via `Entity[TId]`) |
| Business exception | `domain/` | `exceptions/` (subclass `DomainError`) |
| Use case (orchestration) | `application/` | `use_cases/` (1 file = 1 use case, `…UseCase` suffix, inherits `UseCase[TInput, TOutput]`, public `execute()` method) |
| Abstract repository | `application/` | `repositories/` (inherits `Repository[TEntity, TId]`) |
| `Clock`, `IdGenerator`, `RandomSource`, `EventBus`, `AuditLog` | `application/` | top-level module (`clock.py`, `id_generator.py`, `random_source.py`, `event_bus.py`, `audit_log.py`) |
| New cross-cutting abstraction (`EmailSender`, `Cache`, …) | `application/` | top-level module — **but read `adding-a-new-abstraction` first to confirm an existing one does not cover it** |
| `…Input` / `…Output` DTOs | `application/` | `dtos/` (frozen dataclass) |
| SQLAlchemy ORM model | `infrastructure/` | `persistence/models/` (suffix `…Model`) |
| Concrete repository | `infrastructure/` | `persistence/<entity>_repository.py` (prefix by mechanism: `SqlAlchemy…`) |
| Async session / engine | `infrastructure/` | `persistence/session.py` |
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
| Health probe endpoints | `presentation/` | `api/health.py` |
| Fake of an abstraction (test double) | `tests/fakes/` | `tests/fakes/<role>.py` (or `tests/fakes/repositories/<entity>.py`) |
| Alembic revision | `alembic/versions/` | `<NNNN>_<short_name>.py` (with non-empty `downgrade()`) |

## Where does X NOT go?

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
| `class UserManager`, `class UserHelper`, `class UserService` | meaningless suffixes | apply `naming-conventions` — pick a role stereotype |

## Enforcement

The architectural rules are not aspirational. They are checked mechanically:

* `scripts/checks/no_third_party_in_domain.py` — pre-commit + Claude hook + CI
* `scripts/checks/no_naive_datetime.py` — same
* `scripts/checks/no_float_in_domain.py` — same
* `ty` strict in `ci-quality.yml` — catches type-level layer violations
* The dependency rule is also expressed as Mermaid in `docs/architecture.md` and rationale in [ADR 0001](../../../docs/adr/0001-clean-architecture.md).
