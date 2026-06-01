"""Unit tests for the ``User`` entity."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from {{ cookiecutter.package_name }}.domain.entities.user import User
from {{ cookiecutter.package_name }}.domain.value_objects.email import Email
from {{ cookiecutter.package_name }}.domain.value_objects.user_id import UserId


def _user(
    *,
    uid: int = 1,
    subject: str = "azure-sub-1",
    email: str = "alice@example.com",
    name: str = "Alice",
) -> User:
    return User(
        id=UserId(UUID(int=uid)),
        subject=subject,
        email=Email(email),
        name=name,
        created_at=datetime(2026, 5, 5, tzinfo=UTC),
    )


@pytest.mark.unit
def test_given_two_users_with_same_id_when_comparing_then_are_equal() -> None:
    # GIVEN
    a = _user(uid=42, email="a@b.com", name="Alpha")
    b = _user(uid=42, email="x@y.com", name="Beta")

    # WHEN / THEN
    assert a == b


@pytest.mark.unit
def test_given_two_users_with_same_id_when_hashing_then_hashes_are_equal() -> None:
    # GIVEN
    a = _user(uid=42, email="a@b.com", name="Alpha")
    b = _user(uid=42, email="x@y.com", name="Beta")

    # WHEN / THEN
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_given_two_users_with_different_id_when_comparing_then_are_not_equal() -> None:
    # GIVEN
    a = _user(uid=1)
    b = _user(uid=2)

    # WHEN / THEN
    assert a != b
