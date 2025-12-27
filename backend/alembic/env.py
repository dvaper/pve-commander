"""
Alembic Environment Configuration for PVE Commander

Konfiguriert Alembic fuer:
- SQLAlchemy async mit aiosqlite
- Automatische Model-Erkennung
- Integration mit app.config.settings
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# App-Imports
from app.database import Base
from app.config import settings

# Alle Models importieren damit sie bei Base.metadata registriert sind
from app.models import user, execution, execution_log, vm_template, vm_history
from app.models import permission, role, role_permission, user_role
from app.models import notification_settings, notification_log, webhook
from app.models import user_notification_preferences, user_playbook_access, user_group_access
from app.models import audit_log, audit_rollback, backup, cloud_init_settings
from app.models import app_settings, terraform_health, playbook_metadata, password_reset_token


# Alembic Config-Objekt
config = context.config

# Logging konfigurieren
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target Metadata fuer Autogenerate
target_metadata = Base.metadata


def get_url():
    """Gibt die Datenbank-URL zurueck."""
    return settings.database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generiert SQL-Scripts ohne Datenbankverbindung.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Fuehrt Migrationen mit einer Verbindung aus."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' mode mit async Engine.
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
