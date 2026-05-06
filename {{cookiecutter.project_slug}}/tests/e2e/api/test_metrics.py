"""E2E test for the Prometheus /metrics endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
def test_given_running_app_when_calling_metrics_then_returns_prometheus_format(
    client: TestClient,
) -> None:
    # GIVEN: trigger a request to populate at least one HTTP metric series
    client.get("/health/live")

    # WHEN
    response = client.get("/metrics")

    # THEN
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    # Process metrics shipped by prometheus_client are always present.
    assert "process_cpu_seconds_total" in body
    # The instrumentator emits HTTP request metrics.
    assert "http_request_duration_seconds" in body or "http_requests_total" in body
