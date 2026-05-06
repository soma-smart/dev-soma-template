---
name: writing-domain-code
description: Rules for code inside src/<pkg>/domain/. Use when editing any file under domain/.
when_to_use: Editing src/<pkg>/domain/**, designing entities or value objects, modelling business rules.
---

# Writing domain code

## Hard rules (enforced)

1. **No third-party imports.** Stdlib only. `Pydantic`, `SQLAlchemy`, `httpx`, `structlog` are forbidden here. Enforced by `scripts/checks/no_third_party_in_domain.py`.
2. **No non-deterministic side effects.** `datetime.now()`, `uuid.uuid4()`, `random.*`, `time.time()` are forbidden in this layer (they break test determinism — FIRST). Use the `Clock`, `IdGenerator`, `RandomSource` abstractions defined in `application/`. The domain types `datetime` and `UUID` themselves are fine — only the side-effecting calls are banned.
3. **No `float`** in monetary or precise quantities. Use `decimal.Decimal`. Enforced by `scripts/checks/no_float_in_domain.py`.
4. **No log calls.** The domain is silent; logging happens at infrastructure and presentation boundaries.
5. **TZ-aware datetimes only.** Always store and pass `datetime` with `tz=UTC`.

## Modelling guidelines

### Value objects (`domain/value_objects/`)

`@dataclass(frozen=True, slots=True)` inheriting from `ValueObject` (marker, keeps slots intact). Validation lives in `__post_init__`. Equality is value-based (from dataclass).

```python
from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject


@dataclass(frozen=True, slots=True)
class Money(ValueObject):
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise NegativeMoneyError(amount=str(self.amount))
        if len(self.currency) != 3:
            raise InvalidCurrencyError(currency=self.currency)
```

### Entities (`domain/entities/`)

Inherit from `Entity[TId]`. `__eq__` / `__hash__` are derived from `(type, id)` — you only set attributes in `__init__`. Mutations through named methods (`order.cancel()`), never direct attribute assignment.

```python
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

### Exceptions (`domain/exceptions/`)

Subclass `DomainError`. Set the class-level `code` (SCREAMING_SNAKE) and `default_message` (English, end-user safe). When you add a new one you MUST add an entry in `presentation/api/error_handlers.py::ERROR_HTTP_MAPPING` — see `adding-a-domain-exception`.

```python
class InsufficientBalanceError(DomainError):
    """Raised when an account has not enough funds for a withdrawal."""

    code = "INSUFFICIENT_BALANCE"
    default_message = "The account does not have sufficient balance."
```
