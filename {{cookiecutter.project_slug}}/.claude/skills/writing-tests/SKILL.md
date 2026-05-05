---
name: writing-tests
description: Test pyramid, FIRST, Fakes-only rule, GIVEN/WHEN/THEN format, and the e2e anti-duplication rule.
when_to_use: Writing or reviewing any test under tests/.
---

# Writing tests

## Pyramid

```
tests/
├── unit/           # Fakes only, no I/O. Mutation testing target.
│   ├── domain/
│   ├── application/
│   └── presentation/
├── integration/    # testcontainers Postgres / Redis. Mocks ONLY for
│   └── infrastructure/   # non-self-hostable SaaS.
└── e2e/            # FastAPI bootted via httpx.AsyncClient or TestClient.
    └── api/
```

## Hard rules

1. **Fakes-only in unit tests.** Implement the abstraction in `tests/fakes/<name>.py` and pass it to the system under test. `unittest.mock`, `Mock`, `MagicMock` are forbidden in `tests/unit/`. If you need to assert a side-effect happened, the Fake exposes its internal state (the `tests.fakes.repositories.user.InMemoryUserRepository.users` dict is the canonical example).

2. **Real systems in integration tests.** Use `testcontainers` (Postgres, Redis) to run actual instances. Mock only what you cannot self-host (paid SaaS sandbox).

3. **E2E tests prove wiring, not branches.** For each endpoint: **1 happy path + 1 critical error**, no more. If a use case has 12 branches, those are 12 unit tests; only 1-2 e2e. Duplicating branches in e2e is a smell — fix by adding a unit test, not by adding an e2e.

4. **GIVEN/WHEN/THEN strict**:

```python
async def test_given_<context>_when_<action>_then_<expectation>() -> None:
    # GIVEN
    <setup>

    # WHEN
    <single action>

    # THEN
    <assertions>
```

Tolerance: `# WHEN / THEN` combined is allowed only when the WHEN is `pytest.raises`. Enforced by `scripts/checks/test_naming.py`.

5. **FIRST** principles: Fast, Isolated, Repeatable, Self-validating, Timely (TDD). The Clock and IdGenerator abstractions exist for the Repeatable property — use FrozenClock/SequentialIdGenerator from `tests/fakes/`.

## Common Fakes

| Abstraction | Production | Fake |
|---|---|---|
| `Clock` | `SystemClock` | `FrozenClock(at=datetime(...))` |
| `IdGenerator` | `Uuid4IdGenerator` | `SequentialIdGenerator(start=1)` |
| `RandomSource` | `SystemRandomSource` | `SeededRandomSource(seed=0)` |
| `UserRepository` | `SqlAlchemyUserRepository` | `InMemoryUserRepository(seed=[...])` |

When you write a new abstraction you write its Fake too — see `writing-a-fake`.

## Mutation testing

After every change in `domain/` or `application/`, run mutmut on the touched paths:

```bash
uv run mutmut run --paths-to-mutate src/{{ cookiecutter.package_name }}/<paths>
uv run mutmut results
```

Surviving mutants ⇒ tests too lax ⇒ write a missing test.
