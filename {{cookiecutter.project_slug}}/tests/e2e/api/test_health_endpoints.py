"""E2E tests for the three K8s health probes."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.presentation.api.dependencies.common import get_session
from tests.e2e.conftest import StubAsyncSession


@pytest.mark.e2e
def test_given_running_app_when_calling_live_then_returns_200(client: TestClient) -> None:
    # WHEN
    response = client.get("/health/live")

    # THEN
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.e2e
def test_given_db_reachable_when_calling_ready_then_returns_200(client: TestClient) -> None:
    # WHEN
    response = client.get("/health/ready")

    # THEN
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.e2e
def test_given_db_unreachable_when_calling_ready_then_returns_503(app: FastAPI, client: TestClient) -> None:
    # GIVEN
    failing = StubAsyncSession(raises=OperationalError("db down", params=None, orig=None))

    async def failing_session() -> AsyncIterator[AsyncSession]:
        yield failing  # type: ignore[misc]

    app.dependency_overrides[get_session] = failing_session

    # WHEN
    response = client.get("/health/ready")

    # THEN
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "reason": "database_unreachable"}


@pytest.mark.e2e
def test_given_db_reachable_when_calling_startup_then_returns_200(client: TestClient) -> None:
    # WHEN
    response = client.get("/health/startup")

    # THEN
    assert response.status_code == 200
    assert response.json() == {"status": "started"}
