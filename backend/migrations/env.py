"""
SentinelAI · Entorno de Alembic.

La URL de la base NO está en alembic.ini: se lee de la variable de entorno,
igual que la aplicación. Así no hay credenciales versionadas ni dos fuentes
de verdad que se desincronicen.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Permite importar `app.*` cuando alembic corre desde backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# La variable de entorno gana siempre sobre el .ini
url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://sentinel:sentinel_local@db:5432/sentinelai",
)
config.set_main_option("sqlalchemy.url", url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Detecta cambios de tipo de columna. Sin esto, cambiar un String(100)
            # a String(300) no genera migración y la base queda desincronizada.
            compare_type=True,
            # Detecta cambios en valores por defecto del servidor.
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
