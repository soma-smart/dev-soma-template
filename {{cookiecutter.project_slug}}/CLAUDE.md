# {{ cookiecutter.project_name }} — AI Rules

> This file is loaded automatically at the start of every Claude Code session.
> It is the routing table to `.claude/skills/`. Do not put long content here.

## Project context

{{ cookiecutter.project_description }}

Stack: Python {{ cookiecutter.python_version }}, FastAPI, SQLAlchemy 2.0 async, Alembic, structlog, OpenTelemetry. Architecture: Clean Architecture (Uncle Bob strict) with four layers — `domain`, `application`, `infrastructure`, `presentation`.

The reference feature is `examples/feature_user_signup/` — read it before adding your first feature.

## When you do X, use skill Y

| Trigger                                          | Skill                          |
| ------------------------------------------------ | ------------------------------ |
| First session on this repo                       | `onboarding-soma`              |
| "Where does this code go?", import questions     | `clean-architecture-layers`    |
| Editing `src/<pkg>/domain/`                      | `writing-domain-code`          |
| "Add a feature", "new use case", "new endpoint"  | `adding-a-use-case`            |
| "New error", "domain exception"                  | `adding-a-domain-exception`    |
| "Fix a bug", "write a test"                      | `tdd-workflow` then `writing-tests` |
| Editing `tests/fakes/`                           | `writing-a-fake`               |
| Editing `infrastructure/container.py` or `dependencies/` | `using-the-di-container` |
| "Migration", "schema change", "alembic"          | `database-and-migrations`      |
| Editing `infrastructure/observability/`          | `observability-patterns`       |
| Naming a class, function, or module              | `naming-conventions`           |
| Editing `helm/`                                  | `writing-a-helm-change`        |
| "Review this PR"                                 | `reviewing-a-pr-soma-style`    |

## Hard rules (non-negotiable)

1. **TDD red first**. Every line of production code is justified by a failing test.
2. **No mocks in unit tests** — only Fakes from `tests/fakes/`. Mocks only for non-self-hostable external SaaS, in integration tests.
3. **No third-party imports in `src/<pkg>/domain/`** — not even `datetime.now()`, `uuid.uuid4()`, `random.*`. Use the `Clock`, `IdGenerator`, `RandomSource` abstractions.
4. **No log in `domain/` or `application/`** — log only at infrastructure and presentation boundaries.
5. **No HTTP types in `application/` or `domain/`** — exceptions are `DomainError` subclasses; the HTTP mapping lives in `presentation/api/error_handlers.py`.
6. **GIVEN/WHEN/THEN strict** in unit and integration tests (function name and body comments).
7. **Conventional commits**, no `--no-verify`, no force push.
8. **Function ≤ 25 lines**. Cyclomatic complexity ≤ 10.
9. **`Decimal` for money**, **TZ-aware datetimes** stored UTC.
10. **No `Manager`, `Helper`, `Util`, `Service`** generic class names.

## Pointers

- Architecture overview: [`docs/architecture.md`](docs/architecture.md)
- ADRs: [`docs/adr/`](docs/adr/)
- Reference feature: [`examples/feature_user_signup/`](examples/feature_user_signup/)
