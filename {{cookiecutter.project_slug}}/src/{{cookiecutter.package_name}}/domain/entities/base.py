"""Base class for entities."""

from __future__ import annotations

from abc import ABC


class Entity[TId](ABC):
    """Domain entity with identity-based equality.

    Subclasses set ``self.id: TId`` in their ``__init__`` and inherit
    ``__eq__`` / ``__hash__`` keyed on ``(type, id)``. Mutations must go
    through named methods (``order.cancel()``), never direct attribute
    assignment.
    """

    id: TId

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and getattr(other, "id", None) == self.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id!r})"
