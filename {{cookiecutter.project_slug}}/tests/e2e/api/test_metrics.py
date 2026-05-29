"""E2E test for the Prometheus /metrics endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_given_running_app_when_calling_metrics_then_content_type_is_text_plain(
    client: AsyncClient,
) -> None:
    # WHEN
    response = await client.get("/metrics")

    # THEN
    assert "text/plain" in response.headers.get("content-type", "")


@pytest.mark.e2e
async def test_given_running_app_when_calling_metrics_then_body_includes_process_metrics(
    client: AsyncClient,
) -> None:
    # WHEN
    response = await client.get("/metrics")

    # THEN: prometheus_client ships process_cpu_seconds_total unconditionally
    assert "process_cpu_seconds_total" in response.text


@pytest.mark.e2e
async def test_given_a_served_request_when_calling_metrics_then_body_includes_http_metrics(
    client: AsyncClient,
) -> None:
    # GIVEN: trigger a request to populate at least one HTTP metric series
    await client.get("/health/live")

    # WHEN
    text = (await client.get("/metrics")).text

    # THEN
    assert "http_request_duration_seconds" in text or "http_requests_total" in text
