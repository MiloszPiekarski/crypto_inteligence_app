"""Migracja 0004 (E5): `feature_values` z kluczem pary aktywów i statusem, korelacja w outbox.

W obie strony na Postgresie z Timescale; migracja odmawia, gdy tabela cech ma dane (zamiast
po cichu je zgubić). Marker `migration` (`make db-migration-test`, Docker).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

pytestmark = pytest.mark.migration

PLATFORM = Path(__file__).resolve().parents[2]
IMAGE = (
    "timescale/timescaledb-ha:pg17"
    "@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
)


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with PostgresContainer(IMAGE, driver=None) as pg:
        yield pg.get_connection_url()


def alembic(db_url: str, target: str, *, down: bool = False) -> None:
    cfg = Config(str(PLATFORM / "alembic.ini"))
    os.environ["GOATCASH_DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+psycopg://")
    if down:
        command.downgrade(cfg, target)
    else:
        command.upgrade(cfg, target)


def execute(db_url: str, sql: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(sql)  # type: ignore[arg-type]


def columns(db_url: str, table: str) -> set[str]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,)
        ).fetchall()
    return {str(r[0]) for r in rows}


SEED = """
INSERT INTO assets (symbol, name) VALUES ('USDT', 'Tether'), ('BTC', 'Bitcoin');
INSERT INTO feature_sets (name, version, definition, code_version)
    VALUES ('fs-1p', 'v', '{}', 't');
"""
ROW = (
    "INSERT INTO feature_values (feature_set_id, asset_id, quote_asset_id, feature, as_of, "
    "data_cutoff, value, status) SELECT feature_set_id, 2, 1, 'rsi_14', now(), now(), 50, 'ok' "
    "FROM feature_sets"
)


def test_upgrade_downgrade_and_refusal_with_data(db_url: str) -> None:
    alembic(db_url, "head")
    assert {"asset_id", "quote_asset_id", "status"} <= columns(db_url, "feature_values")
    assert "instrument_id" not in columns(db_url, "feature_values")
    assert "correlation_id" in columns(db_url, "event_outbox")
    execute(db_url, SEED)
    execute(db_url, ROW)
    # Z danymi w feature_values migracja w dół się nie wykonuje (dane zostają).
    with pytest.raises(Exception, match="wymaga pustej tabeli"):
        alembic(db_url, "0003", down=True)
    execute(db_url, "DELETE FROM feature_values")
    alembic(db_url, "0003", down=True)
    assert "instrument_id" in columns(db_url, "feature_values")
    assert "correlation_id" not in columns(db_url, "event_outbox")
    # Wiersz w starym kształcie: migracja w górę też odmawia.
    execute(
        db_url,
        "INSERT INTO instruments (exchange, symbol, kind, base_asset_id, quote_asset_id) "
        "VALUES ('okx', 'BTC-USDT', 'spot', 2, 1)",
    )
    execute(
        db_url,
        "INSERT INTO feature_values (feature_set_id, instrument_id, feature, as_of, data_cutoff, "
        "value) SELECT feature_set_id, 1, 'x', now(), now(), 1 FROM feature_sets",
    )
    with pytest.raises(Exception, match="wymaga pustej tabeli"):
        alembic(db_url, "head")
    execute(db_url, "DELETE FROM feature_values")
    alembic(db_url, "head")
    execute(db_url, ROW)
    with psycopg.connect(db_url, autocommit=True) as conn:
        hypertable = conn.execute(
            "SELECT compression_enabled FROM timescaledb_information.hypertables "
            "WHERE hypertable_name = 'feature_values'"
        ).fetchone()
    assert hypertable == (True,)
