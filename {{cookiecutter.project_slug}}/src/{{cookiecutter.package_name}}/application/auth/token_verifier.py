"""``TokenVerifier`` protocol.

Production binding lives in :mod:`{{ cookiecutter.package_name }}.infrastructure.auth.jwt_verifier`.
Tests inject :class:`tests.fakes.auth.FakeTokenVerifier`.
"""

from __future__ import annotations

from typing import Protocol

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser


class TokenVerifier(Protocol):
    """Structural contract for a bearer-token verifier."""

    def verify(self, token: str) -> CurrentUser:
        """Validate ``token`` and return the caller identity.

        Raises:
            InvalidTokenError: the token failed verification (bad signature,
                expired, wrong audience/issuer, malformed).
        """
        ...
