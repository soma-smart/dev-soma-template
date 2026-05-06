---
name: onboarding-soma
description: First-session orientation for {{ cookiecutter.project_name }}. Use when starting a fresh Claude Code session on this repo or when the user asks for a tour, project overview, or "where do I start".
when_to_use: First session on the repo; user asks for an overview; user is exploring the codebase.
---

# {{ cookiecutter.project_name }} — Onboarding

## The map

```
src/{{ cookiecutter.package_name }}/
├── domain/          # entities, value objects, exceptions — pure Python, no third-party deps
├── application/     # use cases + abstractions (Clock, IdGenerator, repos)
├── infrastructure/  # SQLAlchemy, structlog, OTel, DI container — concretes
└── presentation/    # FastAPI routes, schemas, error handlers
```

Dependency rule (one-way, inward):

```
presentation  ──→  application  ──→  domain
infrastructure  ─→  application  ──→  domain
```

`presentation` never imports `infrastructure` directly. Concretes are injected via `Depends`.

## Reference feature (read this before adding your first one)

`examples/feature_user_signup/` (or `src/{{ cookiecutter.package_name }}/.../user.py` traced end-to-end) implements the `POST /v1/users` endpoint across all four layers. Pattern to copy:

1. `domain/value_objects/email.py` — Email value object with validation
2. `domain/entities/user.py` — User entity with identity-based equality
3. `domain/exceptions/user.py` — UserAlreadyExistsError, UserNotFoundError
4. `application/repositories/user.py` — abstract `UserRepository`
5. `application/use_cases/create_user.py` — `CreateUserUseCase`
6. `infrastructure/persistence/models/user.py` — `UserModel` SQLAlchemy
7. `infrastructure/persistence/user_repository.py` — `SqlAlchemyUserRepository`
8. `presentation/api/schemas/user.py` — Pydantic schemas
9. `presentation/api/v1/users.py` — FastAPI router
10. `presentation/api/error_handlers.py` — ERROR_HTTP_MAPPING entries

## Five commands you need

The project uses `just` as command runner. Type `just` (no args) to see every
recipe; each one is one line in `justfile`.

```bash
just install     # uv sync --group dev
just dev         # FastAPI with auto-reload
just test        # fast unit tests
just test-all    # unit + integration + e2e
just mutate      # mutation testing on domain + application
```

## Then read these skills

- `clean-architecture-layers` — where things go, what may import what
- `tdd-workflow` — TDD red/green/refactor + mutmut loop
- `writing-tests` — pyramid, Fakes-only, GIVEN/WHEN/THEN
- `naming-conventions` — Uncle Bob strict + role stereotypes
- `adding-a-use-case` — full walkthrough
