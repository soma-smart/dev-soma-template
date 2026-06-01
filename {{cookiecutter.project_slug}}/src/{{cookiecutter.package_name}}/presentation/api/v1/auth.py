"""Auth-related v1 endpoints.

Currently exposes ``GET /v1/auth/whoami`` as the canonical example of a
protected route. Real projects add their own endpoints; see the
``adding-auth`` skill for the protection patterns.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import get_current_user
from {{ cookiecutter.package_name }}.presentation.api.schemas.auth import WhoamiResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get(
    "/whoami",
    response_model=WhoamiResponse,
    summary="Return the authenticated caller's identity",
)
async def whoami(user: CurrentUser = Depends(get_current_user)) -> WhoamiResponse:
    """Echo the verified caller identity. Used as the auth probe by the e2e tests."""
    return WhoamiResponse(subject=user.subject, email=user.email, roles=list(user.roles))
