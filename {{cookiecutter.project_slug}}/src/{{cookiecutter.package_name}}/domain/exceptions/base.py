"""Base domain exception."""

from __future__ import annotations

from typing import Any, ClassVar


class DomainError(Exception):
    """Base for all business-meaningful exceptions raised by the domain.

    Subclasses MUST set ``code`` (a stable SCREAMING_SNAKE machine
    identifier) and ``default_message`` (an English, end-user safe sentence).
    The presentation layer translates ``DomainError`` into HTTP responses
    via ``ERROR_HTTP_MAPPING``; the DI container's ``_instrumented`` wrapper
    serializes ``code`` and ``context`` into structured warning logs.

    Class attributes:
        code: stable machine identifier (e.g. ``USER_ALREADY_EXISTS``).
        default_message: fallback message when the caller does not provide one.

    Instance attributes:
        message: human-readable English message safe to show to an end user.
        context: dict of additional fields surfaced in technical logs.
    """

    code: ClassVar[str] = "DOMAIN_ERROR"
    default_message: ClassVar[str] = "A business rule was violated."

    def __init__(self, message: str | None = None, **context: Any) -> None:
        self.message: str = message or self.default_message
        self.context: dict[str, Any] = dict(context)
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, context={self.context!r})"
