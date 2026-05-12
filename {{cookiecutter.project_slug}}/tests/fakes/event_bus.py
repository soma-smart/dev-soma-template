"""Fake ``EventBus`` for unit tests.

Records every ``(event_name, payload)`` tuple in ``published``. Tests assert
on that list as the Spy view of "did the use case emit what it should".
"""

from __future__ import annotations

from typing import Any


class InMemoryEventBus:
    """In-memory ``EventBus`` that records published events for assertion."""

    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        """Append ``(event_name, payload)`` to ``self.published``."""
        self.published.append((event_name, payload))
