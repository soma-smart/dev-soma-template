---
name: adding-a-domain-exception
description: Add a new DomainError subclass, register its HTTP mapping, write the unit test that raises it. The mapping is mechanically enforced — adding the class without the mapping breaks CI.
when_to_use: A use case needs to signal a business rule violation that no existing DomainError subclass covers. Picked up automatically by the audit-edit Claude hook when you create a class ending in "Error" under domain/exceptions/.
---

# Adding a domain exception

## 1. Pick the bounded context

Group exceptions by what they describe, not by the class that raises them. Put the new class under `domain/exceptions/<bounded_context>.py`:

* `user.py` for everything about user lifecycle, identity, authentication
* `billing.py` for prices, balance, payments
* `inventory.py` for stock, fulfilment

Create the module if it doesn't exist. The User feature ships three working examples in `domain/exceptions/user.py` (`UserAlreadyExistsError`, `UserNotFoundError`) and `domain/value_objects/email.py` (`InvalidEmailError`) — copy the pattern.

## 2. Write the class

Subclass `DomainError`. Set the **class-level** `code` and `default_message` (both are `ClassVar` on the base):

```python
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError


class InsufficientBalanceError(DomainError):
    """Raised when an account has not enough funds for a withdrawal."""

    code = "INSUFFICIENT_BALANCE"
    default_message = "The account does not have sufficient balance."
```

* `code` is **SCREAMING_SNAKE** and **stable** — clients deserialize on it.
* `default_message` is one English sentence safe to show to an end user.
* The class name follows `<Subject><Verb>Error` (`UserAlreadyExistsError`, `OrderCannotBeCancelledError`). See `naming-conventions`.
* The docstring is mandatory (ruff `D101`).

### Optional: rich context for logs

`DomainError.__init__` accepts arbitrary kwargs and stores them under `.context`. Pass anything useful for ops:

```python
raise UserAlreadyExistsError(email=str(email), source="signup-form")
```

The `_instrumented` wrapper in `infrastructure/container.py` extracts `code` and `context` and emits a structured `WARNING` log on the way out — no extra logging code in your use case.

## 3. Register the HTTP mapping

`presentation/api/error_handlers.py`:

```python
ERROR_HTTP_MAPPING: dict[type[DomainError], int] = {
    ...
    InsufficientBalanceError: 402,  # Payment Required
    ...
}
```

The mapping table is the **single source of truth**. The unit test `tests/unit/presentation/test_error_mapping.py` discovers `DomainError.__subclasses__()` automatically and fails the build when a subclass is unmapped — you cannot ship the class without registering it. The Claude `audit-edit.sh` hook also flags it the moment you save the new class file.

If you are tempted to give the same exception type a different HTTP status in different endpoints, that means the type itself is not specific enough — extract a more precise `…Error`. Per-endpoint overrides are not supported on purpose.

## 4. Raise it from the use case (TDD red first)

Following `tdd-workflow`:

```python
# tests/unit/application/test_<use_case>.py
async def test_given_<context>_when_<action>_then_raises_<error>(
    create_user_use_case: CreateUserUseCase,
) -> None:
    # GIVEN: setup that triggers the rule
    ...

    # WHEN / THEN
    with pytest.raises(InsufficientBalanceError) as excinfo:
        await create_user_use_case.execute(...)
    assert excinfo.value.code == "INSUFFICIENT_BALANCE"
```

Then the production code that makes it pass:

```python
# application/use_cases/<use_case>.py
if account.balance < amount:
    raise InsufficientBalanceError(
        account_id=str(account.id), required=str(amount), available=str(account.balance)
    )
```

`just test` until green, then `just mutate` to confirm the test would also catch a "no raise" mutation.

## 5. E2E impact (only if the error reaches the API)

If the use case is exposed through an HTTP endpoint **and** this error is the *primary* error path for that endpoint, replace the existing "1 critical error" e2e test with one targeting the new exception. Otherwise leave the e2e suite alone — branch coverage lives at the unit level.

## HTTP code cheat sheet

| Domain meaning | HTTP |
|---|---|
| Generic bad request, malformed body that Pydantic did not catch | 400 |
| Missing resource (lookup returned `None`) | 404 |
| Conflict (duplicate, version mismatch) | 409 |
| Resource removed permanently | 410 |
| Validation failure on a well-shaped input (business rule) | 422 |
| Authentication missing | 401 |
| Authorization insufficient | 403 |
| Payment required | 402 |
| Resource locked (concurrent edit) | 423 |
| Rate limited | 429 |
| Downstream service unavailable | 503 |
| Internal invariant broken (should never happen) | 500 — the fallback handler covers it |
