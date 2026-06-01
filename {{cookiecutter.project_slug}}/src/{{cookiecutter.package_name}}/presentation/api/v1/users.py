"""User endpoints (API v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from {{ cookiecutter.package_name }}.application.dtos.user import EnsureUserExistsOutput
from {{ cookiecutter.package_name }}.presentation.api.dependencies.users import (
    get_or_provision_user,
)
from {{ cookiecutter.package_name }}.presentation.api.schemas.user import UserReadSchema

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.get("/me", response_model=UserReadSchema)
async def get_current_user_profile(
    user: EnsureUserExistsOutput = Depends(get_or_provision_user),
) -> UserReadSchema:
    """Return the caller's ``User`` row, auto-provisioning on first call.

    The dependency chain verifies the JWT, then maps its subject to a
    persisted ``User`` (creating one from the JWT claims on first sight).
    The handler simply projects the use case output to the response
    schema.
    """
    return UserReadSchema(
        id=user.id,
        subject=user.subject,
        email=user.email,
        name=user.name,
        created_at=user.created_at,
    )
