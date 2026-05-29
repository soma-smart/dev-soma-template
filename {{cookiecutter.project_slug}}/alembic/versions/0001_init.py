"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-05-29

Initial schema shipped with the template. Creates the three tables backing
the features wired by default:

* ``users`` — SSO auto-provisioned identities (``EnsureUserExistsUseCase``).
  Keyed by an internal UUID ``id``, tracked by the IdP's ``subject`` claim
  (unique). ``email`` is also unique so two SSO users cannot share an address.
* ``outbox_events`` — durable buffer for ``SqlOutboxEventBus``. Each row is
  written inside the request transaction; the relay worker
  (``infrastructure/jobs/outbox_relay.py``) drains it asynchronously and
  uses ``status`` + ``next_attempt_at`` to retry / poison-park failing rows.
* ``idempotency_records`` — per-key state for the IdempotencyMiddleware
  so retries return the original response instead of re-running the handler.

Drop the tables a project does not need (and the matching
``…Model`` / Fakes / use cases) — see the per-table notes below.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``users``, ``outbox_events`` and ``idempotency_records``."""
    # ─── users ──────────────────────────────────────────────────────
    # Index names mirror SQLAlchemy's ``unique=True, index=True`` auto-naming
    # (``ix_<tablename>_<column>``) so ``alembic revision --autogenerate``
    # reports no drift on a freshly baked project.
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_subject", "users", ["subject"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ─── outbox_events ──────────────────────────────────────────────
    # ``attempts`` / ``status`` get server_defaults to match the model
    # invariants; the polling index supports the relay's WHERE on
    # ``status = 'pending' AND next_attempt_at <= now()``.
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_name", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_events_event_name", "outbox_events", ["event_name"])
    op.create_index("ix_outbox_events_created_at", "outbox_events", ["created_at"])
    op.create_index("ix_outbox_events_published_at", "outbox_events", ["published_at"])
    op.create_index(
        "ix_outbox_events_status_next_attempt",
        "outbox_events",
        ["status", "next_attempt_at"],
    )

    # ─── idempotency_records ────────────────────────────────────────
    # Lazy cleanup at lookup time: indexed for the WHERE ``expires_at < now()`` pass.
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
    op.create_index("ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"])


def downgrade() -> None:
    """Drop the three tables and their indexes."""
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")

    op.drop_index("ix_outbox_events_status_next_attempt", table_name="outbox_events")
    op.drop_index("ix_outbox_events_published_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_created_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_event_name", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_subject", table_name="users")
    op.drop_table("users")
