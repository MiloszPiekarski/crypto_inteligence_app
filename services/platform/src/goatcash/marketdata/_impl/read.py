"""Odczyt danych rynkowych dla API tylko do odczytu (roadmapa E6, ścieżka pracy, ADR-0008).

Źródłem jest cena referencyjna `candles_ref` (mediana giełd, E4) w jednym kwotowaniu
uniwersum (decyzja D5 z 28.11.2026: bez parametru kwotowania w API). Interwały (decyzja
D3): `1h` wprost z `candles_ref`, `4h` i `1d` liczone z pełnych okresów świec 1 h
(okres UTC wyrównany do północy: 4 albo 24 świece). Okres z brakującą świecą 1 h nie jest
zwracany: brak danych jest widoczny jako brak świecy, a nie jako świeca z niepełnych danych.

Dwie implementacje o tym samym zachowaniu: w pamięci (testy, Schemathesis bez Dockera)
i w Postgresie (proces `api`); test `make api-db-test` porównuje je na tych samych danych.
Kolejność: aktywa rosnąco po symbolu, świece od najnowszej. Paginacja kursorowa: kursor
to ostatni element poprzedniej strony (symbol albo początek świecy), bez przesunięć OFFSET.
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal, LiteralString, Protocol, cast
from uuid import UUID

import psycopg

from goatcash.marketdata._impl.dq import DATASET as DQ_DATASET
from goatcash.marketdata._impl.refprice import RefCandle
from goatcash.marketdata._impl.types import HOUR_MS, datetime_to_ms, ms_to_datetime

ApiTimeframe = Literal["1h", "4h", "1d"]
# Liczba świec 1 h w pełnym okresie interwału.
HOURS: dict[ApiTimeframe, int] = {"1h": 1, "4h": 4, "1d": 24}
DQ_ORDER = ("ok", "degraded", "stale", "down")  # od najlepszego; przegląd pokazuje najgorszy
PUBLIC_ID_PREFIX = "goatcash:asset:"


def asset_public_id(symbol: str) -> UUID:
    """Publiczny identyfikator aktywa: md5 z prefiksu i symbolu (migracja 0005).

    Wyliczany z symbolu (kolumna generowana w bazie), więc migracja w dół i ponownie
    w górę daje te same identyfikatory, a numeracja wewnętrzna `asset_id` nie wychodzi
    na zewnątrz. To nie jest zabezpieczenie (identyfikator jest publiczny).
    """
    digest = hashlib.md5((PUBLIC_ID_PREFIX + symbol).encode(), usedforsecurity=False)
    return UUID(digest.hexdigest())


@dataclass(frozen=True, slots=True)
class AssetInfo:
    public_id: UUID
    symbol: str
    name: str


@dataclass(frozen=True, slots=True)
class Bar:
    """Świeca ceny referencyjnej interwału (początek okresu w ms UTC)."""

    ts_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class OverviewRow:
    asset: AssetInfo
    ts_ms: int  # początek ostatniej świecy 1 h
    close: Decimal
    close_24h_ago: Decimal | None  # zamknięcie świecy sprzed 24 h (brak świecy = None)
    volume_24h: Decimal | None  # suma 24 ostatnich świec, tylko gdy są wszystkie
    dq_status: str | None  # najgorszy status DQ giełd pary (brak wpisów = None)


class MarketReader(Protocol):
    def list_assets(self, after: str | None, limit: int) -> list[AssetInfo]:
        """Aktywa rosnąco po symbolu, po symbolu `after` (wyłącznie)."""
        ...

    def get_asset(self, public_id: UUID) -> AssetInfo | None: ...

    def candles(
        self, public_id: UUID, timeframe: ApiTimeframe, before_ms: int | None, limit: int
    ) -> list[Bar]:
        """Świece od najnowszej, o początku przed `before_ms` (wyłącznie)."""
        ...

    def overview(self) -> list[OverviewRow]: ...


def period_start(ts_ms: int, timeframe: ApiTimeframe) -> int:
    span = HOURS[timeframe] * HOUR_MS
    return ts_ms - ts_ms % span


def aggregate(hourly: Iterable[Bar], timeframe: ApiTimeframe) -> list[Bar]:
    """Pełne okresy interwału ze świec 1 h, rosnąco; okres z brakującą świecą pominięty."""
    need = HOURS[timeframe]
    if need == 1:
        return sorted(hourly, key=lambda b: b.ts_ms)
    groups: dict[int, list[Bar]] = {}
    for bar in hourly:
        groups.setdefault(period_start(bar.ts_ms, timeframe), []).append(bar)
    result: list[Bar] = []
    for start in sorted(groups):
        bars = sorted(groups[start], key=lambda b: b.ts_ms)
        if len({b.ts_ms for b in bars}) != need:
            continue
        result.append(
            Bar(
                ts_ms=start,
                open=bars[0].open,
                high=max(b.high for b in bars),
                low=min(b.low for b in bars),
                close=bars[-1].close,
                volume=sum((b.volume for b in bars), Decimal(0)),
            )
        )
    return result


def worst_dq(statuses: Iterable[str]) -> str | None:
    found = [s for s in statuses if s in DQ_ORDER]
    return max(found, key=DQ_ORDER.index) if found else None


def overview_row(asset: AssetInfo, hourly: Sequence[Bar], dq: Iterable[str]) -> OverviewRow | None:
    """Wiersz przeglądu z rosnących świec 1 h aktywa (brak świec = brak wiersza)."""
    if not hourly:
        return None
    last = hourly[-1]
    by_ts = {b.ts_ms: b for b in hourly}
    ago = by_ts.get(last.ts_ms - 24 * HOUR_MS)
    window = [by_ts.get(last.ts_ms - i * HOUR_MS) for i in range(24)]
    volume = None
    if all(b is not None for b in window):
        volume = sum((cast(Bar, b).volume for b in window), Decimal(0))
    return OverviewRow(
        asset=asset,
        ts_ms=last.ts_ms,
        close=last.close,
        close_24h_ago=None if ago is None else ago.close,
        volume_24h=volume,
        dq_status=worst_dq(dq),
    )


class InMemoryReader:
    """`MarketReader` na liście `RefCandle` (jedno kwotowanie) i statusach DQ par."""

    def __init__(
        self,
        quote: str,
        names: dict[str, str],
        refs: Iterable[RefCandle],
        dq: dict[str, list[str]] | None = None,
    ) -> None:
        self._assets = {
            s: AssetInfo(asset_public_id(s), s, n) for s, n in sorted(names.items()) if s != quote
        }
        self._by_id = {a.public_id: a for a in self._assets.values()}
        self._hourly: dict[str, list[Bar]] = {}
        for r in refs:
            if r.quote != quote or r.timeframe != "1h" or r.base not in self._assets:
                continue
            self._hourly.setdefault(r.base, []).append(
                Bar(r.ts_ms, r.open, r.high, r.low, r.close, r.volume)
            )
        for bars in self._hourly.values():
            bars.sort(key=lambda b: b.ts_ms)
        self._dq = dq or {}

    def list_assets(self, after: str | None, limit: int) -> list[AssetInfo]:
        items = [a for s, a in self._assets.items() if after is None or s > after]
        return items[:limit]

    def get_asset(self, public_id: UUID) -> AssetInfo | None:
        return self._by_id.get(public_id)

    def candles(
        self, public_id: UUID, timeframe: ApiTimeframe, before_ms: int | None, limit: int
    ) -> list[Bar]:
        asset = self._by_id.get(public_id)
        if asset is None:
            return []
        bars = aggregate(self._hourly.get(asset.symbol, []), timeframe)
        bars = [b for b in reversed(bars) if before_ms is None or b.ts_ms < before_ms]
        return bars[:limit]

    def overview(self) -> list[OverviewRow]:
        rows = [
            overview_row(a, self._hourly.get(s, []), self._dq.get(s, []))
            for s, a in self._assets.items()
        ]
        return [r for r in rows if r is not None]


# --- Postgres ---

_ASSETS: LiteralString = """
SELECT a.public_id, a.symbol, a.name FROM assets a
WHERE EXISTS (
    SELECT 1 FROM instruments i JOIN assets q ON q.asset_id = i.quote_asset_id
    WHERE i.base_asset_id = a.asset_id AND q.symbol = %(quote)s
)
"""

# Okresy 4 h i 1 d: date_bin z początkiem 2000-01-01 00:00 UTC (wyrównanie do północy UTC,
# jak `period_start`); bez funkcji Timescale, więc ten sam SQL działa na czystym Postgresie.
_CANDLES: LiteralString = """
SELECT date_bin(%(span)s::interval, r.ts, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS bucket,
       (array_agg(r.open ORDER BY r.ts))[1], max(r.high), min(r.low),
       (array_agg(r.close ORDER BY r.ts DESC))[1], sum(r.volume)
FROM candles_ref r
JOIN assets a ON a.asset_id = r.asset_id
JOIN assets q ON q.asset_id = r.quote_asset_id
WHERE a.public_id = %(id)s AND q.symbol = %(quote)s AND r.timeframe = '1h'
  AND (%(before)s::timestamptz IS NULL OR r.ts < %(before)s::timestamptz)
GROUP BY bucket
HAVING count(*) = %(need)s
ORDER BY bucket DESC
LIMIT %(limit)s
"""

_LAST_DAY: LiteralString = """
SELECT r.ts, r.open, r.high, r.low, r.close, r.volume
FROM candles_ref r
JOIN assets q ON q.asset_id = r.quote_asset_id
WHERE r.asset_id = (SELECT asset_id FROM assets WHERE public_id = %(id)s)
  AND q.symbol = %(quote)s AND r.timeframe = '1h'
  AND r.ts >= (
      SELECT max(x.ts) FROM candles_ref x
      WHERE x.asset_id = r.asset_id AND x.quote_asset_id = r.quote_asset_id
        AND x.timeframe = '1h'
  ) - interval '24 hours'
ORDER BY r.ts
"""

_DQ: LiteralString = """
SELECT s.status FROM dq_status s
JOIN instruments i ON i.instrument_id = s.instrument_id
JOIN assets a ON a.asset_id = i.base_asset_id
JOIN assets q ON q.asset_id = i.quote_asset_id
WHERE a.public_id = %(id)s AND q.symbol = %(quote)s AND s.dataset = %(dataset)s
"""


def _ms(value: object) -> int:
    return datetime_to_ms(cast(datetime, value))


class PostgresReader:
    """`MarketReader` w Postgresie: jedno połączenie (autocommit, tylko do odczytu).

    Konto procesu api (`goatcash_api`) ma tylko SELECT na tabelach rynkowych (konto
    `infra/compose/staging/ensure-api-role.sh`); sesja dodatkowo działa z
    `default_transaction_read_only`. Połączenie jest współdzielone przez wątki (psycopg
    szereguje zapytania) i odtwarzane po zerwaniu.
    """

    def __init__(self, connect: Callable[[], psycopg.Connection[Any]], quote: str) -> None:
        self._connect = connect
        self._quote = quote
        self._conn: psycopg.Connection[Any] | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_url(cls, url: str, quote: str) -> PostgresReader:
        dsn = url.replace("postgresql+psycopg://", "postgresql://", 1)

        def connect() -> psycopg.Connection[Any]:
            return psycopg.connect(
                dsn,
                autocommit=True,
                connect_timeout=5,
                options="-c default_transaction_read_only=on -c statement_timeout=5000",
            )

        return cls(connect, quote)

    def _rows(self, sql: LiteralString, params: dict[str, object]) -> list[tuple[Any, ...]]:
        with self._lock:
            if self._conn is None or self._conn.closed or self._conn.broken:
                self._conn = self._connect()
            conn = self._conn
        try:
            return conn.execute(sql, params).fetchall()
        except psycopg.OperationalError:
            with self._lock:
                if self._conn is conn:
                    self._conn = None
            raise

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def list_assets(self, after: str | None, limit: int) -> list[AssetInfo]:
        rows = self._rows(
            _ASSETS + " AND (%(after)s::text IS NULL OR a.symbol > %(after)s::text) "
            "ORDER BY a.symbol LIMIT %(limit)s",
            {"quote": self._quote, "after": after, "limit": limit},
        )
        return [AssetInfo(cast(UUID, r[0]), str(r[1]), str(r[2])) for r in rows]

    def get_asset(self, public_id: UUID) -> AssetInfo | None:
        rows = self._rows(
            _ASSETS + " AND a.public_id = %(id)s", {"quote": self._quote, "id": public_id}
        )
        return (
            None
            if not rows
            else AssetInfo(cast(UUID, rows[0][0]), str(rows[0][1]), str(rows[0][2]))
        )

    def candles(
        self, public_id: UUID, timeframe: ApiTimeframe, before_ms: int | None, limit: int
    ) -> list[Bar]:
        before = None if before_ms is None else ms_to_datetime(before_ms)
        rows = self._rows(
            _CANDLES,
            {
                "span": timedelta(hours=HOURS[timeframe]),
                "id": public_id,
                "quote": self._quote,
                "before": before,
                "need": HOURS[timeframe],
                "limit": limit,
            },
        )
        return [Bar(_ms(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in rows]

    def overview(self) -> list[OverviewRow]:
        result: list[OverviewRow] = []
        for asset in self.list_assets(None, 10_000):
            params: dict[str, object] = {"id": asset.public_id, "quote": self._quote}
            hourly = [
                Bar(_ms(r[0]), r[1], r[2], r[3], r[4], r[5]) for r in self._rows(_LAST_DAY, params)
            ]
            dq = [str(r[0]) for r in self._rows(_DQ, {**params, "dataset": DQ_DATASET})]
            row = overview_row(asset, hourly, dq)
            if row is not None:
                result.append(row)
        return result
