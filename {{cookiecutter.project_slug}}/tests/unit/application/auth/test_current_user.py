"""Unit tests for the ``CurrentUser`` value object."""

from __future__ import annotations

import pytest

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser


@pytest.mark.unit
def test_given_user_with_admin_role_when_has_role_admin_then_returns_true() -> None:
    # GIVEN
    user = CurrentUser(subject="abc", roles=("admin", "viewer"))

    # WHEN
    result = user.has_role("admin")

    # THEN
    assert result is True


@pytest.mark.unit
def test_given_user_without_role_when_has_role_then_returns_false() -> None:
    # GIVEN
    user = CurrentUser(subject="abc", roles=("viewer",))

    # WHEN
    result = user.has_role("admin")

    # THEN
    assert result is False


@pytest.mark.unit
def test_given_user_with_one_of_required_roles_when_has_any_role_then_returns_true() -> None:
    # GIVEN
    user = CurrentUser(subject="abc", roles=("viewer",))

    # WHEN
    result = user.has_any_role("admin", "viewer")

    # THEN
    assert result is True


@pytest.mark.unit
def test_given_user_with_none_of_required_roles_when_has_any_role_then_returns_false() -> None:
    # GIVEN
    user = CurrentUser(subject="abc", roles=("guest",))

    # WHEN
    result = user.has_any_role("admin", "viewer")

    # THEN
    assert result is False
