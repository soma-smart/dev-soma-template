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
3. Read the reference feature in [`examples/feature_user_signup/`](examples/feature_user_signup) — it threads the four layers end-to-end.
4. Add your first feature using the `adding-a-use-case` Claude skill.

## Conventions (non-negotiable)

- **TDD**: red → green → refactor → mutate. No production code without a failing test first.
- **Clean Architecture layering**: `domain` knows nothing; `application` knows `domain`; `infrastructure` and `presentation` know inward.
- **Tests**: GIVEN/WHEN/THEN strict naming and body. Fakes in unit tests; testcontainers in integration; one happy path + one critical error per endpoint in e2e.
- **Conventional Commits**, mandatory PRs, no `--no-verify`, no force push.

The full ruleset lives in `.claude/skills/` and is enforced by pre-commit, git hooks, Claude Code hooks and CI.

## CI/CD

GitHub Actions: quality (ruff + ty + pytest), security (bandit + pip-audit + gitleaks), mutation (mutmut), helm (lint + kubeconform), conventional commits, release (semver + image push).
