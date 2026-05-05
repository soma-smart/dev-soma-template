"""Audit log abstraction for user-meaningful events.

Use cases call ``AuditLog.record(...)`` to persist a business audit entry.
The default infrastructure implementation writes to a relational ``audit_log``
table. Projects that don't need auditing wire ``NullAuditLog``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class AuditLog(ABC):
    """Abstract sink for domain audit events surfaced to end users / ops."""

    @abstractmethod
    async def record(
        self,
        event_name: str,
        actor_id: UUID | None,
        payload: dict[str, Any],
    ) -> None:
        """Persist an audit entry."""
