# {{ cookiecutter.project_name }}

> {{ cookiecutter.project_description }}

## Stack

- Python {{ cookiecutter.python_version }} • FastAPI • SQLAlchemy 2.0 async • Alembic
- Clean Architecture (Uncle Bob strict) — see [`docs/architecture.md`](docs/architecture.md)
- structlog + OpenTelemetry • uv • ruff • ty • mutmut

## Five commands you need

```bash
uv sync --group dev                              # install deps
uv run uvicorn {{ cookiecutter.package_name }}.presentation.api.app:app --reload
uv run pytest -m unit                            # fast unit tests
uv run pytest                                    # all (unit + integration + e2e)
uv run mutmut run                                # mutation testing on domain + application
```

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
