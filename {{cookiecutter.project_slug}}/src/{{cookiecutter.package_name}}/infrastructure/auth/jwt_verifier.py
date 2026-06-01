"""JWT-based ``TokenVerifier`` binding.

Two algorithms are supported out of the box, chosen via
``Settings.auth_jwt_algorithm``:

* ``HS256`` — symmetric, shared secret. Simple for internal-only services
  and dev. The secret comes from ``Settings.auth_jwt_secret``.
* ``RS256`` — asymmetric, public keys fetched from a JWKS URL. The standard
  for a real IdP (Keycloak, Auth0, Okta, AWS Cognito, …). The JWKS URL
  comes from ``Settings.auth_jwt_jwks_url`` and keys are cached by PyJWT.

Audience and issuer are checked when configured (``auth_jwt_audience``,
``auth_jwt_issuer``). Leaving them empty disables the check.

The role-extraction path is configurable via ``auth_jwt_roles_claim`` —
defaults to ``"roles"`` (flat top-level list). For Keycloak set it to
``"realm_access.roles"``; for Auth0 the namespaced claim
``"https://<your-ns>/roles"``.

Swap to a different IdP: change this file's body or replace the binding in
``infrastructure/container.build_token_verifier``. Nothing else needs to
change.
"""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWKClient

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.domain.exceptions.auth import InvalidTokenError


class JwtTokenVerifier:
    """Verify a bearer JWT and project it onto ``CurrentUser``."""

    def __init__(  # noqa: PLR0913 — every kw flows from Settings.auth_jwt_*
        self,
        *,
        algorithm: str,
        secret: str | None = None,
        jwks_url: str | None = None,
        audience: str | None = None,
        issuer: str | None = None,
        roles_claim: str = "roles",
    ) -> None:
        if algorithm == "HS256":
            if not secret:
                raise ValueError("HS256 requires Settings.auth_jwt_secret to be set.")
        elif algorithm == "RS256":
            if not jwks_url:
                raise ValueError("RS256 requires Settings.auth_jwt_jwks_url to be set.")
        else:
            raise ValueError(f"Unsupported auth_jwt_algorithm={algorithm!r}; use HS256 or RS256.")

        self._algorithm = algorithm
        self._secret = secret
        self._audience = audience
        self._issuer = issuer
        self._roles_claim = roles_claim
        # PyJWKClient caches keys with a 5 min default lifespan; safe to reuse.
        self._jwks_client = PyJWKClient(jwks_url) if jwks_url else None

    def verify(self, token: str) -> CurrentUser:
        """Decode + validate the token, returning the caller identity."""
        try:
            claims = self._decode(token)
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError(reason=type(exc).__name__) from exc

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise InvalidTokenError(reason="missing_sub_claim")

        email_value = claims.get("email")
        email = email_value if isinstance(email_value, str) else None

        name_value = claims.get("name")
        name = name_value if isinstance(name_value, str) else None

        return CurrentUser(
            subject=subject,
            email=email,
            name=name,
            roles=_extract_roles(claims, self._roles_claim),
            claims=claims,
        )

    def _decode(self, token: str) -> dict[str, Any]:
        if self._algorithm == "HS256":
            return jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience or None,
                issuer=self._issuer or None,
                options={"require": ["sub", "exp"]},
            )
        # RS256
        # ``__init__`` guarantees jwks_url is set for RS256; the assert is a
        # defensive check for the type narrower (``PyJWKClient | None``).
        if self._jwks_client is None:  # pragma: no cover
            raise InvalidTokenError(reason="jwks_client_missing")
        signing_key = self._jwks_client.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=self._audience or None,
            issuer=self._issuer or None,
            options={"require": ["sub", "exp"]},
        )


def _extract_roles(claims: dict[str, Any], path: str) -> tuple[str, ...]:
    """Walk ``path`` (dotted) through ``claims`` and return a tuple of role strings.

    Returns an empty tuple when the path is missing, points to a non-list,
    or contains non-string entries. Resilience over precision: a misconfigured
    role path should never crash the request — it should just yield no roles.
    """
    cursor: Any = claims
    for segment in path.split("."):
        if not isinstance(cursor, dict) or segment not in cursor:
            return ()
        cursor = cursor[segment]
    if not isinstance(cursor, list):
        return ()
    return tuple(role for role in cursor if isinstance(role, str))
