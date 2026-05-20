"""SQLAlchemy ORM models.

Models live ONLY in this package. They are mapped to domain entities by
repositories and never exposed outward.

EVERY model module must be imported here so that ``Base.metadata`` knows
about it when Alembic autogenerates a migration. Without this,
``alembic revision --autogenerate`` would think the missing model means
"the table should be dropped" — producing a destructive migration. Add
new models below as the project grows.
"""

from {{ cookiecutter.package_name }}.infrastructure.persistence.models import (  # noqa: F401
    idempotency_record as _idempotency_record,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.models import (  # noqa: F401
    outbox_event as _outbox_event,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.models import (  # noqa: F401
    user as _user,
)
from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base

__all__ = ["Base"]
