# 3. Fakes only in unit tests (no Mock)

Date: 2026-05-05

## Status

Accepted.

## Context

`unittest.mock` is convenient but couples tests to implementation details. A mock-heavy test suite passes after a refactor that broke production behaviour, simply because the mock chain still matches. The team has been bitten enough times to ban Mocks at the unit-test level.

We also want a single, explicit answer to the recurring question "what test double should I use here?".

## Decision

In `tests/unit/`:

- **Fakes only.** Each abstraction in `application/` ships a Fake under `tests/fakes/`. The Fake is a working in-memory implementation (e.g., `InMemoryUserRepository`), simpler than the real binding but faithful enough to enforce the same invariants (uniqueness, validation).
- `unittest.mock`, `Mock`, `MagicMock`, manually written Stubs, `unittest.mock.PropertyMock` are **forbidden** in `tests/unit/`.
- When a test needs to assert that a side effect happened, the Fake exposes its internal state (e.g., `repo.users` dict, `email_sender.sent` list) — this is the role a Spy would play, expressed as observable Fake state instead of a separate doubling mechanism.

In `tests/integration/`:

- **Real systems via `testcontainers`** (Postgres, Redis, etc.) — anything self-hostable.
- **Mocks ONLY for non-self-hostable third-party services** — paid SaaS sandbox APIs that cannot be replicated locally. Document the choice in a comment.

In `tests/e2e/`:

- The whole stack is real (FastAPI booted, test database). Tests prove wiring, not behaviour. **1 happy path + 1 critical error per endpoint** — branches stay covered at the unit level.

## Consequences

**Positive**:
- Tests survive refactors that change "how" without changing "what".
- The Fake of an abstraction doubles as living documentation of its contract.
- The cognitive load is lower: no `Mock` magic to learn, just call `InMemoryUserRepository().users` and `assert`.

**Negative**:
- Writing the first Fake of an abstraction is more work than `Mock(spec=…)`. We treat this as a feature: it forces us to think about the contract.
- Some patterns (interaction-heavy code with many collaborators) suggest Mocks would be easier — but our Clean Architecture layout makes interaction-heavy use cases rare. When they do appear, the smell is usually a missing Fake or a misplaced collaborator.
