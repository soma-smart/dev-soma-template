"""init idempotency

Revision ID: 0004_init_idempotency
Revises: 0003_outbox_retry_columns
Create Date: 2026-05-12

Creates ``idempotency_records`` backing the IdempotencyMiddleware. Each row
captures the state of one client-supplied ``Idempotency-Key`` so retries
return the original response instead of re-running the handler.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_init_idempotency"
down_revision: str | None = "0003_outbox_retry_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``idempotency_records`` table + cleanup index."""
    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.JSON(), nullable=True),
        sa.Column("response_headers", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    # Lazy cleanup at lookup time: indexed for the WHERE expires_at < now() pass.
    op.create_index("ix_idempotency_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    """Drop the ``idempotency_records`` table and its index."""
    op.drop_index("ix_idempotency_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
