"""Immutable identity of the caller of an HTTP request."""

from __future__ import annotations

from dataclasses import dataclass, field

from {{ cookiecutter.package_name }}.domain.value_objects.base import ValueObject


@dataclass(frozen=True, slots=True)
class CurrentUser(ValueObject):
    """The caller's identity as resolved from the bearer token.

    ``subject`` is the IdP-issued stable identifier (``sub`` claim). It is
    NOT necessarily the ``UserId`` of the ``User`` entity — projects map
    one to the other in the application layer if they need to.

    ``roles`` are the names of authz roles attached to the token (typically
    ``realm_access.roles`` for Keycloak, ``"https://<ns>/roles"`` for Auth0).
    The path is configurable in ``infrastructure/auth/jwt_verifier.py``.

    ``email`` is best-effort: not every IdP issues an email claim, so it is
    optional and never relied upon for identity decisions. Use ``subject``
    for that.

    Attributes:
        subject: stable opaque identifier from the IdP (``sub`` claim).
        email: optional email associated with the principal.
        roles: authz roles attached to the principal.
        claims: full raw claims dict — for projects that need access to
            non-standard IdP claims without altering this VO.
    """

    subject: str
    email: str | None = None
    roles: tuple[str, ...] = ()
    claims: dict[str, object] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Return whether the principal has the given role."""
        return role in self.roles

    def has_any_role(self, *roles: str) -> bool:
        """Return whether the principal has at least one of the given roles."""
        return any(role in self.roles for role in roles)
