"""init outbox

Revision ID: 0002_init_outbox
Revises: 0001_init_users
Create Date: 2026-05-06

Creates the outbox_events table backing ``SqlOutboxEventBus``. The relay
worker (``infrastructure/jobs/outbox_relay.py``) consumes rows where
``published_at IS NULL`` and forwards them to the configured broker.

Drop this revision (and the OutboxEventModel) on projects that publish
events through a different mechanism — see ADR 0005.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_init_outbox"
down_revision: str | None = "0001_init_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``outbox_events`` table with indexes used by the relay."""
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_name", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_event_name", "outbox_events", ["event_name"])
    op.create_index("ix_outbox_created_at", "outbox_events", ["created_at"])
    op.create_index("ix_outbox_published_at", "outbox_events", ["published_at"])


def downgrade() -> None:
    """Drop the ``outbox_events`` table and its indexes."""
    op.drop_index("ix_outbox_published_at", table_name="outbox_events")
    op.drop_index("ix_outbox_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_event_name", table_name="outbox_events")
    op.drop_table("outbox_events")
