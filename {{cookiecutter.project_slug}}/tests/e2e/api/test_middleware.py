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
def test_given_request_without_request_id_when_completing_then_response_has_generated_32_char_id(
    client: TestClient,
) -> None:
    # GIVEN: client without any custom header
    # WHEN
    response = client.get("/health/live")

    # THEN: UUID4 hex form is 32 lowercase hex chars; len == 32 implies presence
    assert len(response.headers.get("X-Request-ID", "")) == 32


@pytest.mark.e2e
def test_given_request_with_request_id_when_completing_then_id_is_echoed(
    client: TestClient,
) -> None:
    # GIVEN
    upstream_id = "abc123def456"

    # WHEN
    response = client.get("/health/live", headers={"X-Request-ID": upstream_id})

    # THEN
    assert response.headers["X-Request-ID"] == upstream_id


@pytest.mark.e2e
def test_given_oversized_payload_when_posting_then_response_is_413_payload_too_large(
    client: TestClient,
) -> None:
    # GIVEN: request advertises a body two megabytes large (above the 1 MiB default)
    huge_size = 2 * 1024 * 1024

    # WHEN
    response = client.post(
        "/v1/users",
        headers={"Content-Length": str(huge_size), "Content-Type": "application/json"},
        content=b"{}",
    )

    # THEN: status + error code describe the same response outcome (§4b tuple equality)
    assert (response.status_code, response.json()["error"]["code"]) == (
        413,
        "PAYLOAD_TOO_LARGE",
    )
