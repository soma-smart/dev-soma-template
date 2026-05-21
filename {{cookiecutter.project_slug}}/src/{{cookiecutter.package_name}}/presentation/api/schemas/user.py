"""Pydantic schemas for the user resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UserReadSchema(BaseModel):
    """Response body for user reads (``GET /v1/users/me``)."""

    id: UUID
    subject: str
    email: str
    name: str
    created_at: datetime
