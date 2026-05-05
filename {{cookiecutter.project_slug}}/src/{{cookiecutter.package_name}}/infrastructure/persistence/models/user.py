"""SQLAlchemy ORM model for ``User``."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base


class UserModel(Base):
    """``users`` table mapping. Never exposed outside ``infrastructure/persistence/``."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
