"""SQLAlchemy ORM model for ``idempotency_records``.

Backs the IdempotencyMiddleware. One row per client-supplied
``Idempotency-Key`` value; rows are short-lived (default 24h) and cleaned
up lazily at lookup time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID  # noqa: F401  # kept for symmetry with other models

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base

IdempotencyStatus = Literal["in_progress", "completed"]


class IdempotencyRecord(Base):
    """One persisted reply for a client-supplied ``Idempotency-Key``.

    Lifecycle:

    * inserted with ``status='in_progress'`` when the first request reaches
      the middleware; on PK conflict, retries either return the cached
      reply (``status='completed'``) or 409 (still in flight).
    * after the handler returns successfully, the row is updated to
      ``status='completed'`` with ``response_status / response_body /
      response_headers`` populated. On handler exception the row is left
      in-progress and times out via ``expires_at``.

    The row stores the original ``method`` and ``path`` so a retry that
    targets a different endpoint with the same key returns 422 instead of
    a stale response.
    """

    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[IdempotencyStatus] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    response_headers: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
