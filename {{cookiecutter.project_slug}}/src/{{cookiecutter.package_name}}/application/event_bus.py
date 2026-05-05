"""Event bus abstraction for domain event propagation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EventBus(ABC):
    """Abstract publisher of domain events."""

    @abstractmethod
    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        """Publish a domain event to subscribers."""
