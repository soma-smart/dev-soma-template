"""Auth-related domain exceptions.

These live in ``domain/exceptions/`` even though the validation runs in
``presentation/`` because they describe a business outcome (the caller is
not authorized to perform the operation). The HTTP status mapping lives in
``presentation/api/error_handlers.py``.
"""

from __future__ import annotations

from {{ cookiecutter.package_name }}.domain.exceptions.base import DomainError


class MissingTokenError(DomainError):
    """Raised when a protected route is hit without an ``Authorization`` header."""

    code = "AUTH_MISSING_TOKEN"
    default_message = "Authentication is required to access this resource."


class InvalidTokenError(DomainError):
    """Raised when the bearer token cannot be verified.

    Catch-all for the verifier: bad signature, expired token, wrong
    audience / issuer, malformed payload. The cause is logged in ``context``
    but never exposed to the caller (to limit oracle-style leaks).
    """

    code = "AUTH_INVALID_TOKEN"
    default_message = "Authentication credentials are invalid or expired."


class InsufficientPermissionsError(DomainError):
    """Raised when an authenticated caller lacks a required role / scope."""

    code = "AUTH_INSUFFICIENT_PERMISSIONS"
    default_message = "You do not have permission to perform this action."
