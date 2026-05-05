---
name: database-and-migrations
description: Workflow for changing the schema with Alembic in async SQLAlchemy.
when_to_use: New table or column; renaming or dropping; reading or writing models in infrastructure/persistence/.
---

# Database and migrations

Stack: SQLAlchemy 2.0 async + asyncpg + Alembic with async env.

## Where things live

- ORM models: `src/<pkg>/infrastructure/persistence/models/<entity>.py`. Suffix `…Model` (e.g., `UserModel`).
- Repositories: `src/<pkg>/infrastructure/persistence/<entity>_repository.py`. Map `Entity ↔ Model` in private `_to_entity` / `_to_model` static methods.
- Migrations: `alembic/versions/`.

**Models never leave `infrastructure/persistence/`.** Repositories return domain entities only.

## Add a new model

```python
# infrastructure/persistence/models/<entity>.py
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from {{ cookiecutter.package_name }}.infrastructure.persistence.models.base import Base


class <Entity>Model(Base):
    """``<entity>s`` table."""

    __tablename__ = "<entity>s"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    ...
```

## Generate a migration

```bash
uv run alembic revision --autogenerate -m "add_<entity>_table"
```

**Read the generated file before committing.** Autogenerate is a starting point, not the truth. Watch out for:

- Destructive `op.drop_*` calls — confirm they are intended.
- Missing `server_default` on new NOT NULL columns when the table already has rows.
- Ordering issues (FK target table must exist first).

## Downgrade is mandatory

Every migration must implement `downgrade()` non-trivially. The `script.py.mako` raises `NotImplementedError` if you forget — the CI test will fail. Test the round trip:

```bash
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

## Apply locally

```bash
uv run alembic upgrade head
```

In the devcontainer this happens automatically on `postStart`.

## Production

The Helm chart's `migration-job.yaml` runs `alembic upgrade head` as a `pre-install`/`pre-upgrade` hook (weight `-5`) before any pod boots on the new image. To disable for a project that uses a different schema management strategy, set `migrations.enabled: false` in values.
