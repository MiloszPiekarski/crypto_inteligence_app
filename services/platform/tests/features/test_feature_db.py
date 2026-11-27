"""Cechy na prawdziwym Postgresie (Timescale) i Valkey (bramka G5p, `database`, marker `db`).

- źródło `candles_ref` w bazie = źródło w pamięci (te same bity, także z `known_at`);
- pełne przeliczenie historii zapisane w `feature_values` (rola `goatcash_app`) jest bit
  w bit równe przeliczeniu w pamięci, a drugie przeliczenie niczego nie zmienia (F-08);
- `candle.closed` → cechy + `features.ready` v2 w outbox w jednej transakcji, przekaźnik
  workera publikuje tylko `features.ready`, przekaźnik ingestu tylko `candle.closed`;
- konsument (ADR-0003): potwierdzenie po skutku, dead-letter po 5 nieudanych próbach;
- ograniczenia tabeli (NaN tylko poza `ok`) i uprawnienia ról.
Uruchomienie: `make features-db-test` (Docker). Lokalnie bez Dockera: `GOATCASH_TEST_DB_URL`
(baza po `alembic upgrade head`) i `GOATCASH_TEST_VALKEY_URL`.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
import redis
from alembic import command
from alembic.config import Config
from fs_helpers import BTC, ETH, H, real_series_refs
from test_job import ASSETS, candle_event, contract
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from goatcash.features.api import (
    DEAD_LETTER,
    FEATURES_READY,
    FeatureJob,
    InMemoryRefSource,
    PostgresFeatureStore,
    PostgresRefSource,
    StreamConsumer,
    recompute_history,
    values_digest,
)
from goatcash.marketdata.api import PostgresStore, RefCandle, relay_outbox

pytestmark = pytest.mark.db

PLATFORM = Path(__file__).resolve().parents[2]
# Te same obrazy co test migracji (G2), Compose staging (G3) i test bazy marketdata (G4p).
PG_IMAGE = (
    "timescale/timescaledb-ha:pg17"
    "@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
)
VALKEY_IMAGE = (
    "valkey/valkey:9.0.8-alpine"
    "@sha256:139d21c97b1a956e42e29b1e4ede4752a6ff52d1a0db9ef0ff4954a570f23976"
)


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    if url := os.environ.get("GOATCASH_TEST_DB_URL"):
        yield url
        return
    with PostgresContainer(PG_IMAGE, driver=None) as pg:
        url = pg.get_connection_url()
        cfg = Config(str(PLATFORM / "alembic.ini"))
        os.environ["GOATCASH_DATABASE_URL"] = url.replace("postgresql://", "postgresql+psycopg://")
        command.upgrade(cfg, "head")
        yield url


@pytest.fixture(scope="module")
def valkey() -> Iterator[redis.Redis]:
    if url := os.environ.get("GOATCASH_TEST_VALKEY_URL"):
        yield redis.Redis.from_url(url, decode_responses=True)  # pyright: ignore[reportUnknownMemberType]
        return
    with RedisContainer(VALKEY_IMAGE) as container:
        yield container.get_client(decode_responses=True)


@pytest.fixture(scope="module")
def refs() -> list[RefCandle]:
    return real_series_refs()


def _app(db_url: str) -> psycopg.Connection[Any]:
    conn = psycopg.connect(db_url, autocommit=True)
    conn.execute("SET ROLE goatcash_app")  # uprawnienia procesu worker, nie superużytkownika
    return conn


def _ingested(r: RefCandle) -> int:
    return r.ts_ms + 2 * H


@pytest.fixture
def loaded(db_url: str, refs: list[RefCandle], valkey: redis.Redis) -> str:
    """Pusta baza cech, w `candles_ref` prawdziwa cena referencyjna z kaset E4."""
    valkey.flushall()  # pyright: ignore[reportUnknownMemberType]
    with psycopg.connect(db_url, autocommit=True) as admin, admin.transaction():
        admin.execute(
            "TRUNCATE feature_values, feature_sets, candles_ref, event_outbox, instruments, "
            "assets RESTART IDENTITY CASCADE"
        )
        for symbol in sorted(ASSETS, key=ASSETS.__getitem__):
            admin.execute("INSERT INTO assets (symbol, name) VALUES (%s, %s)", (symbol, symbol))
        for symbol in sorted({r.base for r in refs} - set(ASSETS)):
            admin.execute("INSERT INTO assets (symbol, name) VALUES (%s, %s)", (symbol, symbol))
        with admin.cursor() as cur:
            cur.executemany(
                "INSERT INTO candles_ref (asset_id, quote_asset_id, timeframe, ts, open, high, "
                "low, close, volume, sources, source, ingested_at) "
                "SELECT b.asset_id, q.asset_id, '1h', %s, %s, %s, %s, %s, %s, %s, %s, %s "
                "FROM assets b, assets q WHERE b.symbol = %s AND q.symbol = %s",
                [
                    (
                        datetime.fromtimestamp(r.ts_ms / 1000, tz=UTC),
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        r.volume,
                        list(r.sources),
                        r.source,
                        datetime.fromtimestamp(_ingested(r) / 1000, tz=UTC),
                        r.base,
                        r.quote,
                    )
                    for r in refs
                ],
            )
    return db_url


def _memory(refs: list[RefCandle]) -> InMemoryRefSource:
    return InMemoryRefSource.from_ref_candles(
        refs, ingested_at_ms={(r.base, r.quote, r.ts_ms): _ingested(r) for r in refs}
    )


def _until(refs: list[RefCandle]) -> int:
    return max(r.ts_ms for r in refs) + H


def test_ref_source_matches_memory(loaded: str, refs: list[RefCandle]) -> None:
    pg = PostgresRefSource(_app(loaded))
    mem = _memory(refs)
    assert list(pg.pairs()) == list(mem.pairs())
    until = _until(refs)
    for pair in mem.pairs():
        for close_until, known_at in (
            (until, None),
            (until - 500 * H, None),
            (until, until - 900 * H),
        ):
            assert list(
                pg.ref_bars(pair, close_until_ms=close_until, known_at_ms=known_at)
            ) == list(mem.ref_bars(pair, close_until_ms=close_until, known_at_ms=known_at))


def test_recompute_in_database_is_bit_identical(loaded: str, refs: list[RefCandle]) -> None:
    until = _until(refs)
    expected = recompute_history(_memory(refs), until_ms=until)
    job = FeatureJob(
        PostgresFeatureStore(_app(loaded)), PostgresRefSource(_app(loaded)), code_version="t"
    )
    assert job.recompute(until) > 0
    stored = job.store.values(job.feature_set_id)
    assert stored.height == expected.height
    assert values_digest(stored) == values_digest(expected)  # zapis i odczyt bez zmiany bitów
    # Drugie pełne przeliczenie (nowe połączenia, nowy proces zadania): nic się nie zmienia.
    again = FeatureJob(
        PostgresFeatureStore(_app(loaded)), PostgresRefSource(_app(loaded)), code_version="t"
    )
    assert again.feature_set_id == job.feature_set_id
    assert again.recompute(until) == 0
    assert values_digest(again.store.values(job.feature_set_id)) == values_digest(expected)


def test_candle_closed_outbox_and_relays(
    loaded: str, refs: list[RefCandle], valkey: redis.Redis
) -> None:
    ts = _until(refs) - 2 * H
    job = FeatureJob(
        PostgresFeatureStore(_app(loaded)), PostgresRefSource(_app(loaded)), code_version="t"
    )
    trigger = candle_event(ETH, ts)
    (event,) = job.on_candle_closed(trigger)
    assert job.on_candle_closed(trigger) == []  # powtórka: bez zmian, bez zdarzenia
    outbox = PostgresStore(_app(loaded))
    # Przekaźnik ingestu (tylko candle.closed) nie publikuje zdarzeń workera.
    assert relay_outbox(outbox, valkey, producer="ingest@t", types=("candle.closed",)) == 0  # pyright: ignore[reportArgumentType]
    assert relay_outbox(outbox, valkey, producer="worker@0.1.0", types=(FEATURES_READY,)) == 1  # pyright: ignore[reportArgumentType]
    entries = cast(list[tuple[str, dict[str, str]]], valkey.xrange("ev:features.ready"))
    (doc,) = [json.loads(fields["event"]) for _, fields in entries]
    assert list(contract("features.ready", 2).iter_errors(doc)) == []  # pyright: ignore[reportUnknownMemberType]
    assert doc["event_id"] == str(event.event_id)
    assert doc["correlation_id"] == trigger["event_id"]
    assert doc["producer"] == "worker@0.1.0"
    assert valkey.xlen("ev:candle.closed") == 0


def test_consumer_acks_after_effect_and_dead_letters(
    loaded: str, refs: list[RefCandle], valkey: redis.Redis
) -> None:
    ts = _until(refs) - 3 * H
    job = FeatureJob(
        PostgresFeatureStore(_app(loaded)), PostgresRefSource(_app(loaded)), code_version="t"
    )
    consumer = StreamConsumer(valkey, job.on_candle_closed, consumer="c1")  # pyright: ignore[reportArgumentType]
    consumer.ensure_group()
    consumer.ensure_group()  # druga próba: grupa już jest (BUSYGROUP) bez błędu
    valkey.xadd("ev:candle.closed", {"event": json.dumps(candle_event(BTC, ts))})
    assert consumer.step(block_ms=100) == 1
    assert valkey.xpending("ev:candle.closed", "features")["pending"] == 0
    with psycopg.connect(loaded, autocommit=True) as conn:
        pairs = conn.execute(
            "SELECT count(DISTINCT asset_id) FROM feature_values WHERE as_of = %s",
            (datetime.fromtimestamp((ts + H) / 1000, tz=UTC),),
        ).fetchone()
    assert pairs is not None
    assert pairs[0] == 5  # BTC i pozostałe pary z kwotowaniem USDT (korelacja z BTC)
    # Komunikat, którego nie da się obsłużyć: 5 dostarczeń, potem ev:dead-letter i XACK.
    broken = StreamConsumer(valkey, job.on_candle_closed, consumer="c2", claim_idle_ms=0)  # pyright: ignore[reportArgumentType]
    valkey.xadd(
        "ev:candle.closed", {"event": json.dumps({**candle_event(ETH, ts), "schema_version": 9})}
    )
    for _ in range(5):
        broken.step(block_ms=10)
    assert valkey.xpending("ev:candle.closed", "features")["pending"] == 0
    dead = cast(list[tuple[str, dict[str, str]]], valkey.xrange(DEAD_LETTER))
    assert len(dead) == 1
    assert "UnsupportedEventError" in dead[0][1]["reason"]


@pytest.mark.parametrize(
    ("value", "status"),
    [(math.nan, "ok"), (1.0, "missing_data"), (1.0, "nieznany")],
)
def test_table_rejects_value_status_mismatch(loaded: str, value: float, status: str) -> None:
    job = FeatureJob(
        PostgresFeatureStore(_app(loaded)), PostgresRefSource(_app(loaded)), code_version="t"
    )
    with pytest.raises(psycopg.errors.CheckViolation), _app(loaded) as conn:
        conn.execute(
            "INSERT INTO feature_values (feature_set_id, asset_id, quote_asset_id, feature, as_of, "
            "data_cutoff, value, status) VALUES (%s, 2, 1, 'x', now(), now(), %s, %s)",
            (job.feature_set_id, value, status),
        )


def test_readonly_role_reads_but_cannot_write(loaded: str) -> None:
    with psycopg.connect(loaded, autocommit=True) as conn:
        conn.execute("SET ROLE goatcash_readonly")
        conn.execute("SELECT * FROM feature_values LIMIT 1")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM feature_values")
