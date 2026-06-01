"""Alembic environment for async SQLAlchemy."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from {{ cookiecutter.package_name }}.infrastructure.persistence.models import Base


def _load_dotenv() -> None:
    """Inject ``.env`` values into ``os.environ`` if not already set.

    Avoids the dependency on ``python-dotenv`` for a 30-line shell-style parser.
    Called before alembic reads ``DB_URL`` so that ``uv run alembic ...`` works
    out of the box without the user manually sourcing ``.env``.
    """
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", os.environ.get("DB_URL", config.get_main_option("sqlalchemy.url", "")))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations against the URL only, no actual DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
