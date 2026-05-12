"""E2E tests for ``GET /v1/auth/whoami`` — the canonical protected route."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fakes.auth import FakeTokenVerifier


@pytest.mark.e2e
def test_given_valid_bearer_token_when_calling_whoami_then_returns_identity(
    client: TestClient,
    token_verifier: FakeTokenVerifier,
) -> None:
    # GIVEN
    token_verifier.accept("good-token", subject="alice", email="alice@example.com", roles=("admin",))

    # WHEN
    response = client.get("/v1/auth/whoami", headers={"Authorization": "Bearer good-token"})

    # THEN
    assert response.status_code == 200
    assert response.json() == {
        "subject": "alice",
        "email": "alice@example.com",
        "roles": ["admin"],
    }


@pytest.mark.e2e
def test_given_no_authorization_header_when_calling_whoami_then_returns_401(
    client: TestClient,
) -> None:
    # GIVEN: no header set

    # WHEN
    response = client.get("/v1/auth/whoami")

    # THEN
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.e2e
def test_given_unknown_token_when_calling_whoami_then_returns_401(
    client: TestClient,
) -> None:
    # GIVEN: token_verifier has no registered tokens

    # WHEN
    response = client.get("/v1/auth/whoami", headers={"Authorization": "Bearer unknown"})

    # THEN
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_TOKEN"


@pytest.mark.e2e
def test_given_non_bearer_scheme_when_calling_whoami_then_returns_401(
    client: TestClient,
) -> None:
    # GIVEN: non-Bearer scheme

    # WHEN
    response = client.get("/v1/auth/whoami", headers={"Authorization": "Basic abc"})

    # THEN
    assert response.status_code == 401
