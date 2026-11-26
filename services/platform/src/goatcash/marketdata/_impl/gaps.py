"""Detektor luk w świecach (roadmapa E4, punkt 5 ścieżki pracy).

Oczekiwane świece to każdy pełny interwał w przedziale [od, do); luka to ciąg kolejnych
brakujących świec. Każdą lukę klasyfikujemy ponownym zapytaniem do giełdy:

- „nasza” (`ours`): giełda zwraca świecę, której nie mamy, więc ją uzupełniamy;
- „po stronie giełdy” (`exchange`): giełda nie udostępnia świecy także przy ponownym
  zapytaniu (np. przerwa techniczna giełdy).

Kompletność liczymy względem świec, które giełda faktycznie udostępnia:
zapisane / (oczekiwane - luki po stronie giełdy) (kryterium G4p, ADR-0008).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from goatcash.marketdata._impl.types import Candle, TimeRange

GapKind = Literal["exchange", "ours"]


@dataclass(frozen=True, slots=True)
class Gap:
    """Ciąg kolejnych brakujących świec: [start_ms, end_ms)."""

    start_ms: int
    end_ms: int

    def count(self, interval_ms: int) -> int:
        return (self.end_ms - self.start_ms) // interval_ms


@dataclass(frozen=True, slots=True)
class ClassifiedGap:
    """Fragment luki z klasyfikacją; dla `ours` także uzupełnione świece."""

    start_ms: int
    end_ms: int
    kind: GapKind
    candles: tuple[Candle, ...] = ()


def expected_ts(time_range: TimeRange, interval_ms: int) -> range:
    """Początki wszystkich świec w [start, end) (start wyrównany w górę do interwału)."""
    first = -(-time_range.start_ms // interval_ms) * interval_ms
    return range(first, time_range.end_ms, interval_ms)


def find_gaps(present: Iterable[int], time_range: TimeRange, interval_ms: int) -> list[Gap]:
    """Luki: ciągi oczekiwanych świec, których nie ma w `present`."""
    have = set(present)
    gaps: list[Gap] = []
    start: int | None = None
    previous = 0
    for ts in expected_ts(time_range, interval_ms):
        if ts in have:
            if start is not None:
                gaps.append(Gap(start, previous + interval_ms))
                start = None
            continue
        if start is None:
            start = ts
        previous = ts
    if start is not None:
        gaps.append(Gap(start, previous + interval_ms))
    return gaps


def classify_gap(
    gap: Gap,
    refetch: Callable[[TimeRange], Sequence[Candle]],
    interval_ms: int,
) -> list[ClassifiedGap]:
    """Dzieli lukę na fragmenty „nasza” (giełda ma świece) i „po stronie giełdy”."""
    returned = {c.ts_ms: c for c in refetch(TimeRange(gap.start_ms, gap.end_ms))}
    parts: list[ClassifiedGap] = []
    run_kind: GapKind | None = None
    run_start = gap.start_ms
    run: list[Candle] = []
    for ts in range(gap.start_ms, gap.end_ms, interval_ms):
        kind: GapKind = "ours" if ts in returned else "exchange"
        if kind != run_kind:
            if run_kind is not None:
                parts.append(ClassifiedGap(run_start, ts, run_kind, tuple(run)))
            run_kind, run_start, run = kind, ts, []
        if kind == "ours":
            run.append(returned[ts])
    if run_kind is not None:
        parts.append(ClassifiedGap(run_start, gap.end_ms, run_kind, tuple(run)))
    return parts


def completeness(expected: int, stored: int, exchange_missing: int) -> float:
    """Zapisane / (oczekiwane - brakujące po stronie giełdy); brak oczekiwanych = 1.0."""
    available = expected - exchange_missing
    if available < 0 or stored > available:
        raise ValueError(f"niespójne liczby: {expected=} {stored=} {exchange_missing=}")
    return 1.0 if available == 0 else stored / available
