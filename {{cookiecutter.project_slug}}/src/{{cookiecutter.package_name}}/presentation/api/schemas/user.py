"""Pydantic schemas for the user resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreateSchema(BaseModel):
    """Request body for ``POST /v1/users``."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=255)


class UserReadSchema(BaseModel):
    """Response body for user reads."""

    id: UUID
    email: str
    name: str
    created_at: datetime
