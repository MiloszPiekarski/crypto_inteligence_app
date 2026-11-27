"""Pobieranie świec: uzupełnianie historii z punktami kontrolnymi, luki i raport danych.

Roadmapa E4, punkty 4, 5 i 9 ścieżki pracy. Jedna ścieżka kodu dla historii i pracy
bieżącej: `backfill_pair` przetwarza okna od punktu kontrolnego do ostatniej zamkniętej
świecy, więc uruchomione co godzinę po prostu dopisuje nowe świece.

Okno = świece obu giełd z przedziału → kontrola jakości → cena referencyjna → jeden
zapis atomowy razem z punktem kontrolnym. Przerwanie (wyjątek, restart procesu) w środku
okna nie zostawia połowy zapisu, a kolejne uruchomienie zaczyna od tego samego okna.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from goatcash.marketdata._impl.dq import (
    GAP_EXCHANGE,
    GAP_OURS,
    DqConfig,
    DqEvent,
    PairDq,
    is_stale,
)
from goatcash.marketdata._impl.events import OutboxEvent, candle_closed
from goatcash.marketdata._impl.gaps import ClassifiedGap, classify_gap, completeness, find_gaps
from goatcash.marketdata._impl.refprice import reference_candles
from goatcash.marketdata._impl.sources import MarketDataSource
from goatcash.marketdata._impl.store import (
    BACKFILL_JOB,
    Checkpoint,
    CommitBatch,
    MarketStore,
    exchange_gap_ts,
)
from goatcash.marketdata._impl.types import HOUR_MS, Candle, TimeRange, ms_to_datetime
from goatcash.marketdata._impl.universe import Universe

# Okno przetwarzania: 1000 świec 1 h (OKX: 10 zapytań po 100, Bybit: 1 zapytanie).
WINDOW_MS = 1000 * HOUR_MS
# candle.closed tylko dla świec z ostatniej doby: zdarzenie oznacza nową świecę dla
# konsumentów bieżących (E5+); historię czytają oni z bazy (ADR-0003: historia w Postgresie).
LIVE_WINDOW_MS = 24 * HOUR_MS


def last_closed_end(now_ms: int) -> int:
    """Koniec (wyłączny) przedziału świec 1 h zamkniętych w chwili `now_ms`."""
    return (now_ms // HOUR_MS) * HOUR_MS


@dataclass(slots=True)
class Ingest:
    store: MarketStore
    sources: Mapping[str, MarketDataSource]
    universe: Universe
    producer: str
    now_ms: Callable[[], int] = field(default=lambda: int(time.time() * 1000))
    dq_config: DqConfig = field(default_factory=DqConfig)
    window_ms: int = WINDOW_MS
    instrument_ids: dict[tuple[str, str], int] = field(default_factory=dict[tuple[str, str], int])

    @property
    def exchanges(self) -> tuple[str, ...]:
        return self.universe.exchanges

    def setup_instruments(self) -> dict[tuple[str, str], int]:
        """Instrumenty z giełd (precyzja) zapisane w bazie; para musi być na obu giełdach."""
        infos = [
            i for ex in self.exchanges for i in self.sources[ex].instruments(self.universe.symbols)
        ]
        for symbol in self.universe.symbols:
            missing = [
                ex
                for ex in self.exchanges
                if (ex, symbol) not in {(i.exchange, i.symbol) for i in infos}
            ]
            if missing:
                raise RuntimeError(f"para {symbol} niedostępna na: {', '.join(missing)}")
        self.instrument_ids = self.store.ensure_instruments(self.universe, infos)
        return self.instrument_ids

    def _outbox(self, candles: Sequence[Candle], now: int) -> list[OutboxEvent]:
        return [
            candle_closed(
                c,
                self.instrument_ids[(c.exchange, c.symbol)],
                source=f"{c.exchange}-rest",
                now_ms=now,
            )
            for c in candles
            if c.ts_ms >= now - LIVE_WINDOW_MS
        ]

    def _dq(self, symbol: str, before_ms: int) -> PairDq:
        dq = PairDq(self.exchanges, self.dq_config)
        for ex in self.exchanges:
            dq.warm_up(ex, self.store.recent_good(ex, symbol, before_ms, self.dq_config.window + 1))
        return dq

    def backfill_pair(self, symbol: str) -> int:
        """Od punktu kontrolnego do ostatniej zamkniętej świecy; zwraca liczbę zapisanych."""
        now = self.now_ms()
        end = last_closed_end(now)
        cp = self.store.checkpoint(BACKFILL_JOB, symbol)
        cursor = cp.cursor_ms if cp else self.universe.start_ms
        dq = self._dq(symbol, cursor)
        written = 0
        while cursor < end:
            window = TimeRange(cursor, min(cursor + self.window_ms, end))
            fetched = [
                c
                for ex in self.exchanges
                for c in self.sources[ex].candles(symbol, self.universe.timeframe, window)
            ]
            result = dq.process(fetched)
            self.store.commit(
                CommitBatch(
                    candles=result.accepted,
                    flagged=result.flagged,
                    events=result.events,
                    refs=reference_candles(result.good()),
                    outbox=self._outbox(result.accepted, now),
                    checkpoint=Checkpoint(BACKFILL_JOB, symbol, window.end_ms),
                )
            )
            written += len(result.accepted)
            cursor = window.end_ms
        return written

    def repair_gaps(self, symbol: str, exchange: str) -> list[ClassifiedGap]:
        """Wykrywa luki od pierwszej świecy do punktu kontrolnego, klasyfikuje i uzupełnia.

        Luki już potwierdzone po stronie giełdy nie są ponownie odpytywane.
        """
        cp = self.store.checkpoint(BACKFILL_JOB, symbol)
        first = self.store.first_ts(exchange, symbol)
        if cp is None or first is None:
            return []
        span = TimeRange(first, cp.cursor_ms)
        known = exchange_gap_ts(self.store.events(exchange, symbol, [GAP_EXCHANGE]))
        present = self.store.present_ts(exchange, symbol, span) | known
        source = self.sources[exchange]
        parts: list[ClassifiedGap] = []
        for gap in find_gaps(present, span, HOUR_MS):
            for part in classify_gap(
                gap, lambda r: source.candles(symbol, self.universe.timeframe, r), HOUR_MS
            ):
                self._commit_gap_part(symbol, exchange, part)
                parts.append(part)
        return parts

    def _commit_gap_part(self, symbol: str, exchange: str, part: ClassifiedGap) -> None:
        count = (part.end_ms - part.start_ms) // HOUR_MS
        details = {
            "end": ms_to_datetime(part.end_ms).isoformat(),
            "count": str(count),
        }
        if part.kind == "exchange":
            event = DqEvent(exchange, symbol, part.start_ms, GAP_EXCHANGE, "flagged", details)
            self.store.commit(CommitBatch(events=[event]))
            return
        ts_list = [c.ts_ms for c in part.candles]
        context = self.store.good_at(symbol, ts_list)
        dq = self._dq(symbol, part.start_ms)
        result = dq.process(part.candles, context)
        good = result.good() + [c for by_ex in context.values() for c in by_ex.values()]
        repaired = DqEvent(
            exchange,
            symbol,
            part.start_ms,
            GAP_OURS,
            "repaired",
            {**details, "stored": str(len(result.accepted))},
        )
        self.store.commit(
            CommitBatch(
                candles=result.accepted,
                flagged=result.flagged,
                events=[*result.events, repaired],
                refs=reference_candles(good),
                outbox=self._outbox(result.accepted, self.now_ms()),
            )
        )


@dataclass(frozen=True, slots=True)
class InstrumentReport:
    """Kompletność i luki jednego instrumentu (giełda, para) do raportu danych G4p."""

    exchange: str
    symbol: str
    first_ts_ms: int | None
    end_ms: int
    expected: int
    stored: int
    exchange_missing: int
    unexplained: tuple[int, ...]  # brakujące świece bez klasyfikacji (kryterium: 0)
    rejected: int  # brakujące, bo giełda dała błędną świecę (odrzucona przez DQ)
    completeness: float
    stale: bool
    last_ts_ms: int | None = None  # ostatnia zapisana świeca


REJECT_KINDS = ("nonpositive_price", "ohlc_inconsistent", "negative_volume")


def instrument_report(
    store: MarketStore, exchange: str, symbol: str, now_ms: int
) -> InstrumentReport:
    """Raport: oczekiwane od pierwszej świecy udostępnionej przez giełdę do punktu kontrolnego.

    Każda brakująca świeca musi być opisana: luka po stronie giełdy (potwierdzona ponownym
    zapytaniem) albo świeca odrzucona przez DQ; reszta to `unexplained`.
    """
    cp = store.checkpoint(BACKFILL_JOB, symbol)
    first = store.first_ts(exchange, symbol)
    end = cp.cursor_ms if cp else 0
    if first is None or cp is None:
        return InstrumentReport(exchange, symbol, None, end, 0, 0, 0, (), 0, 0.0, True)
    span = TimeRange(first, end)
    expected = range(first, end, HOUR_MS)
    present = store.present_ts(exchange, symbol, span)
    # Świeca z luki giełdy, która później się pojawiła, liczy się jako zapisana, nie brakująca.
    gap_ts = (
        exchange_gap_ts(store.events(exchange, symbol, [GAP_EXCHANGE])) & set(expected)
    ) - present
    rejected_ts = {
        e.ts_ms for e in store.events(exchange, symbol, REJECT_KINDS) if e.ts_ms not in present
    }
    missing = set(expected) - present
    unexplained = tuple(sorted(missing - gap_ts - rejected_ts))
    stored = len(present)
    return InstrumentReport(
        exchange=exchange,
        symbol=symbol,
        first_ts_ms=first,
        end_ms=end,
        expected=len(expected),
        stored=stored,
        exchange_missing=len(gap_ts),
        unexplained=unexplained,
        rejected=len(rejected_ts & missing),
        completeness=completeness(len(expected), stored, len(gap_ts)),
        stale=is_stale(max(present) if present else None, now_ms),
        last_ts_ms=max(present) if present else None,
    )
