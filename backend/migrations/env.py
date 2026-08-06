"""Alembic environment configuration script.

Loads database connection URL dynamically from backend.config settings and imports Base.metadata
along with all ORM models for autogenerate detection.
"""

import os
import sys
import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ------------------------------------------------------------------------------
# 1. Path Setup & Module Imports
# ------------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.config import settings
from backend.database import Base, _format_database_url
import backend.models  # Registers User, Issue, Vote, Comment, VolunteerTask, Notification models

logger = logging.getLogger("alembic.env")

# ------------------------------------------------------------------------------
# 2. Alembic Config Object & Logging Setup
# ------------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ------------------------------------------------------------------------------
# 3. Offline Migration Handler
# ------------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without an active DB connection string engine."""
    url = _format_database_url(settings.DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ------------------------------------------------------------------------------
# 4. Online Migration Handler
# ------------------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' mode by creating an Engine and connecting."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _format_database_url(settings.DATABASE_URL)

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
            )

            with context.begin_transaction():
                context.run_migrations()
    except Exception as e:
        logger.error(f"Alembic migration failed: {e}", exc_info=True)
        raise e


# ------------------------------------------------------------------------------
# 5. Execution Entry Point
# ------------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
