"""E2E tests for ``GET /v1/users/me`` (SSO auto-provisioning entry point)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fakes.auth import FakeTokenVerifier
from tests.fakes.repositories.user import InMemoryUserRepository


@pytest.mark.e2e
def test_given_valid_jwt_when_getting_me_then_returns_200_with_user(
    client: TestClient,
    token_verifier: FakeTokenVerifier,
    user_repository: InMemoryUserRepository,
) -> None:
    # GIVEN
    token_verifier.accept(
        "good-token",
        subject="azure-sub-alice",
        email="alice@example.com",
        name="Alice",
    )

    # WHEN
    response = client.get("/v1/users/me", headers={"Authorization": "Bearer good-token"})

    # THEN
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "azure-sub-alice"
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Alice"
    # auto-provisioning persisted the user on first call
    assert len(user_repository.users) == 1


@pytest.mark.e2e
def test_given_no_authorization_header_when_getting_me_then_returns_401(
    client: TestClient,
) -> None:
    # WHEN
    response = client.get("/v1/users/me")

    # THEN
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.e2e
def test_given_jwt_missing_email_claim_when_getting_me_then_returns_401(
    client: TestClient,
    token_verifier: FakeTokenVerifier,
) -> None:
    # GIVEN
    token_verifier.accept(
        "incomplete-token",
        subject="azure-sub-noprofile",
        email=None,
        name="Whoever",
    )

    # WHEN
    response = client.get(
        "/v1/users/me", headers={"Authorization": "Bearer incomplete-token"}
    )

    # THEN
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_MISSING_PROFILE_CLAIMS"


@pytest.mark.e2e
def test_given_same_jwt_when_calling_me_twice_then_user_is_provisioned_only_once(
    client: TestClient,
    token_verifier: FakeTokenVerifier,
    user_repository: InMemoryUserRepository,
) -> None:
    # GIVEN
    token_verifier.accept(
        "good-token",
        subject="azure-sub-idem",
        email="alice@example.com",
        name="Alice",
    )

    # WHEN
    client.get("/v1/users/me", headers={"Authorization": "Bearer good-token"})
    client.get("/v1/users/me", headers={"Authorization": "Bearer good-token"})

    # THEN
    assert len(user_repository.users) == 1
