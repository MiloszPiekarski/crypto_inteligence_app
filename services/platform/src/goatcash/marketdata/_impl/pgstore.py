"""`MarketStore` w Postgresie (schemat z migracji 0001-0003, ADR-0002 i ADR-0003).

Każdy `commit` to jedna transakcja: świece (`ON CONFLICT DO NOTHING`), zdarzenia DQ,
ceny referencyjne (upsert), `event_outbox` i punkt kontrolny. Świeca „poprawna” to świeca
bez zdarzenia `flagged` rodzaju odchylenie albo skok w tej samej chwili.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, LiteralString, cast

import psycopg

from goatcash.marketdata._impl.dq import CROSS_DEVIATION, DATASET, PRICE_SPIKE, DqEvent
from goatcash.marketdata._impl.events import OutboxEvent
from goatcash.marketdata._impl.store import Checkpoint, CommitBatch
from goatcash.marketdata._impl.types import (
    Candle,
    InstrumentInfo,
    TimeRange,
    datetime_to_ms,
    ms_to_datetime,
)
from goatcash.marketdata._impl.universe import Universe

FLAG_KINDS = (CROSS_DEVIATION, PRICE_SPIKE)

_GOOD: LiteralString = """
    NOT EXISTS (
        SELECT 1 FROM dq_events e
        WHERE e.dataset = %(dataset)s AND e.ts = c.ts AND e.instrument_id = c.instrument_id
          AND e.decision = 'flagged' AND e.kind = ANY(%(flag_kinds)s)
    )
