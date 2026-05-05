"""Smoke test that ships with the generated project.

Phase B will replace this with the real /health implementation tests and add
GIVEN/WHEN/THEN compliance through scripts/checks/test_naming.py.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from {{ cookiecutter.package_name }}.presentation.api.app import app


@pytest.mark.unit
def test_given_running_app_when_calling_health_then_returns_ok() -> None:
    # GIVEN
    client = TestClient(app)

    # WHEN
    response = client.get("/health")

    # THEN
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
