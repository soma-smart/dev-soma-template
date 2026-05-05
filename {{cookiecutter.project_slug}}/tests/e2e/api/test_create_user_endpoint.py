"""E2E tests for ``POST /v1/users``.

E2E tests are intentionally thin: 1 happy path + 1 critical error per endpoint.
The 4 unit-level branches of the use case stay covered by
``tests/unit/application/test_create_user_use_case.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from {{ cookiecutter.package_name }}.application.use_cases.create_user import CreateUserUseCase
from {{ cookiecutter.package_name }}.presentation.api.app import create_app
from {{ cookiecutter.package_name }}.presentation.api.dependencies.users import get_create_user_use_case
from tests.fakes.clock import FrozenClock
from tests.fakes.id_generator import SequentialIdGenerator
from tests.fakes.repositories.user import InMemoryUserRepository


def _build_client_with_fakes(repo: InMemoryUserRepository) -> TestClient:
    app = create_app()
    use_case = CreateUserUseCase(
        users=repo,
        clock=FrozenClock(at=datetime(2026, 5, 5, tzinfo=UTC)),
        ids=SequentialIdGenerator(),
    )
    app.dependency_overrides[get_create_user_use_case] = lambda: use_case
    return TestClient(app)


@pytest.mark.e2e
def test_given_valid_payload_when_posting_to_users_then_returns_201() -> None:
    # GIVEN
    repo = InMemoryUserRepository()
    client = _build_client_with_fakes(repo)

    # WHEN
    response = client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice"})

    # THEN
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert body["name"] == "Alice"
    assert len(repo.users) == 1


@pytest.mark.e2e
def test_given_existing_email_when_posting_to_users_then_returns_409() -> None:
    # GIVEN
    repo = InMemoryUserRepository()
    client = _build_client_with_fakes(repo)
    client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice"})

    # WHEN
    response = client.post("/v1/users", json={"email": "alice@example.com", "name": "Alice2"})

    # THEN
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_ALREADY_EXISTS"
