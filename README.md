# dev-soma-template

A **Cookiecutter** template that generates state-of-the-art SOMA Python services.

What you get out-of-the-box:

- **FastAPI 0.115+** + **SQLAlchemy 2.0 async** + **asyncpg** + **Alembic**
- **Clean Architecture** (Uncle Bob strict): `domain` / `application` / `infrastructure` / `presentation`
- **uv** + **ruff** (extended ruleset) + **ty** (Astral type checker) + **mutmut** (mutation testing)
- **OpenTelemetry** auto-switching between console and OTLP exporters
- **structlog** with technical (JSON) and human-readable formats
- **Devcontainer** with full local stack (Postgres + Jaeger + OTel collector)
- **Helm chart** with multi-environment values, schema validation, migrations job
- **Multi-layer guardrails** preventing convention drift: Claude Code skills + hooks, pre-commit, git hooks, CI

Authoritative design: [`docs/superpowers/specs/2026-05-05-soma-template-v2-design.md`](docs/superpowers/specs/2026-05-05-soma-template-v2-design.md).

## Generate a new project

```bash
# Install cookiecutter (one-time, globally or via pipx/uvx)
uvx cookiecutter gh:soma-smart/dev-soma-template

# Or from a local clone
git clone git@github.com:soma-smart/dev-soma-template.git
uvx cookiecutter ./dev-soma-template
```

You will be prompted for:

| Variable               | Default               | Description                                         |
| ---------------------- | --------------------- | --------------------------------------------------- |
| `project_name`         | `My SOMA Service`     | Human-readable project name                         |
| `project_slug`         | derived from name     | Folder + repo slug (`kebab-case`)                   |
| `package_name`         | derived from slug     | Importable Python package (`snake_case`)            |
| `project_description`  |                       | One-liner                                           |
| `author_name`          | `SOMA`                |                                                     |
| `author_email`         | `team@soma-smart.com` |                                                     |
| `python_version`       | `3.13`                | `3.13` or `3.14`                                    |
| `database`             | `postgres`            | `postgres`, `sqlite`, or `none` (no example)        |
| `include_helm`         | `yes`                 | Ship a Helm chart                                   |
| `include_otel`         | `yes`                 | Wire OpenTelemetry instrumentations                 |
| `include_cli`          | `no`                  | Add a `presentation/cli/` layer                     |
| `license`              | `proprietary`         | `proprietary`, `MIT`, `Apache-2.0`                  |

After generation, the post-hook automatically:

1. `git init` + initial commit
2. `uv sync --group dev`
3. `cp .env.example .env`
4. `pre-commit install` (commit-msg + pre-push hooks)

## Develop on the template itself

```bash
uv sync                                       # template tooling
uv run pytest                                 # bake tests (pytest-cookies)
uv run cookiecutter . --no-input -o /tmp/out  # smoke-bake locally
uv run ruff check . && uv run ruff format .
```

See [`CLAUDE.md`](CLAUDE.md) for AI-assisted editing rules.
