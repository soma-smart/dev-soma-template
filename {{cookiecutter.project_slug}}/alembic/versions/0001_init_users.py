"""init users

Revision ID: 0001_init_users
Revises:
Create Date: 2026-05-06

The first revision shipped with the template. It creates the ``users``
table backing the SSO auto-provisioning flow (``EnsureUserExistsUseCase``).
Each user is keyed by an internal UUID ``id`` and tracked by the IdP's
``subject`` claim (unique). ``email`` is also unique to prevent two SSO
users sharing the same address. A project that drops the user feature
should also drop this revision (and the ``UserModel``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init_users"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``users`` table with unique-indexed subject and email."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Both ``subject`` and ``email`` are declared ``unique=True, index=True``
    # on ``UserModel``, which SQLAlchemy compiles to single unique indexes
    # (no separate constraint). The migration mirrors that so
    # ``alembic revision --autogenerate`` reports no drift.
    op.create_index("ix_users_subject", "users", ["subject"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Drop the ``users`` table and its indexes."""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_subject", table_name="users")
    op.drop_table("users")
