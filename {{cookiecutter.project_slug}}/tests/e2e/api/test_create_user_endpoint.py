"""E2E tests for ``POST /v1/users``.

Thin by design: 1 happy path + 1 critical error per endpoint. The 4 unit-level
branches of the use case stay covered by
``tests/unit/application/test_create_user_use_case.py``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.fakes.repositories.user import InMemoryUserRepository


@pytest.mark.e2e
def test_given_valid_payload_when_posting_to_users_then_returns_201(
    client: TestClient,
    user_repository: InMemoryUserRepository,
) -> None:
    # WHEN
    response = client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice"})

    # THEN
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Alice"
    assert len(user_repository.users) == 1


@pytest.mark.e2e
def test_given_existing_email_when_posting_to_users_then_returns_409(
    client: TestClient,
) -> None:
    # GIVEN
    client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice"})

    # WHEN
    response = client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice2"})

    # THEN
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_ALREADY_EXISTS"
