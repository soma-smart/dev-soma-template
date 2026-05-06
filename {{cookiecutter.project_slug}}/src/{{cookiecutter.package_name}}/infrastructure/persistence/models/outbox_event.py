"""SQLAlchemy ORM model for the outbox table."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base


class OutboxEventModel(Base):
    """``outbox_events`` — domain events queued for asynchronous publication.

    Rows are inserted by the use case in the same transaction as the
    aggregate write (see ADR 0005). A separate relay process polls
    ``published_at IS NULL`` and forwards rows to the configured broker.
    """

    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
