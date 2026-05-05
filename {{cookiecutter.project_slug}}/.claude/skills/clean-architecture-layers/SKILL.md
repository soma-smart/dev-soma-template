---
name: clean-architecture-layers
description: Authoritative rules for layer boundaries and the import direction. Use whenever you need to decide where a piece of code goes or whether an import is allowed.
when_to_use: Deciding where new code lives; reviewing imports; designing a use case; refactoring across layers.
---

# Clean Architecture layers

## The four layers

| Layer | Knows about | Can NOT import |
|---|---|---|
| `domain/` | Python stdlib only — and even there, no non-deterministic side effects (`datetime.now()`, `uuid.uuid4()`, `random.*` are forbidden). Use the `Clock`, `IdGenerator`, `RandomSource` abstractions. | Anything third-party. Anything from `application/`, `infrastructure/`, `presentation/`. |
| `application/` | `domain/` only | `infrastructure/`, `presentation/`, third-party libs (in general — Pydantic, structlog, etc. live in `infrastructure/`/`presentation/`). |
| `infrastructure/` | `domain/` and `application/` | `presentation/`. |
| `presentation/` | `application/` and `domain/` (types only) | `infrastructure/` directly — pull concretes via the DI container. |

## Where does X go?

| Thing | Layer | Folder |
|---|---|---|
| Business rule, invariant | `domain/` | `entities/` or `value_objects/` |
| Money, Email, Quantity | `domain/` | `value_objects/` (frozen dataclass + `__post_init__`) |
| Aggregate with identity | `domain/` | `entities/` (regular class, identity-based equality) |
| Business exception | `domain/` | `exceptions/` (subclass `DomainError`) |
| Use case (orchestration) | `application/` | `use_cases/` (one file per use case, `…UseCase` suffix, `execute()` method) |
| Abstract repository | `application/` | `repositories/` |
| `Clock`, `IdGenerator`, etc. | `application/` | top-level module (`clock.py`, `id_generator.py`) |
| `…Input` / `…Output` DTO | `application/` | `dtos/` |
| SQLAlchemy model | `infrastructure/` | `persistence/models/` |
| Concrete repository | `infrastructure/` | `persistence/<entity>_repository.py` |
| HTTP client | `infrastructure/` | `http_clients/` |
| OTel / logging setup | `infrastructure/` | `observability/` |
| Pydantic Settings | `infrastructure/` | `config/` |
| FastAPI router | `presentation/` | `api/v1/` |
| Pydantic Schema | `presentation/` | `api/schemas/` |
| Middleware | `presentation/` | `api/middleware/` |
| `Depends` factory | `presentation/` | `api/dependencies/` |
| Fake of an abstraction | `tests/fakes/` | `tests/fakes/...` |

## Enforcement

- `scripts/checks/no_third_party_in_domain.py` runs in pre-commit, in the Claude `audit-edit.sh` hook, and in CI.
- The dependency direction is also documented in `docs/architecture.md` and ADR-0001.
