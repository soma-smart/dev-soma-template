# {{ cookiecutter.project_name }} — AI Rules

> This file is loaded automatically at the start of every Claude Code session.
> It is the routing table to `.claude/skills/`. Do not put long content here.

## Project context

{{ cookiecutter.project_description }}

Stack: Python {{ cookiecutter.python_version }}, FastAPI, SQLAlchemy 2.0 async, Alembic, structlog, OpenTelemetry. Architecture: Clean Architecture (Uncle Bob strict) with four layers — `domain`, `application`, `infrastructure`, `presentation`.

The reference feature shipped in `src/` and `tests/` is the SSO-backed `GET /v1/users/me` flow: a verified JWT → `EnsureUserExistsUseCase` (idempotent find-or-create on the `subject` claim) → `SqlAlchemyUserRepository` → `users` table. The first authenticated call lazily provisions the row; subsequent calls reuse it. Read the `onboarding-soma` skill for the file map and `docs/swagger-oauth2.md` for the Azure / Auth0 / Keycloak app-registration walkthrough.

## When you do X, use skill Y

| Trigger                                                            | Skill                          |
| ------------------------------------------------------------------ | ------------------------------ |
| First session on this repo                                         | `onboarding-soma`              |
| "Where does this code go?", import questions, naming, layer rules  | `onboarding-soma`              |
| `infrastructure/container.py`, `dependencies/`, observability      | `onboarding-soma`              |
| Editing `src/<pkg>/domain/`, new entity, value object, exception   | `writing-domain-code`          |
| "Add a feature", "new use case", "new endpoint"                    | `building-a-feature`           |
| "Need a new EmailSender / Gateway / Hasher / ..."                  | `building-a-feature` (§ "Adding a new abstraction") |
| Domain events, transactions, outbox                                | `building-a-feature` (§ "Transactions and events") |
| "Idempotency-Key", "retry safe", 409/422 idempotency               | `building-a-feature` (§ "Idempotency") |
| "Fix a bug", "write a test", editing `tests/fakes/`                | `tdd-workflow`                 |
| "Migration", "schema change", "alembic"                            | `database-and-migrations`      |
| Editing `helm/`                                                    | `writing-a-helm-change`        |
| "Protect a route", "JWT", role check, "401/403"                    | `adding-auth`                  |
| "Event-source X", "should we ES this entity?", audit / time-travel | `event-sourcing-pattern`       |
| "Review this PR"                                                   | `reviewing-a-pr-soma-style`    |
| Operator runbooks (incident, backup, restore)                      | `docs/runbooks/`               |

## Hard rules (non-negotiable)

1. **TDD red first**. Every line of production code is justified by a failing test.
2. **No mocks in unit tests** — only Fakes from `tests/fakes/`. Mocks only for non-self-hostable external SaaS, in integration tests.
3. **No third-party imports in `src/<pkg>/domain/`** — not even `datetime.now()`, `uuid.uuid4()`, `random.*`. Use the `Clock`, `IdGenerator`, `RandomSource` abstractions.
4. **No log in `domain/` or `application/`** — log only at infrastructure and presentation boundaries.
5. **No HTTP types in `application/` or `domain/`** — exceptions are `DomainError` subclasses; the HTTP mapping lives in `presentation/api/error_handlers.py`.
6. **GIVEN/WHEN/THEN strict** in unit and integration tests (function name and body comments). One assertion per test, no `@pytest.mark.parametrize`.
7. **Conventional commits**, no `--no-verify`, no force push.
8. **Function ≤ 25 lines**. Cyclomatic complexity ≤ 10.
9. **`Decimal` for money**, **TZ-aware datetimes** stored UTC.
10. **No `Manager`, `Helper`, `Util`, `Service`** generic class names.

## How the main agent works on this repo

This project ships **no custom sub-agents**. The main agent handles the whole flow directly, guided by skills. For a feature:

1. The user gives a one-liner prompt.
2. The main agent asks 4-6 clarification questions (picked from the packs in `building-a-feature`).
3. The user answers.
4. The main agent produces the 5-section outside-in plan.
5. The user validates.
6. The main agent executes outside-in TDD: use case (unit) → persistence (integration) → route (e2e), wires the container, runs mutation testing.

The full runbook is in `building-a-feature`. The discipline (red-green-refactor, Fakes-only, GIVEN/WHEN/THEN, mutation) is in `tdd-workflow`. The "how SOMA code is shaped" reference (layers, naming, DI, observability) is in `onboarding-soma`.

PR review uses Anthropic's built-in `pr-review-toolkit:*` agents plus the `reviewing-a-pr-soma-style` skill.

## Pointers

- Architecture overview: [`docs/architecture.md`](docs/architecture.md)
- ADRs: [`docs/adr/`](docs/adr/)
- Operator runbooks: [`docs/runbooks/`](docs/runbooks/) — backups, restore, disaster-recovery playbooks
- Reference feature file map: see the `onboarding-soma` skill
