"""Integration tests for :class:`JwtTokenVerifier` — round-trip with PyJWT.

Pure stdlib + PyJWT — no testcontainers, but lives in ``integration/``
because it exercises a real crypto library, not a Fake. Each test signs a
JWT then verifies it through the production binding.

The RS256 branch is special: ``PyJWKClient`` (the JWKS fetcher shipped
by PyJWT) uses ``urllib`` internally, NOT ``httpx``, so ``respx``
cannot intercept its requests. The right tool here is monkeypatching
``PyJWKClient.fetch_data``. For our own httpx-based outbound adapters,
``respx`` remains the canonical pattern (see the
``building-a-feature`` skill, §"Testing external HTTP adapters").
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClient

from {{ cookiecutter.package_name }}.domain.exceptions.auth import InvalidTokenError
from {{ cookiecutter.package_name }}.infrastructure.auth.jwt_verifier import JwtTokenVerifier

SECRET = "test-secret-do-not-use-in-prod"
JWKS_URL = "https://idp.example.com/.well-known/jwks.json"
KID = "test-kid"


def _sign(payload: dict[str, Any], *, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _rsa_keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwks_payload(private_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    return {"keys": [jwk]}


def _sign_rs256(payload: dict[str, Any], *, private_key: rsa.RSAPrivateKey) -> str:
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


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


@pytest.mark.integration
def test_given_token_with_name_claim_when_verifying_then_extracts_name() -> None:
    # GIVEN
    verifier = JwtTokenVerifier(algorithm="HS256", secret=SECRET)
    token = _sign(_claims(extra={"name": "Alice Liddell"}))

    # WHEN
    user = verifier.verify(token)

    # THEN
    assert user.name == "Alice Liddell"


@pytest.mark.integration
def test_given_valid_rs256_token_when_verifying_then_fetches_jwks_and_returns_current_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # GIVEN: the IdP serves a JWKS containing our test public key
    private_key = _rsa_keypair()
    jwks = _jwks_payload(private_key)
    monkeypatch.setattr(PyJWKClient, "fetch_data", lambda _self: jwks)
    verifier = JwtTokenVerifier(algorithm="RS256", jwks_url=JWKS_URL)
    token = _sign_rs256(
        _claims(extra={"email": "alice@example.com", "name": "Alice Liddell"}),
        private_key=private_key,
    )

    # WHEN
    user = verifier.verify(token)

    # THEN
    assert user.subject == "alice"
    assert user.email == "alice@example.com"
    assert user.name == "Alice Liddell"
