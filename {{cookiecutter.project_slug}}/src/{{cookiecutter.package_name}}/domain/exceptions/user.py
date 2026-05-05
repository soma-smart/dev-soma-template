"""User-related domain exceptions."""

from __future__ import annotations

from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError


class UserAlreadyExistsError(DomainError):
    """Raised when attempting to create a user with an email already in use."""

    code = "USER_ALREADY_EXISTS"
    message = "An account with this email already exists."


class UserNotFoundError(DomainError):
    """Raised when looking up a user that does not exist."""

    code = "USER_NOT_FOUND"
    message = "No user found for the given identifier."
