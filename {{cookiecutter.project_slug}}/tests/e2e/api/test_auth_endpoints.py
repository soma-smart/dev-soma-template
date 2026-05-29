"""E2E tests for ``GET /v1/auth/whoami`` — the canonical protected route."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
async def test_given_valid_bearer_token_when_calling_whoami_then_returns_identity(
    client: AsyncClient,
    mint_token: Callable[..., str],
) -> None:
    # GIVEN
    token = mint_token("alice", email="alice@example.com", roles=("admin",))

    # WHEN
    response = await client.get(
        "/v1/auth/whoami", headers={"Authorization": f"Bearer {token}"}
    )

    # THEN
    assert (response.status_code, response.json()) == (
        200,
        {"subject": "alice", "email": "alice@example.com", "roles": ["admin"]},
    )


@pytest.mark.e2e
async def test_given_no_authorization_header_when_calling_whoami_then_returns_401(
    client: AsyncClient,
) -> None:
    # GIVEN: no header set

    # WHEN
    response = await client.get("/v1/auth/whoami")

    # THEN
    assert (response.status_code, response.json()["error"]["code"]) == (
        401,
        "AUTH_MISSING_TOKEN",
    )


@pytest.mark.e2e
async def test_given_unsigned_token_when_calling_whoami_then_returns_401(
    client: AsyncClient,
) -> None:
    # GIVEN: bearer that wasn't signed with the e2e secret

    # WHEN
    response = await client.get(
        "/v1/auth/whoami", headers={"Authorization": "Bearer unknown"}
    )

    # THEN
    assert (response.status_code, response.json()["error"]["code"]) == (
        401,
        "AUTH_INVALID_TOKEN",
    )


@pytest.mark.e2e
async def test_given_non_bearer_scheme_when_calling_whoami_then_returns_401(
    client: AsyncClient,
) -> None:
    # GIVEN: non-Bearer scheme

    # WHEN
    response = await client.get(
        "/v1/auth/whoami", headers={"Authorization": "Basic abc"}
    )

    # THEN
    assert response.status_code == 401
