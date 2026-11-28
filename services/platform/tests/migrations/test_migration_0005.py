"""Migracja 0005 (E6): `assets.public_id` w górę i w dół z danymi (bramka G6p, `migrations`).

Doprecyzowanie kryterium G6p „bez utraty danych” (`docs/gates/G6p.md`):
- dane we wszystkich tabelach schematu `public` (suma kontrolna każdego wiersza bez
  kolumny `public_id`) są identyczne przed 0005, po 0005, po powrocie do 0004 i po
  ponownym 0005;
- w dół znika tylko kolumna `public_id`; jest wyliczana z symbolu, więc ponowne 0005 daje
  dokładnie te same identyfikatory (żadna informacja nie ginie);
- `public_id` = `asset_public_id(symbol)` z Pythona, unikalny, nadawany też nowym aktywom
  i niezmienialny ręcznie.
Marker `migration` (`make db-migration-test` w G2 i `make api-migration-test` w G6p, Docker).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

from goatcash.marketdata.api import asset_public_id

pytestmark = pytest.mark.migration

PLATFORM = Path(__file__).resolve().parents[2]
IMAGE = (
    "timescale/timescaledb-ha:pg17"
    "@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
)


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    if url := os.environ.get("GOATCASH_TEST_MIGRATION_DB_URL"):  # pusta baza, tylko lokalnie
        yield url
        return
    with PostgresContainer(IMAGE, driver=None) as pg:
        yield pg.get_connection_url()


def alembic(db_url: str, target: str, *, down: bool = False) -> None:
    cfg = Config(str(PLATFORM / "alembic.ini"))
    os.environ["GOATCASH_DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+psycopg://")
    if down:
        command.downgrade(cfg, target)
    else:
        command.upgrade(cfg, target)


def query(db_url: str, sql: str, params: Any = None) -> list[tuple[Any, ...]]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        return conn.execute(sql, params).fetchall()  # type: ignore[arg-type]


SEED = """
INSERT INTO assets (symbol, name, coingecko_id) VALUES
    ('USDT', 'Tether', 'tether'), ('BTC', 'Bitcoin', 'bitcoin'), ('ETH', 'Ethereum', NULL);
INSERT INTO instruments (exchange, symbol, kind, base_asset_id, quote_asset_id)
    SELECT e, b.symbol || '-USDT', 'spot', b.asset_id, q.asset_id
    FROM assets b, assets q, (VALUES ('okx'), ('bybit')) x(e)
    WHERE q.symbol = 'USDT' AND b.symbol <> 'USDT';
INSERT INTO candles (instrument_id, timeframe, ts, open, high, low, close, volume, source)
    SELECT i.instrument_id, '1h', TIMESTAMPTZ '2026-01-01 00:00+00' + g * INTERVAL '1 hour',
           100 + g, 101 + g, 99 + g, 100.5 + g, 10 * g, i.exchange
    FROM instruments i, generate_series(0, 47) g;
INSERT INTO candles_ref (asset_id, quote_asset_id, timeframe, ts, open, high, low, close, volume,
                         sources)
    SELECT b.asset_id, q.asset_id, '1h', TIMESTAMPTZ '2026-01-01 00:00+00' + g * INTERVAL '1 hour',
           100.123456789 + g, 101 + g, 99 + g, 100.5 + g, 20 * g, ARRAY['okx', 'bybit']
    FROM assets b, assets q, generate_series(0, 47) g
    WHERE q.symbol = 'USDT' AND b.symbol <> 'USDT';
INSERT INTO dq_events (instrument_id, dataset, ts, kind, decision, details)
    SELECT instrument_id, 'candles_1h', TIMESTAMPTZ '2026-01-01 05:00+00', 'price_spike',
           'flagged', '{"z": 7.5}' FROM instruments;
INSERT INTO dq_status (dataset, instrument_id, status, completeness, last_ts)
    SELECT 'candles_1h', instrument_id, 'ok', 1, TIMESTAMPTZ '2026-01-02 23:00+00'
    FROM instruments;
