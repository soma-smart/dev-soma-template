"""Unit tests for the auth dependencies — bearer parsing, verification, roles."""

from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.domain.exceptions.auth import (
    InsufficientPermissionsError,
    InvalidTokenError,
    MissingTokenError,
)
from {{ cookiecutter.package_name }}.presentation.api.dependencies.auth import (
    get_bearer_token,
    get_current_user,
    get_current_user_optional,
    require_roles,
)

from tests.fakes.auth import FakeTokenVerifier


def _request_with(headers: dict[str, str]) -> Request:
    """Build a starlette ``Request`` with the given headers."""
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


@pytest.mark.unit
def test_given_valid_bearer_credentials_when_extracting_token_then_returns_token() -> None:
    # GIVEN
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="abc.def.ghi")

    # WHEN
    token = get_bearer_token(credentials)

    # THEN
    assert token == "abc.def.ghi"


@pytest.mark.unit
def test_given_no_credentials_when_extracting_token_then_raises_missing_token() -> None:
    # GIVEN: no Authorization header was provided

    # WHEN / THEN
    with pytest.raises(MissingTokenError):
        get_bearer_token(None)


@pytest.mark.unit
def test_given_non_bearer_scheme_when_extracting_token_then_raises_missing_token() -> None:
    # GIVEN
    credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="dXNlcjpwYXNz")

    # WHEN / THEN
    with pytest.raises(MissingTokenError):
        get_bearer_token(credentials)


@pytest.mark.unit
def test_given_known_token_when_resolving_current_user_then_returns_user(
    token_verifier: FakeTokenVerifier,
) -> None:
    # GIVEN
    expected = token_verifier.accept("good-token", subject="alice", roles=("admin",))

    # WHEN
    resolved = get_current_user(token="good-token", verifier=token_verifier)

    # THEN
    assert resolved == expected


@pytest.mark.unit
def test_given_unknown_token_when_resolving_current_user_then_raises_invalid_token(
    token_verifier: FakeTokenVerifier,
) -> None:
    # GIVEN: no tokens registered

    # WHEN / THEN
    with pytest.raises(InvalidTokenError):
        get_current_user(token="bad-token", verifier=token_verifier)


@pytest.mark.unit
def test_given_no_header_when_resolving_optional_then_returns_none(
    token_verifier: FakeTokenVerifier,
) -> None:
    # GIVEN
    request = _request_with({})

    # WHEN
    user = get_current_user_optional(request=request, verifier=token_verifier)

    # THEN
    assert user is None


@pytest.mark.unit
def test_given_user_with_required_role_when_require_roles_then_returns_user() -> None:
    # GIVEN
    user = CurrentUser(subject="alice", roles=("admin",))
    dep = require_roles("admin")

    # WHEN
    resolved = dep(user=user)

    # THEN
    assert resolved is user


@pytest.mark.unit
def test_given_user_without_required_role_when_require_roles_then_raises_insufficient_permissions() -> None:
    # GIVEN
    user = CurrentUser(subject="bob", roles=("viewer",))
    dep = require_roles("admin")

    # WHEN / THEN
    with pytest.raises(InsufficientPermissionsError):
        dep(user=user)
