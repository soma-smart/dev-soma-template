"""Mint a short-lived HS256 JWT for local dev calls.

Invoked via ``just dev-token <subject> [roles]``. NEVER usable in prod —
relies on ``AUTH_JWT_ALGORITHM=HS256`` and the local ``AUTH_JWT_SECRET``.
Prints a token good for one hour. The ``roles`` argument is a comma-
separated list and lands under the claim path configured by
``AUTH_JWT_ROLES_CLAIM`` (default ``roles``).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from {{ cookiecutter.package_name }}.infrastructure.config.settings import get_settings


def _set_nested(claims: dict[str, Any], path: str, value: Any) -> None:
    """Set ``claims[a][b][c] = value`` given dotted ``path = 'a.b.c'``."""
    cursor: dict[str, Any] = claims
    parts = path.split(".")
    for segment in parts[:-1]:
        cursor = cursor.setdefault(segment, {})
    cursor[parts[-1]] = value


def main(argv: list[str]) -> int:
    """Print a freshly signed HS256 token for ``argv = [subject, roles_csv?]``."""
    if not argv:
        print("usage: dev-token <subject> [roles_csv]", file=sys.stderr)
        return 2
    subject = argv[0]
    roles_csv = argv[1] if len(argv) > 1 else ""
    roles = [r.strip() for r in roles_csv.split(",") if r.strip()]

    settings = get_settings()
    if settings.auth_jwt_algorithm != "HS256":
        print(f"dev-token only supports HS256; AUTH_JWT_ALGORITHM={settings.auth_jwt_algorithm}", file=sys.stderr)
        return 2
    if settings.auth_jwt_secret is None:
        print("AUTH_JWT_SECRET is not set; populate it in .env first", file=sys.stderr)
        return 2

    now = datetime.now(tz=UTC)
    claims: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    if settings.auth_jwt_audience:
        claims["aud"] = settings.auth_jwt_audience
    if settings.auth_jwt_issuer:
        claims["iss"] = settings.auth_jwt_issuer
    if roles:
        _set_nested(claims, settings.auth_jwt_roles_claim, roles)

    token = jwt.encode(claims, settings.auth_jwt_secret.get_secret_value(), algorithm="HS256")
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
