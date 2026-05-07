---
name: onboarding-soma
description: First-session orientation for {{ cookiecutter.project_name }}. Use on a fresh Claude Code session on this repo or when the user asks for a tour, project overview, or "where do I start".
when_to_use: First session on the repo; user asks for an overview; user is exploring the codebase before any action.
---

# {{ cookiecutter.project_name }} — Onboarding

## What this project is

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

## The User reference feature

The codebase ships a working `POST /v1/users` feature that threads all four layers end to end. **Read these files** before adding your first feature — copy the pattern:

| Layer | File |
|---|---|
| domain | `domain/value_objects/email.py`, `domain/value_objects/user_id.py` |
| domain | `domain/entities/user.py` |
| domain | `domain/exceptions/user.py` |
| application | `application/repositories/user.py` (abstract) |
| application | `application/dtos/user.py` (`CreateUserInput` / `CreateUserOutput`) |
| application | `application/use_cases/create_user.py` |
| infrastructure | `infrastructure/persistence/models/user.py` (SQLAlchemy `UserModel`) |
| infrastructure | `infrastructure/persistence/user_repository.py` (`SqlAlchemyUserRepository`) |
| infrastructure | `infrastructure/container.py` (`build_user_repository`, `build_create_user_use_case`) |
| presentation | `presentation/api/schemas/user.py` (Pydantic) |
| presentation | `presentation/api/dependencies/users.py` (`Depends` wiring) |
| presentation | `presentation/api/v1/users.py` (router) |
| presentation | `presentation/api/error_handlers.py` (the `ERROR_HTTP_MAPPING` entries) |
| tests | `tests/unit/domain/test_user.py` + `test_email.py` |
| tests | `tests/unit/application/test_create_user_use_case.py` |
| tests | `tests/integration/infrastructure/test_user_repository.py` |
| tests | `tests/e2e/api/test_create_user_endpoint.py` |
| tests | `tests/fakes/repositories/user.py` (`InMemoryUserRepository`) |

Migration: `alembic/versions/0001_init_users.py`.

If the project domain has no notion of a user, see `README.md` → "Removing the reference feature" for the clean deletion path.

## Five commands you need first

The project uses `just` as command runner — pre-installed in the devcontainer. Type `just` to list every recipe.

```bash
just install     # uv sync --group dev
just dev         # FastAPI with auto-reload
just test        # fast unit tests (-x -q)
just test-all    # unit + integration + e2e (Docker required for integration)
just mutate      # mutation testing on domain + application
```

## Where to look next

* **`CLAUDE.md`** at the repo root — the routing table from prompts to skills (auto-loaded every session). The most important file.
* **`docs/architecture.md`** — Mermaid diagrams of the layers + a request sequence diagram.
* **`docs/adr/`** — five ADRs documenting the structural choices (clean architecture, TDD + mutation, fakes-only, transaction boundary, outbox).
* **`.claude/skills/`** — the skills `CLAUDE.md` points at; pick the one matching your task.
