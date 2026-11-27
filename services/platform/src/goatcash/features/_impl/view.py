"""`MarketView(as_of, known_at)`: jedyny dostęp cech (i od E7 agentów) do danych rynkowych.

Roadmapa E5, zakres 1, z doprecyzowaniem z 27.11.2026 (decyzja właściciela, karta E5
i `docs/praca/metody.md`):

- zawsze: tylko świece zamknięte najpóźniej w chwili `as_of` (`ts + 1 h ≤ as_of`; dla
  `as_of` wyrównanego do godziny to dokładnie `ts < as_of` z roadmapy);
- `known_at` (replay okresu zbieranego na żywo): dodatkowo tylko wiersze zapisane
  najpóźniej w chwili `known_at` (`ingested_at ≤ known_at`). Bez `known_at` (pełne
  przeliczenie historii) warunku na `ingested_at` nie ma: historię od 2023 r. pobrano
  w listopadzie 2026 r., więc warunek `ingested_at ≤ as_of` dawałby pusty widok.

Widok sprawdza dane ze źródła drugi raz: źródło, które zwróci wiersz spoza widoku, to błąd
(`LookAheadError`), a nie cicho odfiltrowany wiersz.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Protocol

import polars as pl

from goatcash.features._impl.types import HOUR_MS, Pair, RefBar, floor_hour
from goatcash.marketdata.api import RefCandle

BAR_SCHEMA: dict[str, type[pl.DataType]] = {
    "ts": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
}


class LookAheadError(RuntimeError):
    """Źródło zwróciło dane spoza widoku (z przyszłości względem `as_of` albo `known_at`)."""


class RefCandleSource(Protocol):
    def ref_bars(
        self, pair: Pair, *, close_until_ms: int, known_at_ms: int | None
    ) -> Sequence[RefBar]:
        """Świece 1 h pary z `ts + 1 h ≤ close_until_ms` (i `ingested_at ≤ known_at_ms`)."""
        ...

    def pairs(self) -> Sequence[Pair]:
        """Pary, dla których źródło ma dane."""
        ...


class InMemoryRefSource:
    """`RefCandleSource` w pamięci (testy i przeliczenia bez bazy)."""

    def __init__(self, bars: Mapping[Pair, Iterable[RefBar]]) -> None:
        self._bars: dict[Pair, list[RefBar]] = {}
        for pair, items in bars.items():
            ordered = sorted(items, key=lambda b: b.ts_ms)
            ts = [b.ts_ms for b in ordered]
            if len(set(ts)) != len(ts):
                raise ValueError(f"powtórzona świeca w {pair}")
            if any(t % HOUR_MS for t in ts):
                raise ValueError(f"świeca niewyrównana do godziny w {pair}")
            self._bars[pair] = ordered

    @classmethod
    def from_ref_candles(
        cls, refs: Iterable[RefCandle], *, ingested_at_ms: Mapping[tuple[str, str, int], int]
    ) -> InMemoryRefSource:
        """Ze świec `marketdata` (Decimal → float z poprawnym zaokrągleniem)."""
        grouped: dict[Pair, list[RefBar]] = {}
        for ref in refs:
            if ref.timeframe != "1h":
                raise ValueError(f"cechy fs-1p liczymy ze świec 1h, jest {ref.timeframe}")
            grouped.setdefault(Pair(ref.base, ref.quote), []).append(
                RefBar(
                    ts_ms=ref.ts_ms,
                    open=float(ref.open),
                    high=float(ref.high),
                    low=float(ref.low),
                    close=float(ref.close),
                    volume=float(ref.volume),
                    ingested_at_ms=ingested_at_ms[(ref.base, ref.quote, ref.ts_ms)],
                )
            )
        return cls(grouped)

    def pairs(self) -> Sequence[Pair]:
        return sorted(self._bars)

    def ref_bars(
        self, pair: Pair, *, close_until_ms: int, known_at_ms: int | None
    ) -> Sequence[RefBar]:
        return [
            b
            for b in self._bars.get(pair, [])
            if b.ts_ms + HOUR_MS <= close_until_ms
            and (known_at_ms is None or b.ingested_at_ms <= known_at_ms)
        ]


def _to_ms(value: datetime | int) -> int:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime bez strefy czasowej")
        return round(value.timestamp() * 1000)
    return value


class MarketView:
    """Dane rynkowe znane w chwili `as_of` (i, w replay, zapisane do chwili `known_at`)."""

    def __init__(
        self,
        source: RefCandleSource,
        as_of: datetime | int,
        known_at: datetime | int | None = None,
    ) -> None:
        self._source = source
        self.as_of_ms = _to_ms(as_of)
        self.known_at_ms = None if known_at is None else _to_ms(known_at)

    @property
    def last_bar_ts_ms(self) -> int:
        """Początek ostatniej godziny zamkniętej najpóźniej w `as_of`."""
        return floor_hour(self.as_of_ms) - HOUR_MS

    def bars(self, pair: Pair) -> pl.DataFrame:
        """Świece pary w widoku, rosnąco po czasie (kolumny `BAR_SCHEMA`)."""
        rows = self._source.ref_bars(
            pair, close_until_ms=self.as_of_ms, known_at_ms=self.known_at_ms
        )
        for b in rows:
            if b.ts_ms + HOUR_MS > self.as_of_ms:
                raise LookAheadError(f"{pair}: świeca {b.ts_ms} zamknięta po as_of")
            if self.known_at_ms is not None and b.ingested_at_ms > self.known_at_ms:
                raise LookAheadError(f"{pair}: świeca {b.ts_ms} zapisana po known_at")
        ordered = sorted(rows, key=lambda b: b.ts_ms)
        return pl.DataFrame(
            {
                "ts": [b.ts_ms for b in ordered],
                "open": [b.open for b in ordered],
                "high": [b.high for b in ordered],
                "low": [b.low for b in ordered],
                "close": [b.close for b in ordered],
                "volume": [b.volume for b in ordered],
            },
            schema=BAR_SCHEMA,
        )
