"""Domain entities.

Entities have identity. They are regular Python classes (NOT
``@dataclass``) with explicit ``__init__``, an ``id`` attribute, and
identity-based ``__eq__``/``__hash__``. Mutations go through named methods
(``order.cancel()``), never direct attribute assignment.
"""
