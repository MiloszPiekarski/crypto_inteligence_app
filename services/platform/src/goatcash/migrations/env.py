"""Środowisko Alembic: migracje pisane ręcznie (SQL), bez autogenerate (ADR-0002)."""

import os

from alembic import context
from sqlalchemy import create_engine, pool


def database_url() -> str:
    url = context.get_x_argument(as_dictionary=True).get("url") or os.environ.get(
        "GOATCASH_DATABASE_URL"
    )
    if not url:
        raise RuntimeError("Brak GOATCASH_DATABASE_URL (albo -x url=...): adres bazy dla migracji")
    return url


def run_offline() -> None:
    context.configure(url=database_url(), literal_binds=True, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