INSERT INTO ingest_checkpoints (job, pair, cursor_ts)
    VALUES ('candles_1h', 'BTC-USDT', TIMESTAMPTZ '2026-01-03 00:00+00');
INSERT INTO feature_sets (name, version, definition, code_version)
    VALUES ('fs-1p', 'abc', '{"n": 19}', 'test');
INSERT INTO feature_values (feature_set_id, asset_id, quote_asset_id, feature, as_of,
                            data_cutoff, value, status)
    SELECT f.feature_set_id, b.asset_id, q.asset_id, 'rsi_14',
           TIMESTAMPTZ '2026-01-02 00:00+00', TIMESTAMPTZ '2026-01-02 00:00+00', 55.5, 'ok'
    FROM feature_sets f, assets b, assets q WHERE q.symbol = 'USDT' AND b.symbol = 'BTC';
INSERT INTO event_outbox (event_id, type, schema_version, payload, occurred_at)
    VALUES ('0193a4f2-7c1e-7a3b-9d2e-000000000001', 'candle.closed', 1,
            '{"symbol": "BTC-USDT"}', TIMESTAMPTZ '2026-01-03 00:00+00');
"""
SEEDED = (
    "assets",
    "instruments",
    "candles",
    "candles_ref",
    "dq_events",
    "dq_status",
    "ingest_checkpoints",
    "feature_sets",
    "feature_values",
    "event_outbox",
)


def snapshot(db_url: str) -> dict[str, tuple[int, str]]:
    """Liczba wierszy i suma kontrolna treści każdej tabeli `public` (bez `public_id`)."""
    tables = [
        str(r[0])
        for r in query(
            db_url,
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename <> 'alembic_version' ORDER BY tablename",
        )
    ]
    result: dict[str, tuple[int, str]] = {}
    for table in tables:
        row = query(
            db_url,
            f"SELECT count(*), md5(coalesce(string_agg(j, '|' ORDER BY j), '')) FROM "  # noqa: S608
            f"(SELECT (to_jsonb(t) - 'public_id')::text AS j FROM public.\"{table}\" t) x",
        )[0]
        result[table] = (int(row[0]), str(row[1]))
    return result


def public_ids(db_url: str) -> dict[str, Any]:
    return {str(s): p for s, p in query(db_url, "SELECT symbol, public_id FROM assets")}


def has_column(db_url: str) -> bool:
    return bool(
        query(
            db_url,
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'assets' AND column_name = 'public_id'",
        )
    )


def test_upgrade_downgrade_with_data_keeps_everything(db_url: str) -> None:
    alembic(db_url, "0004")
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(SEED)  # type: ignore[arg-type]
    before = snapshot(db_url)
    assert all(before[t][0] > 0 for t in SEEDED), before

    alembic(db_url, "0005")
    assert snapshot(db_url) == before
    ids = public_ids(db_url)
    assert ids == {s: asset_public_id(s) for s in ("USDT", "BTC", "ETH")}
    assert len(set(ids.values())) == len(ids)

    alembic(db_url, "0004", down=True)
    assert not has_column(db_url)
    assert snapshot(db_url) == before

    alembic(db_url, "0005")
    assert public_ids(db_url) == ids  # te same identyfikatory po powrocie
    assert snapshot(db_url) == before


def test_public_id_for_new_assets_and_not_writable(db_url: str) -> None:
    alembic(db_url, "0005")
    query(db_url, "INSERT INTO assets (symbol, name) VALUES ('SOL', 'Solana') RETURNING 1")
    assert public_ids(db_url)["SOL"] == asset_public_id("SOL")
    with pytest.raises(psycopg.errors.Error):
        query(
            db_url,
            "UPDATE assets SET public_id = gen_random_uuid() WHERE symbol = 'SOL' RETURNING 1",
        )
    with pytest.raises(psycopg.errors.UniqueViolation):
        query(db_url, "INSERT INTO assets (symbol, name) VALUES ('SOL', 'x') RETURNING 1")
