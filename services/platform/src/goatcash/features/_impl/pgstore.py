"""Cechy w Postgresie: źródło świec `candles_ref` i magazyn `feature_values` (migracja 0004).

Połączenie w trybie autocommit, każdy zapis w jawnym bloku `transaction()` (jak
`marketdata.PostgresStore`). Wartości cech jako `double precision`: Postgres zwraca
najkrótszy zapis dokładny (`extra_float_digits` = 1, domyślnie od PG 12), więc odczyt daje
te same bity co zapis (sprawdza test bazy: skrót przeliczenia przed i po zapisie).
"""

from __future__ import annotations

import json
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

import polars as pl
import psycopg

from goatcash.features._impl.store import LONG_SCHEMA, Changed, FeatureSetMismatchError
from goatcash.features._impl.types import HOUR_MS, Pair, RefBar
from goatcash.marketdata.api import OutboxEvent

_CHUNK = 50_000

_REF_BARS = """
SELECT r.ts, r.open, r.high, r.low, r.close, r.volume, r.ingested_at
FROM candles_ref r
JOIN assets b ON b.asset_id = r.asset_id
JOIN assets q ON q.asset_id = r.quote_asset_id
WHERE b.symbol = %(base)s AND q.symbol = %(quote)s AND r.timeframe = '1h'
  AND r.ts <= %(last_ts)s
  AND (%(known_at)s::timestamptz IS NULL OR r.ingested_at <= %(known_at)s::timestamptz)
ORDER BY r.ts
"""

_UPSERT = """
INSERT INTO feature_values AS fv
    (feature_set_id, asset_id, quote_asset_id, feature, as_of, data_cutoff, value, status)
SELECT %(set_id)s, a, q, f, t, c, v, s
FROM unnest(%(a)s::bigint[], %(q)s::bigint[], %(f)s::text[], %(t)s::timestamptz[],
            %(c)s::timestamptz[], %(v)s::double precision[], %(s)s::text[])
     AS x(a, q, f, t, c, v, s)
ON CONFLICT (feature_set_id, asset_id, quote_asset_id, feature, as_of) DO UPDATE
SET value = EXCLUDED.value, status = EXCLUDED.status, data_cutoff = EXCLUDED.data_cutoff,
    ingested_at = now()
WHERE (fv.value, fv.status, fv.data_cutoff)
      IS DISTINCT FROM (EXCLUDED.value, EXCLUDED.status, EXCLUDED.data_cutoff)
RETURNING fv.asset_id, fv.quote_asset_id, fv.as_of
"""

_VALUES = """
SELECT b.symbol, q.symbol, fv.feature, fv.as_of, fv.data_cutoff, fv.value, fv.status
FROM feature_values fv
JOIN assets b ON b.asset_id = fv.asset_id
JOIN assets q ON q.asset_id = fv.quote_asset_id
WHERE fv.feature_set_id = %s
ORDER BY b.symbol, q.symbol, fv.feature, fv.as_of
"""


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def _ms(dt: datetime) -> int:
    return round(dt.timestamp() * 1000)


