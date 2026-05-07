---
name: tdd-workflow
description: Strict red-green-refactor TDD with mutation testing as the fourth step. Mandatory for any change that affects behaviour in domain/ or application/. NOT for pure refactor that preserves behaviour.
when_to_use: User asks to add a feature, fix a bug, or change logic. Skip this skill only when the change is a pure-refactor (rename, extract, inline) that does not change observable behaviour.
---

# TDD workflow

Four steps, in order. Step 4 is the one everyone forgets and the one mutmut catches in CI.

## 1. Red — write the failing test first

A test that fails for the right reason (assertion fails, not `ImportError`).

- Lives under `tests/unit/domain/` or `tests/unit/application/`.
- Naming + body format are mandatory — see the `writing-tests` skill.
- Use Fakes from `tests/fakes/`. Never `unittest.mock`. Never `Mock`, `MagicMock`, `Spy`, `Stub`.

Run `just test` and confirm the new test **fails**.

## 2. Green — minimum code to pass

Implement the smallest amount of production code that turns the test green.

- No additional features. No "while I'm here". No premature abstraction.
- If you find yourself adding a second branch the test does not cover, stop, write a second failing test, then add the branch.

Run `just test` and confirm it passes.

## 3. Refactor — clean up under the green bar

While every test is green: rename, extract, inline, deduplicate. After each meaningful change, re-run `just test`. A red bar during refactor means undo, not push through.

## 4. Mutate — let mutmut grade your tests

```bash
just mutate           # mutmut on domain + application (paths set in pyproject)
just mutate-results   # show the latest report
```

A surviving mutant is a free hole through your test suite. Treat it like a new red bar:

1. Read the surviving mutant — it shows the line and the mutation that survived.
2. Write a new failing test that would die against that mutation.
3. Re-run `just test` (red), then re-run the steps.

The CI `ci-mutation.yml` workflow enforces a 90% kill rate floor on PRs that touch `src/` or `tests/`.

## Worked example: `Email.value` lower-cased

### Red

```python
# tests/unit/domain/test_email.py
def test_given_uppercase_input_when_constructing_email_then_value_is_lowercase() -> None:
    # GIVEN
    raw = "Alice@Example.COM"

    # WHEN
    email = Email(raw)

    # THEN
    assert email.value == "alice@example.com"
```

`just test` → fails (`assert "Alice@Example.COM" == "alice@example.com"`).

### Green

```python
# domain/value_objects/email.py
@dataclass(frozen=True, slots=True)
class Email(ValueObject):
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", self.value.lower())
```

`just test` → passes.

### Refactor

Add the regex validation that lives in the production code. Run `just test` between every change.

### Mutate

`just mutate` flips `self.value.lower()` to `self.value.upper()` and `self.value.title()`. Both must die (they do, because the test asserts the exact lowercase form).

## Hard rules

- **No production code without a failing test first.** Non-negotiable.
- **Never disable a failing test to make CI green.** Either fix the test or fix the code, or revert the change.
- **Never skip step 4 when `domain/` or `application/` logic was touched.** Line coverage without mutation kill rate is a comforting lie.
- **Bug fixes follow the same loop.** A bug = a missing test. Write the test that reproduces the bug (red), then fix the code (green).
