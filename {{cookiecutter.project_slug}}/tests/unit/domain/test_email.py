"""Unit tests for the ``Email`` value object."""

from __future__ import annotations

import pytest

from {{ cookiecutter.package_name }}.domain.value_objects.email import Email, InvalidEmailError


@pytest.mark.unit
def test_given_valid_address_when_constructing_email_then_normalises_to_lowercase() -> None:
    # GIVEN
    raw = "Alice@Example.COM"

    # WHEN
    email = Email(raw)

    # THEN
    assert email.value == "alice@example.com"
    assert str(email) == "alice@example.com"


@pytest.mark.unit
def test_given_two_emails_with_different_case_when_comparing_then_are_equal() -> None:
    # GIVEN
    a = Email("foo@bar.com")
    b = Email("FOO@BAR.COM")

    # WHEN / THEN
    assert a == b


@pytest.mark.unit
def test_given_string_without_at_sign_when_constructing_email_then_raises_invalid_email() -> None:
    # GIVEN
    raw = "not-an-email"

    # WHEN / THEN
    with pytest.raises(InvalidEmailError):
        Email(raw)


@pytest.mark.unit
def test_given_string_without_tld_when_constructing_email_then_raises_invalid_email() -> None:
    # GIVEN
    raw = "alice@localhost"

    # WHEN / THEN
    with pytest.raises(InvalidEmailError):
        Email(raw)
