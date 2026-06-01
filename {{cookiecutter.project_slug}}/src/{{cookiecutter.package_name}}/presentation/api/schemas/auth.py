"""Pydantic schemas for auth-related responses."""

from __future__ import annotations

from pydantic import BaseModel


class WhoamiResponse(BaseModel):
    """Response body for ``GET /v1/auth/whoami``."""

    subject: str
    email: str | None = None
    roles: list[str] = []
