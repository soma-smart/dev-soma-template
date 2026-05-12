"""outbox retry + dead-letter columns

Revision ID: 0003_outbox_retry_columns
Revises: 0002_init_outbox
Create Date: 2026-05-12

Adds the retry / backoff / dead-letter state to ``outbox_events`` so the
relay can:

* defer a re-attempt after a handler failure (``next_attempt_at``)
* park rows that fail repeatedly under ``status='poisoned'`` so they
  stop blocking the queue and start firing alerts.

NOT NULL columns receive a ``server_default`` because the table may
contain rows already — see ``database-and-migrations``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_outbox_retry_columns"
down_revision: str | None = "0002_init_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add retry-state columns and the polling index."""
    op.add_column(
        "outbox_events",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "outbox_events",
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
    )
    # Backfill: any row already published before this migration ran is
    # transitioned to status='published' so the new polling query does
    # not pick it up.
    op.execute(
        "UPDATE outbox_events SET status = 'published' WHERE published_at IS NOT NULL"
    )
    # Polling index — matches the WHERE clause of _select_due_rows.
    op.create_index(
        "ix_outbox_status_next_attempt",
        "outbox_events",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    """Drop the retry-state columns and the polling index."""
    op.drop_index("ix_outbox_status_next_attempt", table_name="outbox_events")
    op.drop_column("outbox_events", "status")
    op.drop_column("outbox_events", "last_error")
    op.drop_column("outbox_events", "next_attempt_at")
    op.drop_column("outbox_events", "last_attempt_at")
    op.drop_column("outbox_events", "attempts")
