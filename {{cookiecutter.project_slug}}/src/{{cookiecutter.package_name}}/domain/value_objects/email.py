"""``Email`` value object."""

from __future__ import annotations

import re
from dataclasses import dataclass

from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError
from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject

# Pragmatic RFC-ish regex. Strict RFC 5321 parsing is out of scope; this catches
# the vast majority of typos at boundary entry without false-rejecting valid
# corporate addresses.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class InvalidEmailError(DomainError):
    """Raised when an ``Email`` is constructed from a malformed string."""

    code = "INVALID_EMAIL"
    default_message = "The email address is not valid."


@dataclass(frozen=True, slots=True)
class Email(ValueObject):
    """Validated email address. Stored lowercase to enforce case-insensitive equality."""

    value: str

    def __post_init__(self) -> None:
        if not _EMAIL_RE.match(self.value):
            raise InvalidEmailError(value=self.value)
        # Force lowercase normalisation through __setattr__ since the dataclass is frozen.
        object.__setattr__(self, "value", self.value.lower())

    def __str__(self) -> str:
        return self.value
