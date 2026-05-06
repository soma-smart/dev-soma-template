"""Base abstract repository."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Repository[TEntity, TId](ABC):
    """Generic persistence contract for an entity.

    Concrete subclasses implement ``add`` and ``find_by_id`` and add
    domain-specific finders (``find_by_email``, ``search_active``, ...).
    """

    @abstractmethod
    async def add(self, entity: TEntity, /) -> None:
        """Persist ``entity``, raising a ``DomainError`` on uniqueness violation."""

    @abstractmethod
    async def find_by_id(self, id: TId, /) -> TEntity | None:
        """Return the entity with the given identifier or ``None`` when absent."""
