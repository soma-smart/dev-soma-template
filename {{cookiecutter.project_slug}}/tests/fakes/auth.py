"""Fake ``TokenVerifier`` for unit and e2e tests.

The verifier maintains an in-memory map ``token -> CurrentUser``. Tests
register a token via :meth:`accept` and pass that token as the bearer.
Any other token raises ``InvalidTokenError``. The empty string is treated
as absent — use the no-header path for that.
"""

from __future__ import annotations

from {{ cookiecutter.package_name }}.application.auth.current_user import CurrentUser
from {{ cookiecutter.package_name }}.domain.exceptions.auth import InvalidTokenError


class FakeTokenVerifier:
    """In-memory ``TokenVerifier`` for tests. Doubles as a Spy via ``.calls``."""

    def __init__(self) -> None:
        self._users: dict[str, CurrentUser] = {}
        self.calls: list[str] = []

    def accept(
        self,
        token: str,
        *,
        subject: str = "test-subject",
        email: str | None = "test@example.com",
        name: str | None = "Test User",
        roles: tuple[str, ...] = (),
    ) -> CurrentUser:
        """Register ``token`` to resolve to a synthetic ``CurrentUser``.

        Returns the resolved ``CurrentUser`` so the test can refer to it for
        assertions without re-instantiating.
        """
        user = CurrentUser(subject=subject, email=email, name=name, roles=roles)
        self._users[token] = user
        return user

    def verify(self, token: str) -> CurrentUser:
        """Look up ``token``; raise ``InvalidTokenError`` if not registered."""
        self.calls.append(token)
        try:
            return self._users[token]
        except KeyError as exc:
            raise InvalidTokenError(reason="unknown_token") from exc
