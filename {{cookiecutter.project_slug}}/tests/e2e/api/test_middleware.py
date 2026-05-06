"""E2E tests for the HTTP middleware stack.

Covers the user-facing behaviour: header echo for ``X-Request-ID``, 413 on
oversized payload. Access log and timeout are also exercised at runtime
but their side-effects (a structured log line, asyncio cancellation) are
out of scope here — they are validated indirectly by smoke testing the
response and would otherwise need log capture / a slow handler harness.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
def test_given_request_without_request_id_when_completing_then_response_has_generated_id(
    client: TestClient,
) -> None:
    # GIVEN: client without any custom header
    # WHEN
    response = client.get("/health/live")

    # THEN
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    # UUID4 hex form is 32 lowercase hex chars
    assert len(response.headers["X-Request-ID"]) == 32


@pytest.mark.e2e
def test_given_request_with_request_id_when_completing_then_id_is_echoed(
    client: TestClient,
) -> None:
    # GIVEN
    upstream_id = "abc123def456"

    # WHEN
    response = client.get("/health/live", headers={"X-Request-ID": upstream_id})

    # THEN
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == upstream_id


@pytest.mark.e2e
def test_given_oversized_payload_when_posting_then_returns_413(client: TestClient) -> None:
    # GIVEN: request advertises a body two megabytes large (above the 1 MiB default)
    huge_size = 2 * 1024 * 1024

    # WHEN
    response = client.post(
        "/v1/users",
        headers={"Content-Length": str(huge_size), "Content-Type": "application/json"},
        content=b"{}",
    )

    # THEN
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
