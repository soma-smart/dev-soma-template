---
name: tdd-workflow
description: Strict red-green-refactor TDD with mutation testing as the fourth step. Use whenever production code is about to change (feature, bug fix, refactor with behaviour change).
when_to_use: Adding a feature; fixing a bug; any change to logic in domain/ or application/. NOT for pure refactor that does not change behaviour.
---

# TDD workflow

The loop is **mandatory** for any change that affects behaviour in `domain/` or `application/`.

## 1. Red

Write a failing test for the smallest behaviour you want. The test must fail for the right reason (assertion, not import error).

- Tests live under `tests/unit/domain/` or `tests/unit/application/`.
- Format: `test_given_<context>_when_<action>_then_<expectation>` plus `# GIVEN`, `# WHEN`, `# THEN` comment blocks (or `# WHEN / THEN` combined for `pytest.raises`).
- Use Fakes from `tests/fakes/` — no `unittest.mock`, no Mock, no MagicMock, no Stub, no Spy.
- Run `uv run pytest -m unit` and confirm the new test fails.

## 2. Green

Write the **minimum** production code that makes the test pass. No additional features. No "while I'm here". No premature abstraction.

Run `uv run pytest -m unit` and confirm it passes.

## 3. Refactor

Clean up while the bar is green. Names, dead code, duplication. Run the tests after each meaningful change. If you break something, undo and try again.

## 4. Mutate

This is the step everyone forgets. Run mutation testing on the surface you just touched:

```bash
just mutate           # mutmut on domain + application (paths set in pyproject)
just mutate-results   # show the latest report
```

If mutants survive → your tests are too lax → write another failing test that catches the missing behaviour → back to step 1.

The 90% mutation score floor is enforced by `ci-mutation.yml` on PRs.

## Strict rules

- **No production code without a failing test first.** This is non-negotiable.
- **Never disable a failing test to make CI green.** Fix the test or fix the code; reverting the change is also acceptable.
- **Never skip step 4 when domain/application logic was touched.** Coverage without mutation kills hides weak assertions.
