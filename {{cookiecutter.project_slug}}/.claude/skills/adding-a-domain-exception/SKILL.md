---
name: adding-a-domain-exception
description: Steps to add a new DomainError subclass, including the mandatory HTTP mapping registration and test.
when_to_use: User asks for a new business error / exception type; you discover a missing error during use case design.
---

# Adding a domain exception

## Steps

1. **Decide the bounded context**: pick the right module under `domain/exceptions/` (e.g., `user.py`, `billing.py`, `inventory.py`). Create it if it doesn't exist.

2. **Write the class**:

```python
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError

class InsufficientBalanceError(DomainError):
    """Raised when an account has not enough funds for a withdrawal."""

    code = "INSUFFICIENT_BALANCE"
    message = "The account does not have sufficient balance for this operation."
```

The `code` is SCREAMING_SNAKE and stable (clients depend on it). The `message` is end-user safe English. Add a docstring (D rule). Optional context payload via `__init__(**context)`.

3. **Register the HTTP mapping** in `presentation/api/error_handlers.py`:

```python
ERROR_HTTP_MAPPING: dict[type[DomainError], int] = {
    ...
    InsufficientBalanceError: 402,  # Payment Required
    ...
}
```

The mapping table is the single source of truth. Without an entry the unit test `tests/unit/presentation/test_error_mapping.py` fails.

4. **Reuse it from where it is raised**: typically a use case that detects the rule violation. Add a unit test that exercises the raise.

5. **Update the e2e test** if the new error flows through an existing endpoint and is "critical": replace or add the existing critical-error test case.

## HTTP code cheatsheet

| Domain meaning | HTTP |
|---|---|
| Validation failure (input shape) | 422 |
| Missing resource | 404 |
| Conflict (duplicate, version) | 409 |
| Authorization missing | 401 |
| Authorization insufficient | 403 |
| Payment required | 402 |
| Rate limited | 429 |
| Internal invariant broken (should not happen) | 500 (the fallback handler covers it) |
