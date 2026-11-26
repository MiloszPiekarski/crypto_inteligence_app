"""Typy danych rynkowych po normalizacji (roadmapa E4, zakres 2).

Czas zawsze w UTC jako liczba milisekund od epoki (`ts_ms`, początek świecy), ceny
i wolumen jako `Decimal` utworzony z tekstu odpowiedzi giełdy (bez przejścia przez float).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

HOUR_MS = 3_600_000
Timeframe = Literal["1h"]
TIMEFRAME_MS: dict[str, int] = {"1h": HOUR_MS}


def ms_to_datetime(ts_ms: int) -> datetime:
    """Milisekundy UTC → `datetime` ze strefą UTC."""
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC)


def datetime_to_ms(value: datetime) -> int:
    """`datetime` ze strefą → milisekundy UTC (bez strefy: błąd, nie zgadujemy)."""
    if value.tzinfo is None:
        raise ValueError("datetime bez strefy czasowej")
    return int(value.timestamp() * 1000)


@dataclass(frozen=True, slots=True)
class TimeRange:
    """Przedział półotwarty [start_ms, end_ms) wyrównany do interwału świecy."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.end_ms < self.start_ms:
            raise ValueError(f"pusty przedział odwrotny: {self.start_ms} > {self.end_ms}")


@dataclass(frozen=True, slots=True)
class Candle:
    """Zamknięta świeca z jednej giełdy po normalizacji."""

    exchange: str
    symbol: str  # postać znormalizowana, np. "BTC-USDT"
    timeframe: Timeframe
    ts_ms: int  # początek świecy, UTC
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal  # w walucie bazowej


@dataclass(frozen=True, slots=True)
class InstrumentInfo:
    """Instrument spot z giełdy po normalizacji (precyzja jako krok ceny i ilości)."""

    exchange: str
    symbol: str  # "BTC-USDT"
    exchange_symbol: str  # identyfikator na giełdzie, np. "BTC-USDT" (OKX), "BTCUSDT" (Bybit)
    base: str
    quote: str
    price_tick: Decimal
    amount_step: Decimal
    active: bool
