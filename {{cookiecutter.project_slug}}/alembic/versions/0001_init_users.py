"""init users

Revision ID: 0001_init_users
Revises:
Create Date: 2026-05-06

The first revision shipped with the template. It creates the `users` table
backing the reference feature ``CreateUserUseCase``. A project that drops
the user feature should also drop this revision (and the `UserModel`).
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
    """Create the ``users`` table with a unique-indexed email."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # ``UserModel.email`` declares ``unique=True, index=True`` which SQLAlchemy
    # compiles to a single unique index (no separate constraint). The migration
    # mirrors that so ``alembic revision --autogenerate`` reports no drift.
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Drop the ``users`` table and its index."""
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
