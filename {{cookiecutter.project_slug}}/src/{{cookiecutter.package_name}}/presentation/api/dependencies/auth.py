"""Authentication / authorization FastAPI dependencies.

The chain is:

    Authorization: Bearer <token>
        → get_bearer_token         (extract; raise MissingTokenError on absent)
        → get_current_user         (verify with TokenVerifier; raise InvalidTokenError)
        → require_roles(...)       (assert role membership; raise InsufficientPermissionsError)

Routes opt in to authentication by declaring ``Depends(get_current_user)``
in their handler signature. Public routes do nothing — they stay public.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.application.auth.token_verifier import TokenVerifier
from {{ cookiecutter.package_name }}.domain.exceptions.auth import (
    InsufficientPermissionsError,
    MissingTokenError,
)
from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings, get_settings
from {{ cookiecutter.package_name }}.infrastructure.container import build_token_verifier

# ``HTTPBearer`` is declared as a Security scheme so FastAPI publishes it
# in the OpenAPI document — Swagger UI then renders an "Authorize" button
# where devs paste their JWT once per session. ``auto_error=False`` keeps
# our own ``MissingTokenError`` path: FastAPI does not raise its own
# ``HTTPException`` on missing/malformed headers, so the error mapping in
# ``error_handlers.py`` stays the single source of truth.
_bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description="Paste the JWT issued by your IdP (Azure AD, Auth0, Keycloak…).",
    auto_error=False,
)


def get_token_verifier(settings: Settings = Depends(get_settings)) -> TokenVerifier:
    """Inject the production ``TokenVerifier``."""
    return build_token_verifier(settings)


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> str:
    """Extract the bearer token via the OpenAPI-declared ``HTTPBearer`` scheme.

    Using ``Security(HTTPBearer(...))`` instead of reading the header by
    hand registers the scheme in the OpenAPI document — Swagger UI renders
    the "Authorize" button automatically. ``auto_error=False`` lets us
    keep raising ``MissingTokenError`` so the error mapping stays
    consistent with the rest of the auth chain.

    Raises:
        MissingTokenError: header absent or not in ``Bearer <token>`` form.
    """
    if credentials is None:
        raise MissingTokenError()
    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise MissingTokenError(reason="malformed_authorization_header")
    return credentials.credentials


def get_current_user(
    token: str = Depends(get_bearer_token),
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> CurrentUser:
    """Resolve and verify the caller identity.

    Raises:
        MissingTokenError: 401 — no usable bearer header.
        InvalidTokenError: 401 — token failed verification.
    """
    return verifier.verify(token)


def get_current_user_optional(
    request: Request,
    verifier: TokenVerifier = Depends(get_token_verifier),
) -> CurrentUser | None:
    """Return the verified caller identity, or ``None`` when unauthenticated.

    Use this for routes that work for both anonymous and authenticated
    callers (e.g. listing public content but tailoring it when logged in).
    A malformed or invalid token still raises — it's a client bug, not
    an anonymous request.
    """
    header = request.headers.get("Authorization") or request.headers.get("authorization")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise MissingTokenError(reason="malformed_authorization_header")
    return verifier.verify(token)


def require_roles(*roles: str) -> Callable[[CurrentUser], CurrentUser]:
    """Build a dependency that enforces ``current_user.has_any_role(*roles)``.

    Usage::

        @router.delete("/users/{id}", dependencies=[Depends(require_roles("admin"))])
        async def delete_user(...): ...

    Or pull the user too::

        async def handler(user: CurrentUser = Depends(require_roles("admin"))): ...
    """

    def dependency(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_any_role(*roles):
            raise InsufficientPermissionsError(required_roles=list(roles), held_roles=list(user.roles))
        return user

    return dependency
