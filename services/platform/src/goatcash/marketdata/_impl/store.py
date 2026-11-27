"""Magazyn danych rynkowych: interfejs, partia zapisu i implementacja w pamięci (testy).

Implementacja w Postgresie (`pgstore.py`) ma to samo zachowanie; test integracyjny
uruchamia ten sam scenariusz na obu i porównuje wynik.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from goatcash.marketdata._impl.dq import GAP_EXCHANGE, DqEvent
from goatcash.marketdata._impl.events import OutboxEvent
from goatcash.marketdata._impl.refprice import RefCandle
from goatcash.marketdata._impl.types import HOUR_MS, Candle, InstrumentInfo, TimeRange
from goatcash.marketdata._impl.universe import Universe

BACKFILL_JOB = "candles_1h"


@dataclass(frozen=True, slots=True)
class InstrumentStatus:
    """dq_status: ok | degraded | stale | down, kompletność i ostatnia świeca."""

    exchange: str
    symbol: str
    status: str
    completeness: float | None
    last_ts_ms: int | None


@dataclass(frozen=True, slots=True)
class Checkpoint:
    job: str
    pair: str
    cursor_ms: int  # następne okno zaczyna się tutaj (wszystko przed jest przetworzone)


@dataclass(slots=True)
class CommitBatch:
    """Wszystko z jednego okna przetwarzania; zapis atomowy (jedna transakcja)."""

    candles: list[Candle] = field(default_factory=list[Candle])
    flagged: set[tuple[str, int]] = field(default_factory=set[tuple[str, int]])
    events: list[DqEvent] = field(default_factory=list[DqEvent])
    refs: list[RefCandle] = field(default_factory=list[RefCandle])
    outbox: list[OutboxEvent] = field(default_factory=list[OutboxEvent])
    checkpoint: Checkpoint | None = None


class MarketStore(Protocol):
    def ensure_instruments(
        self, universe: Universe, infos: Sequence[InstrumentInfo]
    ) -> dict[tuple[str, str], int]:
        """Aktywa i instrumenty (idempotentnie); mapa (giełda, symbol) → instrument_id."""
        ...

    def checkpoint(self, job: str, pair: str) -> Checkpoint | None: ...

    def commit(self, batch: CommitBatch) -> None:
        """Atomowo: świece (istniejące pomijane), zdarzenia DQ, ceny ref., outbox, punkt."""
        ...

    def recent_good(self, exchange: str, symbol: str, before_ms: int, limit: int) -> list[Candle]:
        """Ostatnie nieoznaczone świece przed `before_ms`, rosnąco (rozgrzanie DQ)."""
        ...

    def good_at(self, symbol: str, ts: Iterable[int]) -> dict[int, dict[str, Candle]]:
        """Nieoznaczone świece wszystkich giełd w podanych chwilach (ts → giełda → świeca)."""
        ...

    def present_ts(self, exchange: str, symbol: str, time_range: TimeRange) -> set[int]: ...

    def first_ts(self, exchange: str, symbol: str) -> int | None: ...

    def events(self, exchange: str, symbol: str, kinds: Iterable[str]) -> list[DqEvent]: ...

    def upsert_status(self, status: InstrumentStatus) -> None:
        """Wiersz dq_status instrumentu (zbiór danych candles_1h)."""
        ...

    def missing_refs(self, symbol: str) -> int:
        """Chwile z co najmniej jedną nieoznaczoną świecą pary, a bez ceny referencyjnej."""
        ...


def exchange_gap_ts(events: Iterable[DqEvent]) -> set[int]:
    """Chwile objęte potwierdzonymi lukami po stronie giełdy (zdarzenia z `count`)."""
    covered: set[int] = set()
    for event in events:
        if event.kind != GAP_EXCHANGE:
            continue
        count = int(event.details.get("count", "1"))
        covered.update(event.ts_ms + i * HOUR_MS for i in range(count))
    return covered


class InMemoryStore:
    """`MarketStore` w pamięci: zachowanie jak w Postgresie (ON CONFLICT DO NOTHING itd.)."""

    def __init__(self) -> None:
        self.instruments: dict[tuple[str, str], int] = {}
        self.candles: dict[tuple[str, str, int], Candle] = {}
        self.flagged: set[tuple[str, str, int]] = set()
        self.dq_events: list[DqEvent] = []
        self.refs: dict[tuple[str, str, int], RefCandle] = {}
        self.outbox: list[tuple[int, OutboxEvent, datetime | None]] = []
        self.checkpoints: dict[tuple[str, str], Checkpoint] = {}
        self.statuses: dict[tuple[str, str], InstrumentStatus] = {}
        self.commits = 0

    def ensure_instruments(
        self, universe: Universe, infos: Sequence[InstrumentInfo]
    ) -> dict[tuple[str, str], int]:
        for info in infos:
            key = (info.exchange, info.symbol)
            self.instruments.setdefault(key, len(self.instruments) + 1)
        return dict(self.instruments)

    def checkpoint(self, job: str, pair: str) -> Checkpoint | None:
        return self.checkpoints.get((job, pair))

    def commit(self, batch: CommitBatch) -> None:
        for candle in batch.candles:
            key = (candle.exchange, candle.symbol, candle.ts_ms)
            if (candle.exchange, candle.ts_ms) in batch.flagged:
                self.flagged.add(key)
            self.candles.setdefault(key, candle)
        self.dq_events.extend(batch.events)
        for ref in batch.refs:
            self.refs[(ref.base, ref.quote, ref.ts_ms)] = ref
        for event in batch.outbox:
            self.outbox.append((len(self.outbox) + 1, event, None))
        if batch.checkpoint is not None:
            cp = batch.checkpoint
            self.checkpoints[(cp.job, cp.pair)] = cp
        self.commits += 1

    def _good(self, exchange: str, symbol: str) -> list[Candle]:
        return sorted(
            (
                c
                for key, c in self.candles.items()
                if key[0] == exchange and key[1] == symbol and key not in self.flagged
            ),
            key=lambda c: c.ts_ms,
        )

    def recent_good(self, exchange: str, symbol: str, before_ms: int, limit: int) -> list[Candle]:
        good = [c for c in self._good(exchange, symbol) if c.ts_ms < before_ms]
        return good[-limit:] if limit else []

    def good_at(self, symbol: str, ts: Iterable[int]) -> dict[int, dict[str, Candle]]:
        wanted = set(ts)
        result: dict[int, dict[str, Candle]] = {}
        for key, candle in self.candles.items():
            if key[1] == symbol and key[2] in wanted and key not in self.flagged:
                result.setdefault(key[2], {})[key[0]] = candle
        return result

    def present_ts(self, exchange: str, symbol: str, time_range: TimeRange) -> set[int]:
        return {
            ts
            for (ex, sym, ts) in self.candles
            if ex == exchange and sym == symbol and time_range.start_ms <= ts < time_range.end_ms
        }

    def first_ts(self, exchange: str, symbol: str) -> int | None:
        found = [ts for (ex, sym, ts) in self.candles if ex == exchange and sym == symbol]
        return min(found) if found else None

    def events(self, exchange: str, symbol: str, kinds: Iterable[str]) -> list[DqEvent]:
        wanted = set(kinds)
        return [
            e
            for e in self.dq_events
            if e.exchange == exchange and e.symbol == symbol and e.kind in wanted
        ]

    def upsert_status(self, status: InstrumentStatus) -> None:
        self.statuses[(status.exchange, status.symbol)] = status

    def missing_refs(self, symbol: str) -> int:
        base, quote = symbol.split("-")
        good = {key[2] for key in self.candles if key[1] == symbol and key not in self.flagged}
        return len({ts for ts in good if (base, quote, ts) not in self.refs})

    # OutboxStore (przekaźnik zdarzeń)
    def unpublished(
        self, limit: int, types: Sequence[str] | None = None
    ) -> list[tuple[int, OutboxEvent]]:
        return [
            (oid, ev)
            for oid, ev, pub in self.outbox
            if pub is None and (types is None or ev.type in types)
        ][:limit]

    def mark_published(self, outbox_ids: Sequence[int], published_at: datetime) -> None:
        ids = set(outbox_ids)
        self.outbox = [
            (oid, ev, published_at if oid in ids else pub) for oid, ev, pub in self.outbox
        ]