class PostgresRefSource:
    """`RefCandleSource` z tabeli `candles_ref` (Decimal → float jak w źródle w pamięci)."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        conn.autocommit = True
        self._conn = conn

    def pairs(self) -> Sequence[Pair]:
        rows = self._conn.execute(
            "SELECT DISTINCT b.symbol, q.symbol FROM candles_ref r "
            "JOIN assets b ON b.asset_id = r.asset_id "
            "JOIN assets q ON q.asset_id = r.quote_asset_id WHERE r.timeframe = '1h' "
            "ORDER BY 1, 2"
        ).fetchall()
        return [Pair(str(b), str(q)) for b, q in rows]

    def ref_bars(
        self, pair: Pair, *, close_until_ms: int, known_at_ms: int | None
    ) -> Sequence[RefBar]:
        rows = self._conn.execute(
            _REF_BARS,
            {
                "base": pair.base,
                "quote": pair.quote,
                "last_ts": _dt(close_until_ms - HOUR_MS),
                "known_at": None if known_at_ms is None else _dt(known_at_ms),
            },
        ).fetchall()
        return [
            RefBar(
                ts_ms=_ms(cast(datetime, r[0])),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
                ingested_at_ms=_ms(cast(datetime, r[6])),
            )
            for r in rows
        ]


class PostgresFeatureStore:
    """`FeatureStore` w Postgresie (rola procesu: `goatcash_app`)."""

    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        conn.autocommit = True
        self._conn = conn
        self._assets: dict[str, int] = {}
        self._symbols: dict[int, str] = {}

    @contextmanager
    def transaction(self) -> Generator[None]:
        with self._conn.transaction():
            yield

    def ensure_feature_set(
        self, name: str, version: str, definition: dict[str, Any], code_version: str
    ) -> int:
        self._conn.execute(
            "INSERT INTO feature_sets (name, version, definition, code_version) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (name, version) DO NOTHING",
            (name, version, json.dumps(definition), code_version),
        )
        row = self._conn.execute(
            "SELECT feature_set_id, definition FROM feature_sets WHERE name = %s AND version = %s",
            (name, version),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"{name} {version}: brak wiersza feature_sets po zapisie")
        if row[1] != definition:
            raise FeatureSetMismatchError(f"{name} {version}: inna definicja niż zapisana")
        return int(row[0])

    def _load_assets(self) -> None:
        for aid, sym in self._conn.execute("SELECT asset_id, symbol FROM assets").fetchall():
            self._assets[str(sym)] = int(aid)
            self._symbols[int(aid)] = str(sym)

    def asset_ids(self, pair: Pair) -> tuple[int, int] | None:
        if pair.base not in self._assets or pair.quote not in self._assets:
            self._load_assets()
        if pair.base in self._assets and pair.quote in self._assets:
            return self._assets[pair.base], self._assets[pair.quote]
        return None

    def upsert_values(self, feature_set_id: int, frame: pl.DataFrame) -> Changed:
        changed: Changed = set()
        for start in range(0, frame.height, _CHUNK):
            part = frame.slice(start, _CHUNK)
            ids = [self.asset_ids(Pair(b, q)) for b, q in part.select("base", "quote").iter_rows()]
            if any(i is None for i in ids):
                raise KeyError("para bez wpisu w assets")
            known = cast(list[tuple[int, int]], ids)
            rows = self._conn.execute(
                _UPSERT,
                {
                    "set_id": feature_set_id,
                    "a": [i[0] for i in known],
                    "q": [i[1] for i in known],
                    "f": part["feature"].to_list(),
                    "t": [_dt(x) for x in part["as_of"].to_list()],
                    "c": [_dt(x) for x in part["data_cutoff"].to_list()],
                    "v": part["value"].to_list(),
                    "s": part["status"].to_list(),
                },
            ).fetchall()
            for aid, qid, as_of in rows:
                changed.add((self._symbols[int(aid)], self._symbols[int(qid)], _ms(as_of)))
        return changed

    def add_outbox(self, events: Sequence[OutboxEvent]) -> None:
        with self._conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO event_outbox (event_id, type, schema_version, payload, occurred_at, "
                "correlation_id) VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    (
                        e.event_id,
                        e.type,
                        e.schema_version,
                        json.dumps(dict(e.payload)),
                        e.occurred_at,
                        e.correlation_id,
                    )
                    for e in events
                ],
            )

    def values(self, feature_set_id: int) -> pl.DataFrame:
        rows = self._conn.execute(_VALUES, (feature_set_id,)).fetchall()
        return pl.DataFrame(
            [
                (str(b), str(q), str(f), _ms(t), _ms(c), float(v), str(s))
                for b, q, f, t, c, v, s in rows
            ],
            schema=LONG_SCHEMA,
            orient="row",
        )