"""


class PostgresStore:
    """Magazyn w Postgresie.

    Połączenie w trybie autocommit: odczyty nie zostawiają otwartej transakcji, a każdy
    zapis to jawny blok `transaction()` (bez autocommit blok wewnątrz niejawnej transakcji
    byłby tylko punktem zapisu i nie zatwierdzałby danych).
    """

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        conn.autocommit = True
        self._conn = conn
        self._ids: dict[tuple[str, str], int] = {}
        self._keys: dict[int, tuple[str, str]] = {}
        self._assets: dict[str, int] = {}

    # --- instrumenty ---

    def _load_ids(self) -> None:
        rows = self._conn.execute(
            "SELECT instrument_id, exchange, symbol FROM instruments WHERE kind = 'spot'"
        ).fetchall()
        for iid, ex, sym in rows:
            self._ids[(str(ex), str(sym))] = int(iid)
            self._keys[int(iid)] = (str(ex), str(sym))
        for aid, sym in self._conn.execute("SELECT asset_id, symbol FROM assets").fetchall():
            self._assets[str(sym)] = int(aid)

    def _id(self, exchange: str, symbol: str) -> int | None:
        if (exchange, symbol) not in self._ids:
            self._load_ids()
        return self._ids.get((exchange, symbol))

    def ensure_instruments(
        self, universe: Universe, infos: Sequence[InstrumentInfo]
    ) -> dict[tuple[str, str], int]:
        with self._conn.transaction():
            for asset in (universe.quote, *universe.bases):
                self._conn.execute(
                    "INSERT INTO assets (symbol, name, coingecko_id) VALUES (%s, %s, %s) "
                    "ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name, "
                    "coingecko_id = EXCLUDED.coingecko_id",
                    (asset.symbol, asset.name, asset.coingecko_id),
                )
            self._load_ids()
            for info in infos:
                self._conn.execute(
                    "INSERT INTO instruments (exchange, symbol, kind, base_asset_id, "
                    "quote_asset_id, active, price_tick, amount_step) "
                    "VALUES (%s, %s, 'spot', %s, %s, %s, %s, %s) "
                    "ON CONFLICT (exchange, symbol, kind) DO UPDATE SET active = EXCLUDED.active, "
                    "price_tick = EXCLUDED.price_tick, amount_step = EXCLUDED.amount_step",
                    (
                        info.exchange,
                        info.symbol,
                        self._assets[info.base],
                        self._assets[info.quote],
                        info.active,
                        info.price_tick,
                        info.amount_step,
                    ),
                )
        self._load_ids()
        return dict(self._ids)

    # --- punkty kontrolne ---

    def checkpoint(self, job: str, pair: str) -> Checkpoint | None:
        row = self._conn.execute(
            "SELECT cursor_ts FROM ingest_checkpoints WHERE job = %s AND pair = %s", (job, pair)
        ).fetchone()
        if row is None:
            return None
        return Checkpoint(job, pair, datetime_to_ms(cast(datetime, row[0])))

    # --- zapis ---

    def commit(self, batch: CommitBatch) -> None:
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO candles (instrument_id, timeframe, ts, open, high, low, close, "
                "volume, source) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (instrument_id, timeframe, ts) DO NOTHING",
                [
                    (
                        self._require_id(c.exchange, c.symbol),
                        c.timeframe,
                        ms_to_datetime(c.ts_ms),
                        c.open,
                        c.high,
                        c.low,
                        c.close,
                        c.volume,
                        f"{c.exchange}-rest",
                    )
                    for c in batch.candles
                ],
            )
            cur.executemany(
                "INSERT INTO dq_events (instrument_id, dataset, ts, kind, decision, details) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    (
                        self._require_id(e.exchange, e.symbol),
                        DATASET,
                        ms_to_datetime(e.ts_ms),
                        e.kind,
                        e.decision,
                        json.dumps(dict(e.details)),
                    )
                    for e in batch.events
                ],
            )
            cur.executemany(
                "INSERT INTO candles_ref (asset_id, quote_asset_id, timeframe, ts, open, high, "
                "low, close, volume, sources, source) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (asset_id, quote_asset_id, timeframe, ts) DO UPDATE SET "
                "open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, "
                "close = EXCLUDED.close, volume = EXCLUDED.volume, sources = EXCLUDED.sources, "
                "source = EXCLUDED.source, ingested_at = now()",
                [
                    (
                        self._assets[r.base],
                        self._assets[r.quote],
                        r.timeframe,
                        ms_to_datetime(r.ts_ms),
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        r.volume,
                        list(r.sources),
                        r.source,
                    )
                    for r in batch.refs
                ],
            )
            cur.executemany(
                "INSERT INTO event_outbox (event_id, type, schema_version, payload, occurred_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                [
                    (
                        o.event_id,
                        o.type,
                        o.schema_version,
                        json.dumps(dict(o.payload)),
                        o.occurred_at,
                    )
                    for o in batch.outbox
                ],
            )
            if batch.checkpoint is not None:
                cp = batch.checkpoint
                cur.execute(
                    "INSERT INTO ingest_checkpoints (job, pair, cursor_ts) VALUES (%s, %s, %s) "
                    "ON CONFLICT (job, pair) DO UPDATE SET cursor_ts = EXCLUDED.cursor_ts, "
                    "updated_at = now()",
                    (cp.job, cp.pair, ms_to_datetime(cp.cursor_ms)),
                )

    def _require_id(self, exchange: str, symbol: str) -> int:
        iid = self._id(exchange, symbol)
        if iid is None:
            raise KeyError(f"brak instrumentu {exchange} {symbol} (najpierw ensure_instruments)")
        return iid

    # --- odczyt ---

    def _candles(self, sql: LiteralString, params: dict[str, Any]) -> list[Candle]:
        rows = self._conn.execute(sql, params).fetchall()
        return [
            Candle(
                exchange=self._keys[int(r[0])][0],
                symbol=self._keys[int(r[0])][1],
                timeframe="1h",
                ts_ms=datetime_to_ms(cast(datetime, r[1])),
                open=cast(Decimal, r[2]),
                high=cast(Decimal, r[3]),
                low=cast(Decimal, r[4]),
                close=cast(Decimal, r[5]),
                volume=cast(Decimal, r[6]),
            )
            for r in rows
        ]

    def recent_good(self, exchange: str, symbol: str, before_ms: int, limit: int) -> list[Candle]:
        iid = self._id(exchange, symbol)
        if iid is None or limit <= 0:
            return []
        found = self._candles(
            "SELECT c.instrument_id, c.ts, c.open, c.high, c.low, c.close, c.volume "
            "FROM candles c WHERE c.instrument_id = %(iid)s AND c.timeframe = '1h' "
            "AND c.ts < %(before)s AND " + _GOOD + " ORDER BY c.ts DESC LIMIT %(limit)s",
            {
                "iid": iid,
                "before": ms_to_datetime(before_ms),
                "limit": limit,
                "dataset": DATASET,
                "flag_kinds": list(FLAG_KINDS),
            },
        )
        return found[::-1]

    def good_at(self, symbol: str, ts: Iterable[int]) -> dict[int, dict[str, Candle]]:
        wanted = [ms_to_datetime(t) for t in ts]
        if not wanted:
            return {}
        self._id("", symbol)  # odświeżenie mapy instrumentów
        ids = [iid for (_, sym), iid in self._ids.items() if sym == symbol]
        found = self._candles(
            "SELECT c.instrument_id, c.ts, c.open, c.high, c.low, c.close, c.volume "
            "FROM candles c WHERE c.instrument_id = ANY(%(ids)s) AND c.timeframe = '1h' "
            "AND c.ts = ANY(%(ts)s) AND " + _GOOD,
            {"ids": ids, "ts": wanted, "dataset": DATASET, "flag_kinds": list(FLAG_KINDS)},
        )
        result: dict[int, dict[str, Candle]] = {}
        for candle in found:
            result.setdefault(candle.ts_ms, {})[candle.exchange] = candle
        return result

    def present_ts(self, exchange: str, symbol: str, time_range: TimeRange) -> set[int]:
        iid = self._id(exchange, symbol)
        if iid is None:
            return set()
        rows = self._conn.execute(
            "SELECT ts FROM candles WHERE instrument_id = %s AND timeframe = '1h' "
            "AND ts >= %s AND ts < %s",
            (iid, ms_to_datetime(time_range.start_ms), ms_to_datetime(time_range.end_ms)),
        ).fetchall()
        return {datetime_to_ms(cast(datetime, r[0])) for r in rows}

    def first_ts(self, exchange: str, symbol: str) -> int | None:
        iid = self._id(exchange, symbol)
        if iid is None:
            return None
        row = self._conn.execute(
            "SELECT min(ts) FROM candles WHERE instrument_id = %s AND timeframe = '1h'", (iid,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return datetime_to_ms(cast(datetime, row[0]))

    def events(self, exchange: str, symbol: str, kinds: Iterable[str]) -> list[DqEvent]:
        iid = self._id(exchange, symbol)
        if iid is None:
            return []
        rows = self._conn.execute(
            "SELECT ts, kind, decision, details FROM dq_events WHERE instrument_id = %s "
            "AND dataset = %s AND kind = ANY(%s) ORDER BY dq_event_id",
            (iid, DATASET, list(kinds)),
        ).fetchall()
        return [
            DqEvent(
                exchange=exchange,
                symbol=symbol,
                ts_ms=datetime_to_ms(cast(datetime, r[0])),
                kind=str(r[1]),
                decision=cast(Any, str(r[2])),
                details={str(k): str(v) for k, v in cast(dict[str, object], r[3]).items()},
            )
            for r in rows
        ]

    # --- outbox (przekaźnik zdarzeń) ---

    def unpublished(self, limit: int) -> list[tuple[int, OutboxEvent]]:
        rows = self._conn.execute(
            "SELECT outbox_id, event_id, type, schema_version, payload, occurred_at "
            "FROM event_outbox WHERE published_at IS NULL ORDER BY outbox_id LIMIT %s",
            (limit,),
        ).fetchall()
        return [
            (
                int(r[0]),
                OutboxEvent(
                    event_id=r[1],
                    type=str(r[2]),
                    schema_version=int(r[3]),
                    payload=cast(dict[str, Any], r[4]),
                    occurred_at=cast(datetime, r[5]),
                ),
            )
            for r in rows
        ]

    def mark_published(self, outbox_ids: Sequence[int], published_at: datetime) -> None:
        with self._conn.transaction():
            self._conn.execute(
                "UPDATE event_outbox SET published_at = %s WHERE outbox_id = ANY(%s)",
                (published_at, list(outbox_ids)),
            )
