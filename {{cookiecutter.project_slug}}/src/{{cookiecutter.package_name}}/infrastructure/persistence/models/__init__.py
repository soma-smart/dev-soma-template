"""SQLAlchemy ORM models.

Models live ONLY in this package. They are mapped to domain entities by
repositories and never exposed outward.
"""

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base

__all__ = ["Base"]
