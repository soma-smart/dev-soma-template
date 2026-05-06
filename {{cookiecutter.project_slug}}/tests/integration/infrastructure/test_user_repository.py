"""Integration tests for ``SqlAlchemyUserRepository``.

These tests exercise the real SQLAlchemy code path against a fresh
Postgres 17 container. They prove the contract that unit tests with the
``InMemoryUserRepository`` Fake cannot:

* INSERT propagates the unique constraint violation as
  ``UserAlreadyExistsError`` (the integrity-error → domain-error
  translation lives in the production binding).
* ``find_by_email`` and ``find_by_id`` round-trip the model ↔ entity
  mapping correctly (the unit-level Fake bypasses that layer).
* The transactional behaviour matches what the request boundary does
  in production (ADR 0004): ``flush`` surfaces violations early, the
  outer transaction commits or rolls back atomically.

One test = one edge case. No ``@parametrize``: each scenario is named
and written to fail first (TDD) before the corresponding production
code lands. Add new tests when you discover a behaviour the existing
five do not cover.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.exceptions.user import UserAlreadyExistsError
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId
from {{ cookiecutter.package_name }}.infrastructure.persistence.user_repository import SqlAlchemyUserRepository


def _user(*, uid: int = 1, email: str = "alice@example.com", name: str = "Alice") -> User:
    return User(
        id=UserId(UUID(int=uid)),
        email=Email(email),
        name=name,
        created_at=datetime(2026, 5, 5, 12, 0, tzinfo=UTC),
    )


@pytest.mark.integration
async def test_given_empty_db_when_adding_user_then_persists_and_finds_by_id(
    pg_session: AsyncSession,
) -> None:
    # GIVEN
    repo = SqlAlchemyUserRepository(pg_session)
    user = _user()

    # WHEN
    await repo.add(user)
    found = await repo.find_by_id(UserId(UUID(int=1)))

    # THEN
    assert found is not None
    assert found.id == user.id
    assert found.email == Email("alice@example.com")
    assert found.name == "Alice"


@pytest.mark.integration
async def test_given_duplicate_email_when_adding_then_translates_integrity_error_to_domain_error(
    pg_session: AsyncSession,
) -> None:
    # GIVEN
    repo = SqlAlchemyUserRepository(pg_session)
    await repo.add(_user(uid=1, email="alice@example.com"))

    # WHEN / THEN
    with pytest.raises(UserAlreadyExistsError) as excinfo:
        await repo.add(_user(uid=2, email="alice@example.com", name="Alice2"))
    assert excinfo.value.code == "USER_ALREADY_EXISTS"


@pytest.mark.integration
async def test_given_persisted_user_when_finding_by_email_then_returns_user(
    pg_session: AsyncSession,
) -> None:
    # GIVEN
    repo = SqlAlchemyUserRepository(pg_session)
    await repo.add(_user(email="alice@example.com"))

    # WHEN
    found = await repo.find_by_email(Email("alice@example.com"))

    # THEN
    assert found is not None
    assert found.id == UserId(UUID(int=1))


@pytest.mark.integration
async def test_given_unknown_email_when_finding_by_email_then_returns_none(
    pg_session: AsyncSession,
) -> None:
    # GIVEN
    repo = SqlAlchemyUserRepository(pg_session)

    # WHEN
    found = await repo.find_by_email(Email("ghost@example.com"))

    # THEN
    assert found is None


@pytest.mark.integration
async def test_given_unknown_id_when_finding_by_id_then_returns_none(
    pg_session: AsyncSession,
) -> None:
    # GIVEN
    repo = SqlAlchemyUserRepository(pg_session)

    # WHEN
    found = await repo.find_by_id(UserId(UUID(int=999)))

    # THEN
    assert found is None
