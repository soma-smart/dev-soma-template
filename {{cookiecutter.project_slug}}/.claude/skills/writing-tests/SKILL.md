---
name: writing-tests
description: Test pyramid + Fakes-only at unit + testcontainers at integration + 1-happy-1-critical at e2e + GIVEN/WHEN/THEN format + how to write a Fake. The single source of truth for everything that lives under tests/.
when_to_use: Writing or reviewing any test under tests/. Adding a new Fake under tests/fakes/. Designing the test suite for a new feature.
---

# Writing tests

## Pyramid

```
tests/
├── unit/                  # Fakes only, no I/O. Mutation testing target.
│   ├── domain/            # entities, value objects, exceptions
│   ├── application/       # use cases — the bulk of branches
│   └── presentation/      # invariants on the HTTP mapping, schema parsing
├── integration/           # testcontainers Postgres / Redis. Real systems.
│   └── infrastructure/    # repositories, http clients, mappers
└── e2e/                   # FastAPI booted via TestClient.
    └── api/
```

Per-layer conftests under `tests/conftest.py` (root primitives) + `tests/unit/conftest.py` + `tests/integration/conftest.py` (testcontainers PG) + `tests/e2e/conftest.py` (`app`, `client`, `StubAsyncSession`).

## Hard rules

### 1. Fakes-only at unit

Pass an in-memory implementation from `tests/fakes/` to the system under test. **Forbidden** in `tests/unit/`: `unittest.mock`, `Mock`, `MagicMock`, `Spy`, `Stub`, `patch`.

Rationale: a Mock asserts *which* method got called with *which* arguments — that couples the test to the implementation. A Fake asserts that *observable behaviour* happened — the test stays valid through any refactor that preserves behaviour.

If you need to verify a side-effect, the Fake exposes inspectable state. The canonical example is `tests.fakes.repositories.user.InMemoryUserRepository.users` — a dict you read directly to assert "this user was persisted".

### 2. Real systems at integration

Use `testcontainers` (Postgres, Redis) to run actual instances. The `pg_session` fixture in `tests/integration/conftest.py` spawns Postgres 17 once per test session and yields a transaction-rolled-back session per test. **Mock only** what you genuinely cannot self-host (a paid SaaS sandbox API).

Integration tests prove the contract that unit-level Fakes cannot:
* INSERT propagates the unique constraint as a `DomainError`
* `find_by_email` round-trips the entity ↔ ORM model mapping
* the transaction rollback semantics actually rollback

### 3. E2E proves wiring, not branches

For each endpoint: **1 happy path + 1 critical error**. No more.

If a use case has 12 branches, those are 12 unit tests; only 1-2 e2e. Duplicating branches at e2e level is a smell — the right fix is adding a unit test, not adding an e2e.

E2E uses the `client` fixture from `tests/e2e/conftest.py`, which gives a `TestClient` with `dependency_overrides` already wired to the in-memory Fakes. The Fake repository doubles as a Spy: assert against `user_repository.users` after the request.

### 4. GIVEN/WHEN/THEN strict

```python
async def test_given_<context>_when_<action>_then_<expectation>() -> None:
    # GIVEN
    <setup>

    # WHEN
    <single action>

    # THEN
    <assertions>
```

Tolerance: `# WHEN / THEN` combined is allowed only when the WHEN is `pytest.raises`. Enforced by `scripts/checks/test_naming.py`. Annotation form `# GIVEN: <inline note>` is accepted for fixture-driven tests where the GIVEN is fully composed by fixtures.

### 5. FIRST principles

* **F**ast — a unit test runs in milliseconds.
* **I**solated — `frozen_clock`, `sequential_ids`, `seeded_random` are the conftest fixtures that buy this. No flaky reliance on the wall clock or true randomness.
* **R**epeatable — same input, same output, on any machine.
* **S**elf-validating — a single `assert` line tells you pass/fail.
* **T**imely — write the test before the production code (see `tdd-workflow`).

## Mutation testing

After every change in `domain/` or `application/`:

```bash
just mutate           # mutmut on the configured paths
just mutate-results   # latest report
```

Surviving mutants ⇒ tests too lax. Read the mutant, write the missing test, retry. CI enforces a 90% kill-rate floor on PRs (`ci-mutation.yml`).

## Common Fakes shipped with the template

| Abstraction | Production | Fake |
|---|---|---|
| `Clock` | `SystemClock` | `FrozenClock(at=datetime(...))` |
| `IdGenerator` | `Uuid4IdGenerator` | `SequentialIdGenerator(start=1)` |
| `RandomSource` | `SystemRandomSource` | `SeededRandomSource(seed=0)` |
| `UserRepository` | `SqlAlchemyUserRepository` | `InMemoryUserRepository(seed=[...])` |

The root conftest exposes them as fixtures (`frozen_clock`, `sequential_ids`, `seeded_random`, `user_repository`, `create_user_use_case`).

## Writing a new Fake

A Fake is a **working** in-memory implementation of an abstraction. It must be:

* **Deterministic** — no clock drift, no random without a seed.
* **Cheap** — no network, no disk.
* **Inspectable** — tests assert on `fake.<state>`.
* **Faithful** — enforces the same invariants as the real binding (uniqueness constraints, validation). A Fake that always returns the happy answer is useless.

### File layout

* `tests/fakes/<name>.py` for primitives (`clock.py`, `id_generator.py`, `random_source.py`).
* `tests/fakes/repositories/<entity>.py` for repositories.

Mirror the production structure under `tests/fakes/`.

### Skeleton

```python
from {{ cookiecutter.package_name }}.application.<module> import <Abstraction>


class InMemory<Abstraction>(<Abstraction>):
    """In-memory fake for tests. Acts as Spy via its public state."""

    def __init__(self, seed: <SeedType> = ()) -> None:
        self.<state>: <Container> = ...

    async def <abstract_method>(self, ...) -> ...:
        # smallest faithful implementation
        ...
```

### Acting as a Spy

```python
fake_email_sender = InMemoryEmailSender()
await use_case.execute(...)
assert fake_email_sender.sent == [Email("alice@example.com")]
```

The assertion is on **observable behaviour** (a message was queued for that recipient), not on implementation details. `assert_called_with(...)` fails under refactor for free; this assertion does not.

### Mistakes to avoid

* Importing from `infrastructure/` in a Fake — couples Fakes to concretes.
* Using `random.*` without a seed.
* Using `datetime.now()` — Fakes of `Clock` accept the time as a parameter.
* Implementing only the happy path — without the uniqueness / validation invariants the real production code enforces, unit tests pass on impossible scenarios.
* Adding a Fake without registering it as a conftest fixture if more than one test will use it.
