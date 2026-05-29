"""E2E tests for ``GET /v1/users/me`` (SSO auto-provisioning entry point).

Exercises the production wiring end-to-end: real JWT verification
(HS256 against the e2e secret), real ``SqlAlchemyUserRepository`` and
``SqlOutboxEventBus`` against testcontainers Postgres, real outbox
inserts inside the request transaction.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.user import UserModel


@pytest.mark.e2e
async def test_given_valid_jwt_when_getting_me_then_returns_200(
    client: AsyncClient,
    mint_token: Callable[..., str],
) -> None:
    # GIVEN
    token = mint_token("azure-sub-alice", email="alice@example.com", name="Alice")

    # WHEN
    response = await client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    # THEN
    assert response.status_code == 200


@pytest.mark.e2e
async def test_given_valid_jwt_when_getting_me_then_body_carries_provisioned_identity(
    client: AsyncClient,
    mint_token: Callable[..., str],
) -> None:
    # GIVEN
    token = mint_token("azure-sub-alice", email="alice@example.com", name="Alice")

    # WHEN
    response = await client.get(
        "/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    body = response.json()

    # THEN
    assert {k: body[k] for k in ("subject", "email", "name")} == {
        "subject": "azure-sub-alice",
        "email": "alice@example.com",
        "name": "Alice",
    }


@pytest.mark.e2e
async def test_given_first_call_for_subject_when_getting_me_then_user_row_is_inserted(
    client: AsyncClient,
    mint_token: Callable[..., str],
    e2e_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # GIVEN
    token = mint_token("azure-sub-alice", email="alice@example.com", name="Alice")

    # WHEN
    await client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    # THEN
    async with e2e_session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(UserModel).where(UserModel.subject == "azure-sub-alice")
        )
    assert count == 1


@pytest.mark.e2e
async def test_given_no_authorization_header_when_getting_me_then_returns_401(
    client: AsyncClient,
) -> None:
    # WHEN
    response = await client.get("/v1/users/me")

    # THEN
    assert response.status_code == 401


@pytest.mark.e2e
async def test_given_no_authorization_header_when_getting_me_then_error_code_is_missing_token(
    client: AsyncClient,
) -> None:
    # WHEN
    body = (await client.get("/v1/users/me")).json()

    # THEN
    assert body["error"]["code"] == "AUTH_MISSING_TOKEN"


@pytest.mark.e2e
async def test_given_jwt_missing_email_claim_when_getting_me_then_returns_401(
    client: AsyncClient,
    mint_token: Callable[..., str],
) -> None:
    # GIVEN
    token = mint_token("azure-sub-noprofile", email=None, name="Whoever")

    # WHEN
    response = await client.get(
        "/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    # THEN
    assert response.status_code == 401


@pytest.mark.e2e
async def test_given_jwt_missing_email_claim_when_getting_me_then_error_code_is_missing_profile_claims(
    client: AsyncClient,
    mint_token: Callable[..., str],
) -> None:
    # GIVEN
    token = mint_token("azure-sub-noprofile", email=None, name="Whoever")

    # WHEN
    body = (await client.get(
        "/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )).json()

    # THEN
    assert body["error"]["code"] == "AUTH_MISSING_PROFILE_CLAIMS"


@pytest.mark.e2e
async def test_given_same_jwt_when_calling_me_twice_then_user_is_provisioned_only_once(
    client: AsyncClient,
    mint_token: Callable[..., str],
    e2e_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # GIVEN
    token = mint_token("azure-sub-idem", email="alice@example.com", name="Alice")

    # WHEN
    await client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    await client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    # THEN
    async with e2e_session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(UserModel).where(UserModel.subject == "azure-sub-idem")
        )
    assert count == 1
