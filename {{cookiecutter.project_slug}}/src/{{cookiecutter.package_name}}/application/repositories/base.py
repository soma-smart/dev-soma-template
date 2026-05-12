"""Base repository protocol."""

from __future__ import annotations

from typing import Protocol


class Repository[TEntity, TId](Protocol):
    """Generic persistence contract for an entity.

    Concrete implementations provide ``add`` and ``find_by_id`` and may add
    domain-specific finders (``find_by_email``, ``search_active``, ...). Sub-
    protocols inherit and declare those extra methods (see ``UserRepository``).
    """

    async def add(self, entity: TEntity, /) -> None:
        """Persist ``entity``, raising a ``DomainError`` on uniqueness violation."""
        ...

    async def find_by_id(self, id: TId, /) -> TEntity | None:
        """Return the entity with the given identifier or ``None`` when absent."""
        ...
