# {{ cookiecutter.project_name }} — AI Rules

> This file is loaded automatically at the start of every Claude Code session.
> It is the routing table to `.claude/skills/`. Do not put long content here.

## Project context

{{ cookiecutter.project_description }}

Stack: Python {{ cookiecutter.python_version }}, FastAPI, SQLAlchemy 2.0 async, Alembic, structlog, OpenTelemetry. Architecture: Clean Architecture (Uncle Bob strict) with four layers — `domain`, `application`, `infrastructure`, `presentation`.

The reference feature shipped in `src/` and `tests/` is the `POST /v1/users` flow (`User` entity → `CreateUserUseCase` → `SqlAlchemyUserRepository` → `users` table). Read the `onboarding-soma` skill for the file map. Projects without a user concept remove it via the README's "Removing the reference feature" runbook.

## When you do X, use skill Y

| Trigger                                          | Skill                          |
| ------------------------------------------------ | ------------------------------ |
| First session on this repo                       | `onboarding-soma`              |
| "Where does this code go?", import questions     | `clean-architecture-layers`    |
| Editing `src/<pkg>/domain/`                      | `writing-domain-code`          |
| "Add a feature", "new use case", "new endpoint"  | `adding-a-use-case`            |
| "Need a new EmailSender / Gateway / Hasher / ..." | `adding-a-new-abstraction` (BEFORE you write the Protocol) |
| "New error", "domain exception"                  | `adding-a-domain-exception`    |
| "Fix a bug", "write a test", editing `tests/fakes/` | `tdd-workflow` then `writing-tests` |
| Editing `infrastructure/container.py` or `dependencies/` | `using-the-di-container` |
| "Migration", "schema change", "alembic"          | `database-and-migrations`      |
| Editing `infrastructure/observability/`          | `observability-patterns`       |
| Naming a class, function, or module              | `naming-conventions`           |
| Editing `helm/`                                  | `writing-a-helm-change`        |
| "Protect a route", "JWT", role check, "401/403"  | `adding-auth`                  |
| "Idempotency-Key", "retry safe", 409/422 idempotency | `idempotency-and-retries`  |
| Alert firing, on-call question, "what do I do if…" | `incident-response`        |
| "Event-source X", "should we ES this entity?", audit / time-travel | `event-sourcing-pattern` |
| "Review this PR"                                 | `reviewing-a-pr-soma-style`    |
| Feature spans more than one layer; orchestrating sub-agents | `orchestrating-feature-dev` |

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

## Custom sub-agents

This project ships eight custom sub-agents under `.claude/agents/`. They split into two families: **feature-level builders** (produce a vertical slice from a business-intent brief) and **tech-narrow utilities** (surgical edits on one file type). See `orchestrating-feature-dev` for the dispatch rules.

**Feature-level builders** — the main agent dispatches these after designing the Protocol / DTO / event / error contracts:

- `soma-use-case-builder` — domain + application + Fake + unit tests (TDD ≥ 90% mutation). Extends the Repository Protocol with business-named methods.
- `soma-persistence-builder` — SQLAlchemy model + Alembic migration + repository impl + integration tests. Reads the Protocol docstrings as the WHERE-clause contract.
- `soma-route-builder` — Pydantic schema + FastAPI route + container factory + dependency wrapper + e2e tests.

**Tech-narrow utilities** — for surgical work, not for building new features:

- `soma-migration-writer` — standalone schema change (alter column, add index, data migration) independent of a new repo.
- `soma-helm-engineer` — chart edits + `helm lint` / `kubeconform` / `polaris`.
- `soma-event-sourcing-bootstrapper` — scaffolds the 4 lite-ES files for a named entity (architect decides per `event-sourcing-pattern`).
- `soma-unit-test-writer` — fills a coverage gap on EXISTING code; NOT for new use cases (the builder writes its own tests).
- `soma-integration-test-writer` — fills a coverage gap on an EXISTING repo; NOT for new repos.

The main agent is the **architect**: it designs the contracts (Protocol shape, DTO, events, errors, status codes) and writes self-contained briefs for the builders. It does not author production code except for cross-cutting concerns (adding a new shared Protocol, updating `ERROR_HTTP_MAPPING`). PR review uses Anthropic's built-in `pr-review-toolkit:*` agents plus the `reviewing-a-pr-soma-style` skill — no custom reviewer ships here.

Dispatch through the `orchestrating-feature-dev` skill or invoke an agent directly with the `Task` tool when the work is narrowly scoped. PR review uses Anthropic's built-in `pr-review-toolkit:*` agents plus the `reviewing-a-pr-soma-style` skill — no custom reviewer ships here.

## Pointers

- Architecture overview: [`docs/architecture.md`](docs/architecture.md)
- ADRs: [`docs/adr/`](docs/adr/)
- Operator runbooks: [`docs/runbooks/`](docs/runbooks/) — backups, restore, disaster-recovery playbooks
- Reference feature file map: see the `onboarding-soma` skill
