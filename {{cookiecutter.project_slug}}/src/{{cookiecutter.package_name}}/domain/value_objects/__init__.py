"""Value objects.

Value objects are ``@dataclass(frozen=True, slots=True)`` with validation in
``__post_init__``. Equality is by value (inherited from dataclass). Examples:
``Email``, ``Money``, ``UserId``.
"""
