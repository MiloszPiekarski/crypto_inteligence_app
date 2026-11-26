"""marketdata na prawdziwym Postgresie (Timescale) i Valkey (bramka G4p, marker `db`).

Ten sam scenariusz co `test_ingest.py` (atrapy giełd, luki giełdy, nasze i błędna świeca)
na `PostgresStore` z rolą `goatcash_app` (uprawnienia z migracji) i na `InMemoryStore`:
wynik (świece, ceny referencyjne, zdarzenia DQ, raport) musi być identyczny. Przekaźnik
publikuje `candle.closed` do Valkey; zdarzenia ze strumienia przechodzą schemat kontraktu.
Uruchomienie: `make marketdata-db-test` (Docker).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
import redis
from alembic import command
from alembic.config import Config
from md_helpers import FakeSource, gbm_series, mirror
from test_gaps_refprice_events import validator
from test_ingest import NOW, START, scenario
from test_resilience import START as RESILIENCE_START
from test_resilience import ingest as resilience_ingest
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from goatcash.marketdata._impl.events import STREAM
from goatcash.marketdata.api import (
    HOUR_MS,
    InMemoryStore,
    MarketStore,
    PostgresStore,
    instrument_report,
    relay_outbox,
)

pytestmark = pytest.mark.db

H = HOUR_MS
PLATFORM = Path(__file__).resolve().parents[2]
# Te same obrazy co test migracji (G2) i Compose staging (G3), przypięte do digestu.
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
    with PostgresContainer(PG_IMAGE, driver=None) as pg:
        url = pg.get_connection_url()
        cfg = Config(str(PLATFORM / "alembic.ini"))
        os.environ["GOATCASH_DATABASE_URL"] = url.replace("postgresql://", "postgresql+psycopg://")
        command.upgrade(cfg, "head")
        yield url


@pytest.fixture(scope="module")
def valkey() -> Iterator[redis.Redis]:
    with RedisContainer(VALKEY_IMAGE) as container:
        client = container.get_client(decode_responses=True)
        yield client


@pytest.fixture
def store(db_url: str) -> Iterator[PostgresStore]:
    with psycopg.connect(db_url, autocommit=True) as admin:
        admin.execute(
            "TRUNCATE candles, candles_ref, dq_events, event_outbox, ingest_checkpoints, "
            "instruments, assets RESTART IDENTITY CASCADE"
        )
    conn = psycopg.connect(db_url, autocommit=True)
    conn.execute("SET ROLE goatcash_app")  # uprawnienia procesu ingest, nie superużytkownika
    yield PostgresStore(conn)
    conn.close()


def dump_memory(mem: InMemoryStore) -> dict[str, Any]:
    return {
        "candles": sorted(
            (ex, sym, ts, str(c.open), str(c.high), str(c.low), str(c.close), str(c.volume))
            for (ex, sym, ts), c in mem.candles.items()
        ),
        "refs": sorted(
            (r.base, r.quote, r.ts_ms, str(r.close), r.sources, r.source) for r in mem.refs.values()
        ),
        "events": sorted((e.exchange, e.ts_ms, e.kind, e.decision) for e in mem.dq_events),
    }


def dump_pg(db_url: str) -> dict[str, Any]:
    def norm(value: Any) -> str:
        return format(value.normalize(), "f") if hasattr(value, "normalize") else str(value)

    with psycopg.connect(db_url, autocommit=True) as conn:
        candles = conn.execute(
            "SELECT i.exchange, i.symbol, c.ts, c.open, c.high, c.low, c.close, c.volume "
            "FROM candles c JOIN instruments i USING (instrument_id)"
        ).fetchall()
        refs = conn.execute(
            "SELECT b.symbol, q.symbol, r.ts, r.close, r.sources, r.source FROM candles_ref r "
            "JOIN assets b ON b.asset_id = r.asset_id "
            "JOIN assets q ON q.asset_id = r.quote_asset_id"
        ).fetchall()
        events = conn.execute(
            "SELECT i.exchange, e.ts, e.kind, e.decision FROM dq_events e "
            "JOIN instruments i USING (instrument_id)"
        ).fetchall()
    return {
        "candles": sorted(
            (ex, sym, ms(ts), *(norm(v) for v in (o, h, lo, c, v_)))
            for ex, sym, ts, o, h, lo, c, v_ in candles
        ),
        "refs": sorted((b, q, ms(ts), norm(c), tuple(s), src) for b, q, ts, c, s, src in refs),
        "events": sorted((ex, ms(ts), k, d) for ex, ts, k, d in events),
    }


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def fix(text: str) -> str:
    return format(Decimal(text).normalize(), "f")


def normalized_memory(mem: InMemoryStore) -> dict[str, Any]:
    d = dump_memory(mem)
    d["candles"] = sorted((*row[:3], *(fix(v) for v in row[3:])) for row in d["candles"])
    d["refs"] = sorted((*row[:3], fix(row[3]), *row[4:]) for row in d["refs"])
    return d


def run_scenario(target: MarketStore, delete: Callable[[int], None]) -> None:
    ing, _, _ = scenario(target)
    ing.backfill_pair("BTC-USDT")
    for ts in (START + 100 * H, START + 101 * H, START + 1400 * H):
        delete(ts)
    ing.repair_gaps("BTC-USDT", "okx")
    ing.repair_gaps("BTC-USDT", "bybit")


def test_postgres_matches_memory_and_report_is_complete(store: PostgresStore, db_url: str) -> None:
    mem = InMemoryStore()

    def delete_mem(ts: int) -> None:
        del mem.candles[("okx", "BTC-USDT", ts)]

    run_scenario(mem, delete_mem)

    def delete_pg(ts: int) -> None:
        with psycopg.connect(db_url, autocommit=True) as admin:
            admin.execute(
                "DELETE FROM candles WHERE ts = to_timestamp(%s / 1000.0) AND instrument_id = "
                "(SELECT instrument_id FROM instruments "
                "WHERE exchange = 'okx' AND symbol = 'BTC-USDT')",
                (ts,),
            )

    run_scenario(store, delete_pg)
    assert dump_pg(db_url) == normalized_memory(mem)
    for ex in ("okx", "bybit"):
        assert instrument_report(store, ex, "BTC-USDT", NOW) == instrument_report(
            mem, ex, "BTC-USDT", NOW
        )
        assert instrument_report(store, ex, "BTC-USDT", NOW).unexplained == ()


def test_resume_from_checkpoint_in_postgres(store: PostgresStore, db_url: str) -> None:
    okx = gbm_series(2000, seed=5, t0=RESILIENCE_START)
    bybit = mirror(okx, exchange="bybit", seed=6)
    failing = FakeSource("okx", okx, fail_on_call=lambda n: n == 3)
    with pytest.raises(Exception, match="awaria testowa"):
        resilience_ingest(store, failing, FakeSource("bybit", bybit)).backfill_pair("BTC-USDT")  # pyright: ignore[reportArgumentType]
    resilience_ingest(store, FakeSource("okx", okx), FakeSource("bybit", bybit)).backfill_pair(
        "BTC-USDT"
    )  # pyright: ignore[reportArgumentType]
    with psycopg.connect(db_url, autocommit=True) as conn:
        (count,) = conn.execute("SELECT count(*) FROM candles").fetchone() or (0,)
        (dups,) = conn.execute(
            "SELECT count(*) FROM dq_events WHERE kind = 'duplicate'"
        ).fetchone() or (0,)
    assert count == 4000
    assert dups == 0


def test_relay_to_valkey_and_events_match_contract(
    store: PostgresStore, valkey: redis.Redis
) -> None:
    ing, _, _ = scenario(store)
    ing.backfill_pair("BTC-USDT")
    valkey.delete(STREAM)
    published = relay_outbox(store, valkey, producer="ingest@0.1.0")  # pyright: ignore[reportArgumentType]
    assert published > 0
    assert store.unpublished(10) == []
    entries = cast(list[tuple[str, dict[str, str]]], valkey.xrange(STREAM))
    assert len(entries) == published
    v = validator()
    for _, fields in entries:
        v.validate(json.loads(fields["event"]))  # pyright: ignore[reportUnknownMemberType]
