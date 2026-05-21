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
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2AuthorizationCodeBearer,
)
from fastapi.security.base import SecurityBase

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.application.auth.token_verifier import TokenVerifier
from {{ cookiecutter.package_name }}.domain.exceptions.auth import (
    InsufficientPermissionsError,
    MissingTokenError,
)
from {{ cookiecutter.package_name }}.infrastructure.config.settings import Settings, get_settings
from {{ cookiecutter.package_name }}.infrastructure.container import build_token_verifier


def _build_security_scheme(settings: Settings) -> SecurityBase:
    """Pick the OpenAPI security scheme based on Settings.

    When the OAuth2 endpoints are configured (production with a real IdP
    app registration for Swagger UI), the API publishes
    ``OAuth2AuthorizationCodeBearer`` and Swagger UI renders a clickable
    "Authorize" button that triggers the full IdP redirect flow.

    Otherwise the API falls back to ``HTTPBearer`` — Swagger UI still
    shows an "Authorize" button but the dev pastes a JWT manually
    (typical local-dev flow with ``AUTH_JWT_ALGORITHM=HS256``).

    ``auto_error=False`` in both cases keeps our ``MissingTokenError``
    path the single source of truth for missing/malformed headers
    (no FastAPI-default ``HTTPException`` leaking through).
    """
    if settings.swagger_oauth2_authorization_url and settings.swagger_oauth2_token_url:
        return OAuth2AuthorizationCodeBearer(
            authorizationUrl=settings.swagger_oauth2_authorization_url,
            tokenUrl=settings.swagger_oauth2_token_url,
            scopes=settings.swagger_oauth2_scopes,
            description=(
                "Click Authorize to be redirected to your IdP for a real "
                "SSO login (Authorization Code + PKCE)."
            ),
            auto_error=False,
        )
    return HTTPBearer(
        bearerFormat="JWT",
        description=(
            "Paste a JWT issued by your IdP (Azure AD, Auth0, Keycloak…). "
            "Switch to the OAuth2 flow by setting "
            "``AUTH_SWAGGER_OAUTH2_AUTHORIZATION_URL`` + "
            "``AUTH_SWAGGER_OAUTH2_TOKEN_URL``."
        ),
        auto_error=False,
    )


# Scheme instance pinned at import time. ``Security(...)`` requires an
# instance, not a factory — settings only change when the process
# restarts, so reading them once at module load is safe in practice.
_bearer_scheme = _build_security_scheme(get_settings())


def get_token_verifier(settings: Settings = Depends(get_settings)) -> TokenVerifier:
    """Inject the production ``TokenVerifier``."""
    return build_token_verifier(settings)


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | str | None = Security(_bearer_scheme),
) -> str:
    """Extract the bearer token via the active OpenAPI security scheme.

    The scheme is either ``HTTPBearer`` (paste-once UX in Swagger) or
    ``OAuth2AuthorizationCodeBearer`` (IdP redirect flow), picked at
    module load by :func:`_build_security_scheme`. Both expose the bearer
    token to FastAPI in compatible shapes:

    * ``HTTPBearer`` yields ``HTTPAuthorizationCredentials | None``
    * ``OAuth2AuthorizationCodeBearer`` yields ``str | None`` (the bare
      token, already stripped of the ``Bearer`` prefix)

    Raises:
        MissingTokenError: header absent or not in ``Bearer <token>`` form.
    """
    if credentials is None:
        raise MissingTokenError()
    if isinstance(credentials, str):
        # OAuth2AuthorizationCodeBearer already returns the bare token.
        if not credentials:
            raise MissingTokenError(reason="malformed_authorization_header")
        return credentials
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
