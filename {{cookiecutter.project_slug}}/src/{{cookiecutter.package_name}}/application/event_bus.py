"""Event bus abstraction for domain event propagation."""

from __future__ import annotations

from typing import Any, Protocol


class EventBus(Protocol):
    """Structural contract for a publisher of domain events."""

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        """Publish a domain event to subscribers."""
        ...
