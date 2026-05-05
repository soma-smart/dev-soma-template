"""Base domain exception."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for all business-meaningful exceptions raised by the domain.

    Subclasses MUST set a stable ``code`` (SCREAMING_SNAKE_CASE machine identifier)
    and provide a ``message`` understandable by an end user. The presentation
    layer is responsible for translating ``DomainError`` into HTTP responses.

    Attributes:
        code: stable machine identifier of the error (e.g. ``USER_ALREADY_EXISTS``).
        message: human-readable English message safe to show to an end user.
        context: optional dict of additional fields surfaced in technical logs.
    """

    code: str = "DOMAIN_ERROR"
    message: str = "A business rule was violated."

    def __init__(self, message: str | None = None, **context: Any) -> None:
        self.message = message or self.message
        self.context: dict[str, Any] = dict(context)
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, context={self.context!r})"
