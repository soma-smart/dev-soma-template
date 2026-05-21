# {{ cookiecutter.project_name }}

> {{ cookiecutter.project_description }}

## Stack

- Python {{ cookiecutter.python_version }} • FastAPI • SQLAlchemy 2.0 async • Alembic
- Clean Architecture (Uncle Bob strict) — see [`docs/architecture.md`](docs/architecture.md)
- structlog + OpenTelemetry • uv • ruff • ty • mutmut

## Five commands you need

The project uses [`just`](https://just.systems) as a command runner — a thin
shell over `uv run …`. The devcontainer ships it pre-installed; on bare metal
install it once with `cargo install just` / `brew install just` / `apt install just`.

```bash
just install     # uv sync --group dev
just dev         # uvicorn with auto-reload
just test        # fast unit tests
just test-all    # unit + integration + e2e
just mutate      # mutation testing on domain + application
```

Type `just` (no args) to list every recipe. Each one is one line in `justfile`
— inspect it instead of memorising flags.
{%- if cookiecutter.frontend_sdk == "typescript" %}

A TypeScript client SDK is generated automatically by `.github/workflows/sdk-typescript.yml`
on every push to `main` that touches the API surface; it is uploaded as a workflow
artefact. Run `just openapi` locally to dump the OpenAPI schema to `openapi.json`.
{%- endif %}

## First time on this project

1. Open in VS Code and run **Reopen in Container** — Postgres + Jaeger + OTel collector start automatically.
2. Read [`CLAUDE.md`](CLAUDE.md) (AI rules) and [`docs/architecture.md`](docs/architecture.md).
3. Browse the **User reference feature** shipped in `src/` and `tests/` — it threads the four layers end-to-end (`GET /v1/users/me` → JWT `get_current_user` → `EnsureUserExistsUseCase` (idempotent find-or-create on the `subject` claim) → `SqlAlchemyUserRepository` → `users` table). It is real working code: keep it as a starting point if your service has the notion of a user; remove it cleanly otherwise (see below). The IdP integration walkthrough lives in [`docs/swagger-oauth2.md`](docs/swagger-oauth2.md).
4. Add your first feature using the `building-a-feature` Claude skill.

### Removing the reference feature

Run from the project root, then commit:

```bash
# Source files (12)
git rm src/{{ cookiecutter.package_name }}/domain/entities/user.py \
       src/{{ cookiecutter.package_name }}/domain/value_objects/email.py \
       src/{{ cookiecutter.package_name }}/domain/value_objects/user_id.py \
       src/{{ cookiecutter.package_name }}/domain/exceptions/user.py \
       src/{{ cookiecutter.package_name }}/application/repositories/user.py \
       src/{{ cookiecutter.package_name }}/application/use_cases/ensure_user_exists.py \
       src/{{ cookiecutter.package_name }}/application/dtos/user.py \
       src/{{ cookiecutter.package_name }}/infrastructure/persistence/models/user.py \
       src/{{ cookiecutter.package_name }}/infrastructure/persistence/user_repository.py \
       src/{{ cookiecutter.package_name }}/presentation/api/v1/users.py \
       src/{{ cookiecutter.package_name }}/presentation/api/schemas/user.py \
       src/{{ cookiecutter.package_name }}/presentation/api/dependencies/users.py

# Tests (6) + the migration that creates the users table (1)
git rm tests/unit/domain/test_user.py \
       tests/unit/domain/test_email.py \
       tests/unit/application/test_ensure_user_exists_use_case.py \
       tests/e2e/api/test_users_me_endpoint.py \
       tests/integration/infrastructure/test_user_repository.py \
       tests/fakes/repositories/user.py \
       alembic/versions/0001_init_users.py
```

Then **edit four files** to drop the dangling references:

| File | Drop |
| --- | --- |
| `tests/conftest.py` | the `user_repository` and `ensure_user_exists_use_case` fixtures, and the `app.dependency_overrides[get_ensure_user_exists_use_case]` / `get_or_provision_user` lines |
| `src/{{ cookiecutter.package_name }}/presentation/api/error_handlers.py` | the `UserAlreadyExistsError`, `UserNotFoundError`, `InvalidEmailError`, `MissingProfileClaimsError` imports and entries in `ERROR_HTTP_MAPPING` |
| `src/{{ cookiecutter.package_name }}/infrastructure/container.py` | `build_user_repository`, `build_ensure_user_exists_use_case`, and their imports |
| `src/{{ cookiecutter.package_name }}/presentation/api/app.py` | the `users_v1` import and `app.include_router(users_v1.router)` line |

Sanity-check your removal:

```bash
just lint        # ruff + ty + 4 architectural lints
just test-all    # everything that remained should still pass
```

The base classes (`Entity`, `ValueObject`, `UseCase`, `Repository`), the abstractions (`Clock`, `IdGenerator`, `EventBus`, `AuditLog`, `OutboxEventModel`), the middleware stack, the health probes, the conftest primitives (`frozen_clock`, `sequential_ids`, `seeded_random`, `stub_session`) — all stay and are reusable for your real domain.

## Conventions (non-negotiable)

- **TDD**: red → green → refactor → mutate. No production code without a failing test first.
- **Clean Architecture layering**: `domain` knows nothing; `application` knows `domain`; `infrastructure` and `presentation` know inward.
- **Tests**: GIVEN/WHEN/THEN strict naming and body. Fakes in unit tests; testcontainers in integration; one happy path + one critical error per endpoint in e2e.
- **Conventional Commits**, mandatory PRs, no `--no-verify`, no force push.

The full ruleset lives in `.claude/skills/` and is enforced by pre-commit, git hooks, Claude Code hooks and CI.

## CI/CD

GitHub Actions: quality (ruff + ty + pytest), security (bandit + pip-audit + gitleaks), mutation (mutmut), helm (lint + kubeconform + polaris), migration-drift (autogenerate diff), image-scan (Trivy + SBOM), release (build + scan + cosign sign + SBOM attestation).

Conventional Commits are enforced **locally** by the `commitizen` `commit-msg` pre-commit hook (and Claude Code permissions block `--no-verify`), so a dedicated CI gate is intentionally absent.
