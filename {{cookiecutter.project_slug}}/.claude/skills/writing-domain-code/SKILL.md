---
name: writing-domain-code
description: Hard rules + modelling patterns for code under src/<pkg>/domain/ — purity, entities, value objects, and domain exceptions (with their HTTP mapping). The domain is pure, deterministic, third-party-free.
when_to_use: Editing any file under src/<pkg>/domain/. Designing a new entity / value object / business rule. Adding a new DomainError subclass. Reviewing a domain change.
---

# Writing domain code

## Hard rules (mechanically enforced)

1. **No third-party imports.** Stdlib only. `pydantic`, `sqlalchemy`, `httpx`, `structlog`, `fastapi` — all forbidden here. Enforced by `scripts/checks/no_third_party_in_domain.py`.

2. **No non-deterministic side effects.** `datetime.now()`, `datetime.utcnow()`, `uuid.uuid4()`, `random.*`, `time.time()` are forbidden — they break the **R**epeatable property of FIRST tests. Use the `Clock`, `IdGenerator`, `RandomSource` abstractions from `application/`. The domain may freely **type** with `datetime`, `UUID`, etc. — only the side-effecting calls are banned.

3. **No log calls.** The domain is silent. Logging is an infrastructure concern; the domain raises typed exceptions instead.

4. **TZ-aware datetimes only.** Always pass `datetime` with `tz=UTC` (or another explicit zone). A naive `datetime` is treated as a bug.

## What `domain/` may import

Stdlib only. The typical surface is:

- `datetime`, `time`, `zoneinfo` for time types
- `decimal.Decimal` for money / precise quantities
- `uuid.UUID` for identifier types
- `enum`, `typing`, `dataclasses`, `abc`, `re`
- `pathlib.Path` if you really need it
- Other modules under `{{ cookiecutter.package_name }}.domain.*`

Plus the base classes shipped with the template:

```python
from {{ cookiecutter.package_name }}.domain.entities.base import Entity
from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError
```

---

## Modelling

### Value objects — `domain/value_objects/`

Frozen + slotted dataclass inheriting from `ValueObject` (marker; preserves slots in subclasses). Validation in `__post_init__`. Equality is value-based (inherited from dataclass).

A typed identifier wrapping a primitive — the canonical small VO:

```python
from dataclasses import dataclass
from uuid import UUID

from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject


@dataclass(frozen=True, slots=True)
class UserId(ValueObject):
    """Strongly-typed wrapper around a user identifier UUID."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)
```

A VO that enforces a business invariant on construction:

```python
from decimal import Decimal


# Hypothetical example — Money / NegativeMoneyError / InvalidCurrencyError
# are not shipped; use the same pattern for your own VOs.
@dataclass(frozen=True, slots=True)
class Money(ValueObject):
    amount: Decimal
    currency: str  # ISO-4217

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise NegativeMoneyError(amount=str(self.amount))
        if len(self.currency) != 3 or not self.currency.isupper():
            raise InvalidCurrencyError(currency=self.currency)
```

`frozen=True` makes the instance immutable (hash works, instance is safe to share). `slots=True` saves memory and prevents typos creating new attributes.

### Entities — `domain/entities/`

Inherit from `Entity[TId]`. `__eq__` and `__hash__` are derived from `(type, self.id)` — you only set attributes in `__init__`. Mutations go through **named methods** (`order.cancel()`, `account.credit(amount)`), never direct attribute assignment from outside the class.

```python
# Hypothetical example — copy the pattern.
from {{ cookiecutter.package_name }}.domain.entities.base import Entity


class Order(Entity[OrderId]):
    """A customer order."""

    def __init__(self, *, id: OrderId, items: list[OrderLine], status: OrderStatus) -> None:
        self.id = id
        self._items = list(items)
        self._status = status

    def cancel(self) -> None:
        if self._status is OrderStatus.SHIPPED:
            raise OrderCannotBeCancelledError(order_id=str(self.id))
        self._status = OrderStatus.CANCELLED
```

The User entity at `domain/entities/user.py` is the canonical reference.

### Domain services — when an operation spans multiple entities

If an operation does not naturally belong to a single entity (e.g. transferring funds between two accounts), put it as a free function or a small stateless class in `domain/services/<name>.py`. Domain services follow the same purity rules.

Most projects do not need this. Reach for it only when "this method on `Account.withdraw_to(other)` would mean Account knows about its peers" feels wrong.

---

## Domain exceptions

Every business rule violation surfaces as a typed `DomainError` subclass. The class name + `code` + HTTP mapping form a stable contract clients depend on.

### 1. Pick the bounded context

Group exceptions by what they describe, not by the class that raises them. Put the new class under `domain/exceptions/<bounded_context>.py`:

- `user.py` for everything about user lifecycle, identity, authentication
- `billing.py` for prices, balance, payments
- `inventory.py` for stock, fulfilment

Create the module if it doesn't exist. The User feature ships three working examples in `domain/exceptions/user.py` (`UserAlreadyExistsError`, `UserNotFoundError`) and `domain/value_objects/email.py` (`InvalidEmailError`) — copy the pattern.

### 2. Write the class

Subclass `DomainError`. Set the **class-level** `code` and `default_message` (both are `ClassVar` on the base):

```python
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError


class InsufficientBalanceError(DomainError):
    """Raised when an account has not enough funds for a withdrawal."""

    code = "INSUFFICIENT_BALANCE"
    default_message = "The account does not have sufficient balance."
```

- `code` is **SCREAMING_SNAKE** and **stable** — clients deserialize on it.
- `default_message` is one English sentence safe to show to an end user.
- The class name follows `<Subject><Verb>Error` (`UserAlreadyExistsError`, `OrderCannotBeCancelledError`).
- The docstring is mandatory (ruff `D101`).

### Optional: rich context for logs

`DomainError.__init__` accepts arbitrary kwargs and stores them under `.context`:

```python
raise UserAlreadyExistsError(email=str(email), source="signup-form")
```

The `_instrumented` wrapper in `infrastructure/container.py` extracts `code` and `context` and emits a structured `WARNING` log — no extra logging code in your use case.

### 3. Register the HTTP mapping

`presentation/api/error_handlers.py`:

```python
ERROR_HTTP_MAPPING: dict[type[DomainError], int] = {
    ...
    InsufficientBalanceError: 402,  # Payment Required
    ...
}
```

The mapping table is the **single source of truth**. The unit test `tests/unit/presentation/test_error_mapping.py` discovers `DomainError.__subclasses__()` automatically and fails the build when a subclass is unmapped. The Claude `audit-edit.sh` hook also flags it the moment you save the new class file.

If you are tempted to give the same exception type a different HTTP status in different endpoints, that means the type itself is not specific enough — extract a more precise `…Error`. Per-endpoint overrides are not supported on purpose.

### 4. Raise it from the use case (TDD red first)

Following `tdd-workflow`:

```python
# tests/unit/use_cases/test_<verb>_<noun>.py
async def test_given_<context>_when_<action>_then_raises_<error>(
    <use_case_fixture>: <UseCaseClass>,
) -> None:
    # GIVEN: setup that triggers the rule
    ...

    # WHEN / THEN
    with pytest.raises(InsufficientBalanceError) as excinfo:
        await <use_case_fixture>.execute(...)
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

### 5. E2E impact (only if the error reaches the API)

If the use case is exposed through an HTTP endpoint **and** this error is the *primary* error path for that endpoint, replace the existing "1 critical error" e2e test with one targeting the new exception. Otherwise leave the e2e suite alone — branch coverage lives at the unit level.

### HTTP code cheat sheet

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
