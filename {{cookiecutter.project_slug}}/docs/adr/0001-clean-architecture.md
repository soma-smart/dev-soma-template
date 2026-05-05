# 1. Clean Architecture as the project skeleton

Date: 2026-05-05

## Status

Accepted.

## Context

We need a structural pattern that:

1. Keeps business rules independent from frameworks (FastAPI, SQLAlchemy, Pydantic, structlog) so they can evolve at their own pace.
2. Keeps the domain logic testable without I/O — fast unit tests, deterministic outcomes.
3. Has a clear "where do I put this code" answer for every kind of change.
4. Is recognised broadly enough that a new SOMA developer (or Claude) can map their existing knowledge onto it.

## Decision

We adopt **Clean Architecture** (Uncle Bob, strict variant) with four layers: `domain`, `application`, `infrastructure`, `presentation`. The dependency rule is one-way and inward: outer layers know about inner layers, never the reverse.

Specifically:

- `domain` is pure: stdlib only, no `datetime.now()`, no `uuid.uuid4()`, no `random.*`. Non-deterministic side effects are abstracted (`Clock`, `IdGenerator`, `RandomSource`).
- `application` exposes use cases (`…UseCase` classes with an `execute()` method) and the abstractions they depend on. It imports `domain` only.
- `infrastructure` provides concrete implementations of the abstractions — SQLAlchemy repositories, structlog setup, OTel setup, the DI container — and imports both `application` and `domain`.
- `presentation` exposes FastAPI routes, Pydantic schemas, error handlers. It imports `application` and `domain` for types but **never** `infrastructure`. Concretes flow in via the container exposed through `Depends`.

Naming follows Uncle Bob *Clean Code*: no `Manager`/`Helper`/`Service`/`Util`, role-stereotype suffixes (`Repository`, `Gateway`, `Bus`, `Sender`, …) replace the generic `Port` suffix, and the `…UseCase` suffix is kept as a deliberate role marker.

## Consequences

**Positive**:
- Business rules survive a framework migration unchanged.
- Unit tests on `application/` use Fakes only — fast, deterministic, run in milliseconds.
- A new dev only has to learn four buckets to know where everything is.
- Cross-layer leaks are detectable mechanically (`scripts/checks/no_third_party_in_domain.py`).

**Negative**:
- More files than a flat layout. The `User` aggregate spans ~10 files (entity, value object, exception, repo abstract, repo impl, use case, DTOs, schema, route, mapping). The team has decided this is a worthwhile tax.
- Mapping between domain entities and ORM models adds boilerplate. Mitigated by living strictly inside `infrastructure/persistence/` repositories, with private `_to_entity` / `_to_model` helpers.
