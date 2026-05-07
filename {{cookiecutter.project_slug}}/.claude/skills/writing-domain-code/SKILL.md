---
name: writing-domain-code
description: Hard rules + modelling patterns for code under src/<pkg>/domain/. The domain is pure, deterministic, third-party-free. Use whenever editing or designing entities, value objects, or business exceptions.
when_to_use: Editing any file under src/<pkg>/domain/. Designing a new entity / value object / business rule. Reviewing a domain change.
---

# Writing domain code

## Hard rules (mechanically enforced)

1. **No third-party imports.** Stdlib only. `pydantic`, `sqlalchemy`, `httpx`, `structlog`, `fastapi` — all forbidden here. Enforced by `scripts/checks/no_third_party_in_domain.py`.

2. **No non-deterministic side effects.** `datetime.now()`, `datetime.utcnow()`, `uuid.uuid4()`, `random.*`, `time.time()` are forbidden — they break the **R**epeatable property of FIRST tests (same input must give same output, every machine, every run). Use the `Clock`, `IdGenerator`, `RandomSource` abstractions from `application/`. The domain may freely **type** with `datetime`, `UUID`, etc. — only the side-effecting calls are banned.

3. **No `float`** for monetary or precise quantities. Use `decimal.Decimal`. Enforced by `scripts/checks/no_float_in_domain.py` (scoped to `domain/` only — `RandomSource.next_float` legitimately exists in `application/`).

4. **No log calls.** The domain is silent. Logging is an infrastructure concern; the domain raises typed exceptions instead. The error handler at the presentation boundary logs them with full context.

5. **TZ-aware datetimes only.** Always pass `datetime` with `tz=UTC` (or another explicit zone). A naive `datetime` is treated as a bug.

## What `domain/` may import

Stdlib only. The typical surface is:

* `datetime`, `time`, `zoneinfo` for time types
* `decimal.Decimal` for money / precise quantities
* `uuid.UUID` for identifier types
* `enum`, `typing`, `dataclasses`, `abc`, `re`
* `pathlib.Path` if you really need it
* Other modules under `{{ cookiecutter.package_name }}.domain.*`

Plus the base classes shipped with the template:

```python
from {{ cookiecutter.package_name }}.domain.entities.base import Entity
from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError
```

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


# Hypothetical example for illustration — Money / NegativeMoneyError /
# InvalidCurrencyError are not shipped with the template; use the same
# pattern for your own value objects.
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

The User entity shipped with the template at `domain/entities/user.py` is the canonical reference.

### Business exceptions — `domain/exceptions/`

Subclass `DomainError`. Set the class-level `code` (SCREAMING_SNAKE — clients depend on it) and `default_message` (one English sentence safe to show to an end user). When you add a new one you **must** add an entry in `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING` — see `adding-a-domain-exception`.

```python
from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError


class InsufficientBalanceError(DomainError):
    """Raised when an account has not enough funds for a withdrawal."""

    code = "INSUFFICIENT_BALANCE"
    default_message = "The account does not have sufficient balance."
```

The class itself is named `<Subject><Verb>Error` — e.g. `UserAlreadyExistsError`, `OrderCannotBeCancelledError`. See `naming-conventions` for the full naming rules.

### Domain services — when an operation spans multiple entities

If an operation does not naturally belong to a single entity (e.g. transferring funds between two accounts), put it as a free function or a small stateless class in `domain/services/<name>.py`. Domain services follow the same purity rules as entities — no third party, no side effects.

Most projects do not need this. Reach for it only when "this method on `Account.withdraw_to(other)` would mean Account knows about its peers" feels wrong.
