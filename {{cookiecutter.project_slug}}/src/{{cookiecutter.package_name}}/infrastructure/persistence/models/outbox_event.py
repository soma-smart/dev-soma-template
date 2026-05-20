"""SQLAlchemy ORM model for the outbox table."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base

OutboxStatus = Literal["pending", "published", "poisoned"]


class OutboxEventModel(Base):
    """``outbox_events`` — domain events queued for asynchronous publication.

    Rows are inserted by the use case in the same transaction as the entity
    write (see ADR 0005). A separate relay process polls
    ``status='pending' AND next_attempt_at <= now()`` and dispatches rows
    through the in-process handler registry (see
    :mod:`{{ cookiecutter.package_name }}.infrastructure.jobs.handlers`).

    Lifecycle:

    * inserted with ``status='pending'``, ``attempts=0``, ``next_attempt_at=NULL``
    * on dispatch success → ``status='published'``, ``published_at=now()``
    * on dispatch failure → ``attempts++``, ``last_attempt_at=now()``,
      ``next_attempt_at=now()+backoff(attempts)``, ``last_error=<repr>``
    * after MAX_ATTEMPTS failures → ``status='poisoned'`` (no longer polled).
    """

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Retry / dead-letter state — see infrastructure/jobs/backoff.py
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # No standalone ``index=True`` on ``status`` — Postgres can satisfy
    # ``WHERE status = 'pending'`` from the composite index below (status is
    # the leading column). Avoids autogenerate drift between a single-column
    # ``ix_outbox_events_status`` and the composite.
    status: Mapped[OutboxStatus] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    # Composite index matching the relay's polling ``WHERE`` clause:
    # ``status='pending' AND next_attempt_at <= now()``. Declared explicitly
    # so ``alembic revision --autogenerate`` reports no drift against the
    # 0003 migration that originally created it.
    __table_args__ = (
        Index(
            "ix_outbox_events_status_next_attempt",
            "status",
            "next_attempt_at",
        ),
    )
