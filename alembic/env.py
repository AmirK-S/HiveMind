"""Alembic migration environment for HiveMind.

Configured for async SQLAlchemy with pgvector type registration.

References:
- https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
- https://github.com/sqlalchemy/alembic/discussions/1324 (pgvector registration)
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Alembic config object — gives access to alembic.ini values
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import ORM models so Alembic autogenerate knows the target schema
from hivemind.db.models import Base  # noqa: E402

target_metadata = Base.metadata

# Override the database URL from HiveMind settings (takes precedence over alembic.ini)
from hivemind.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.database_url)


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations against a live connection.

    Registers the pgvector VECTOR type with the connection so Alembic
    autogenerate can recognise vector columns during diff operations.
    """
    # Register pgvector types so Alembic autogenerate recognises VECTOR columns
    from pgvector.sqlalchemy import register_vector

    register_vector(connection)

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=False,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations online.

    Uses NullPool so connections are not pooled during migrations — each
    migration command gets a fresh connection and releases it immediately.
    """
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (SQL script generation).

    Emits SQL to stdout instead of connecting to a database.  Useful for
    generating migration scripts to review before running.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct database connection).

    Uses asyncio.run() to execute the async migration function.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
