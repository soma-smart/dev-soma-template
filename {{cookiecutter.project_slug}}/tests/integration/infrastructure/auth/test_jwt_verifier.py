"""Integration tests for :class:`JwtTokenVerifier` — round-trip with PyJWT.

Pure stdlib + PyJWT — no testcontainers, but lives in ``integration/``
because it exercises a real crypto library, not a Fake. Each test signs a
JWT then verifies it through the production binding.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from {{ cookiecutter.package_name }}.domain.exceptions.auth import InvalidTokenError
from {{ cookiecutter.package_name }}.infrastructure.auth.jwt_verifier import JwtTokenVerifier

SECRET = "test-secret-do-not-use-in-prod"  # noqa: S105


def _sign(payload: dict[str, Any], *, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _claims(
    *,
    sub: str = "alice",
    exp_offset_seconds: int = 60,
    aud: str | None = None,
    iss: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sub": sub,
        "exp": datetime.now(tz=UTC) + timedelta(seconds=exp_offset_seconds),
    }
    if aud is not None:
        payload["aud"] = aud
    if iss is not None:
        payload["iss"] = iss
    if extra:
        payload.update(extra)
    return payload


@pytest.mark.integration
def test_given_valid_hs256_token_when_verifying_then_returns_current_user() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET)
    token = _sign(_claims(extra={"email": "alice@example.com", "roles": ["admin"]}))

    # WHEN
    user = verifier.verify(token)

    # THEN
    assert user.subject == "alice"
    assert user.email == "alice@example.com"
    assert user.roles == ("admin",)


@pytest.mark.integration
def test_given_expired_token_when_verifying_then_raises_invalid_token() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET)
    token = _sign(_claims(exp_offset_seconds=-1))

    # WHEN / THEN
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


@pytest.mark.integration
def test_given_token_signed_with_wrong_secret_when_verifying_then_raises_invalid_token() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET)
    token = _sign(_claims(), secret="another-secret")

    # WHEN / THEN
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


@pytest.mark.integration
def test_given_token_missing_sub_claim_when_verifying_then_raises_invalid_token() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET)
    payload = _claims()
    del payload["sub"]
    token = _sign(payload)

    # WHEN / THEN
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


@pytest.mark.integration
def test_given_audience_mismatch_when_verifying_then_raises_invalid_token() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET, audience="expected-aud")
    token = _sign(_claims(aud="other-aud"))

    # WHEN / THEN
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


@pytest.mark.integration
def test_given_keycloak_style_roles_claim_path_when_verifying_then_extracts_roles() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(
        algorithm="HS256",
        secret=SECRET,
        roles_claim="realm_access.roles",
    )
    token = _sign(
        _claims(extra={"realm_access": {"roles": ["admin", "user"]}}),
    )

    # WHEN
    user = verifier.verify(token)

    # THEN
    assert user.roles == ("admin", "user")


@pytest.mark.integration
def test_given_missing_roles_path_when_verifying_then_returns_empty_roles() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET, roles_claim="realm_access.roles")
    token = _sign(_claims())  # no realm_access in payload

    # WHEN
    user = verifier.verify(token)

    # THEN
    assert user.roles == ()
