---
name: writing-a-fake
description: How to add a Fake under tests/fakes/ for a new abstraction.
when_to_use: New abstract class added in application/; existing test needs a deterministic double.
---

# Writing a Fake

## Rule of thumb

A Fake is a **working** in-memory implementation of an abstraction, simpler than the production binding. It must be:

- **Deterministic** (no clock drift, no random unless seeded).
- **Cheap** (no network, no disk).
- **Inspectable** (tests assert on internal state).
- **Faithful enough** to catch real bugs (a Fake that always returns the happy answer is useless).

## File layout

`tests/fakes/<name>.py` for primitives (`clock.py`, `id_generator.py`).
`tests/fakes/repositories/<entity>.py` for repos.

Mirror the production structure under `tests/fakes/`.

## Pattern

```python
from {{ cookiecutter.package_name }}.application.<module> import <Abstraction>

class InMemory<Abstraction>(<Abstraction>):
    """In-memory fake for tests. Acts as Spy via its public state."""

    def __init__(self, seed: <SeedType> = ()) -> None:
        self.<state>: <Container> = ...

    async def <abstract_method>(self, ...) -> ...:
        # smallest realistic implementation
        ...
```

## Acting as a Spy

Tests that need to assert "method X was called with payload Y" use the Fake's public state instead of `Mock.assert_called_with`:

```python
fake_email_sender = InMemoryEmailSender()
await use_case.execute(...)
assert fake_email_sender.sent == [Email("alice@example.com")]
```

This keeps the test asserting on **observable behaviour** (a message was sent), not implementation details (which collaborator method got called with which arguments).

## Mistakes to avoid

- Importing from `infrastructure/` in a Fake (couples Fakes to concretes).
- Using `random.*` without a seed.
- Using `datetime.now()` — Fakes of `Clock` accept the time as a parameter.
- Implementing only the happy path — Fakes must enforce the same invariants as the real implementation (uniqueness constraints, validation, etc.) or unit tests will pass on impossible scenarios.
