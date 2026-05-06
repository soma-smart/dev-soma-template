"""Base class for use cases."""

from __future__ import annotations

from abc import ABC, abstractmethod


class UseCase[TInput, TOutput](ABC):
    """Single-responsibility orchestrator with one async entry point.

    Subclasses implement ``execute(input)``. Cross-cutting concerns
    (tracing, structured logging) are added by the DI container via the
    ``_instrumented`` wrapper — never inside the use case itself, to keep
    the application layer free of observability imports.
    """

    @abstractmethod
    async def execute(self, input: TInput) -> TOutput:
        """Run the use case against ``input`` and return the produced output."""
