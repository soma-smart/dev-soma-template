# dev-soma-template — Repo IA Rules

> This file governs **AI editing of the template itself**.
> The generated projects ship their own `CLAUDE.md` inside `{{cookiecutter.project_slug}}/CLAUDE.md`.

## What this repo is

A **Cookiecutter** that generates SOMA Python services. Output = a project with FastAPI + Clean Architecture + observability + Helm + multi-layer guardrails (Claude skills, hooks, pre-commit, CI).

The design rationale lives in the git history (commit messages are the source of truth for "why"). Each generated project ships its own `docs/architecture.md` and `docs/adr/`.

## Repo layout

```
.
├── cookiecutter.json                      # template variables
├── hooks/                                 # pre/post_gen_project Python hooks
├── tests/                                 # pytest-cookies bake tests of the template
└── {{cookiecutter.project_slug}}/         # the generated project (see its own CLAUDE.md)
```

## Hard rules for AI editors

1. **Two roots, two pyprojects, two CLAUDE.md** — never confuse them:
   - root `pyproject.toml` = template tooling (cookiecutter, pytest, pytest-cookies, ruff)
   - `{{cookiecutter.project_slug}}/pyproject.toml` = generated project deps (FastAPI, SQLAlchemy, etc.)
2. **Never** edit `{{cookiecutter.project_slug}}/` files to fix a generated-project bug discovered downstream — fix at the template level so the next bake inherits the fix.
3. **Cookiecutter templating syntax** uses `{{ cookiecutter.<var> }}`. Be careful when editing JSON/YAML files: Jinja braces inside JSON strings need to remain valid Jinja, not break JSON parsing.
4. **Bake tests are the contract** — adding a feature without updating `tests/test_template_bake.py` is a regression.
5. **Conventional commits** required. Branches: `feat/*`, `fix/*`, `docs/*`, `refactor/*`, `chore/*`. PRs must pass all CI checks.

## Editing workflow

1. Edit either the template machinery (root) **or** the generated project skeleton (`{{cookiecutter.project_slug}}/`) — rarely both in the same change.
2. Run bake tests locally: `uv run pytest`.
3. Write the commit message so it captures the *why* of the change (it's the long-term decision record).

## Commands

```bash
uv sync                                    # install template tooling
uv run pytest                              # run bake tests
uv run cookiecutter . --no-input -o /tmp   # bake with default values for manual inspection
uv run ruff check hooks/ tests/            # only on the template machinery — see note below
uv run ruff format hooks/ tests/
```

**Note on ruff paths**: `uv run ruff check .` fails because ruff walks into `{{cookiecutter.project_slug}}/` and tries to parse the Jinja-templated `pyproject.toml` as a nested config. Always pass explicit paths (`hooks/`, `tests/`) at the template root. Pre-commit handles this transparently via its `exclude` regex.
