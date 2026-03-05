from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.config import get_settings
from app.database import Base
from app import models


config = context.config
settings = get_settings()


def _to_sync_alembic_url(raw_url: str) -> str:
    # Alembic must always use a synchronous driver.
    if raw_url.startswith("mysql+aiomysql://"):
        return raw_url.replace("mysql+aiomysql://", "mysql+pymysql://", 1)
    if raw_url.startswith("mysql+asyncmy://"):
        return raw_url.replace("mysql+asyncmy://", "mysql+pymysql://", 1)
    if raw_url.startswith("mysql://"):
        return raw_url.replace("mysql://", "mysql+pymysql://", 1)
    return raw_url


config.set_main_option("sqlalchemy.url", _to_sync_alembic_url(settings.database_url))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
