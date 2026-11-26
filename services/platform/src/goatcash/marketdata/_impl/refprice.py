"""Cena referencyjna aktywa (`candles_ref`): roadmapa E4, punkt 7 ścieżki pracy.

Dla każdej chwili t: mediana każdego pola OHLCV ze świec giełd, które przeszły kontrolę
jakości bez oznaczenia. Przy dwóch źródłach mediana to średnia; przy jednym poprawnym
źródle cena referencyjna to jego świeca z adnotacją (`source = "single"`, lista `sources`
z jedną giełdą). Bez poprawnego źródła ceny referencyjnej dla t nie ma (luka widoczna dla
E5 jako brak danych, a nie cena z błędnej świecy).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal

from goatcash.marketdata._impl.normalize import split_symbol
from goatcash.marketdata._impl.types import Candle, Timeframe

RefSource = Literal["median", "single"]


@dataclass(frozen=True, slots=True)
class RefCandle:
    """Wiersz candles_ref."""

    base: str
    quote: str
    timeframe: Timeframe
    ts_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    sources: tuple[str, ...]
    source: RefSource


def median(values: list[Decimal]) -> Decimal:
    """Mediana w arytmetyce dziesiętnej (bez zaokrągleń: precyzja kontekstu 60 cyfr)."""
    if not values:
        raise ValueError("mediana pustej listy")
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    with localcontext() as ctx:
        ctx.prec = 60
        return (ordered[mid - 1] + ordered[mid]) / 2


def reference_candles(good: Iterable[Candle]) -> list[RefCandle]:
    """Ceny referencyjne z poprawnych świec (wiele par i chwil naraz), rosnąco po (para, t)."""
    groups: dict[tuple[str, str, int], list[Candle]] = {}
    for candle in good:
        groups.setdefault((candle.symbol, candle.timeframe, candle.ts_ms), []).append(candle)
    result: list[RefCandle] = []
    for (symbol, _timeframe, ts), candles in sorted(groups.items()):
        exchanges = [c.exchange for c in candles]
        if len(set(exchanges)) != len(exchanges):
            raise ValueError(f"dwie świece tej samej giełdy dla {symbol} {ts}: {exchanges}")
        base, quote = split_symbol(symbol)
        result.append(
            RefCandle(
                base=base,
                quote=quote,
                timeframe=candles[0].timeframe,
                ts_ms=ts,
                open=median([c.open for c in candles]),
                high=median([c.high for c in candles]),
                low=median([c.low for c in candles]),
                close=median([c.close for c in candles]),
                volume=median([c.volume for c in candles]),
                sources=tuple(sorted(exchanges)),
                source="median" if len(candles) > 1 else "single",
            )
        )
    return result
