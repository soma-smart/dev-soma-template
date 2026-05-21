"""DTOs for user use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser


@dataclass(frozen=True, slots=True)
class EnsureUserExistsInput:
    """Input DTO for ``EnsureUserExistsUseCase``.

    The single field is the verified ``CurrentUser`` carrying the JWT
    subject, email and name. The use case treats this as the authoritative
    identity source for SSO auto-provisioning.
    """

    current_user: CurrentUser


@dataclass(frozen=True, slots=True)
class EnsureUserExistsOutput:
    """Output DTO for ``EnsureUserExistsUseCase`` — the persisted user."""

    id: UUID
    subject: str
    email: str
    name: str
    created_at: datetime
