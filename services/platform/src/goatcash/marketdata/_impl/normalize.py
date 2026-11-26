"""Normalizacja odpowiedzi giełd (roadmapa E4, zakres 2).

Wiersz świecy z giełdy (lista tekstów) → `Candle`: symbol `BAZA-KWOTOWANIE`, czas UTC
w milisekundach, ceny i wolumen jako `Decimal` z tekstu. Wartość, która nie jest tekstem
liczby dziesiętnej, jest błędem (nie zgadujemy i nie przechodzimy przez float).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

from goatcash.marketdata._impl.types import Candle, Timeframe

_DECIMAL_RE = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?")
_ASSET_RE = re.compile(r"[A-Z0-9]{1,20}")


class NormalizationError(ValueError):
    """Odpowiedź giełdy nie daje się znormalizować (zmiana formatu albo błąd danych)."""


def normalize_symbol(base: str, quote: str) -> str:
    """("btc", "usdt") → "BTC-USDT"."""
    b, q = base.upper(), quote.upper()
    if not _ASSET_RE.fullmatch(b) or not _ASSET_RE.fullmatch(q):
        raise NormalizationError(f"niepoprawny symbol aktywa: {base!r}/{quote!r}")
    return f"{b}-{q}"


def split_symbol(symbol: str) -> tuple[str, str]:
    """ "BTC-USDT" → ("BTC", "USDT")."""
    parts = symbol.split("-")
    if len(parts) != 2:  # noqa: PLR2004 (baza i kwotowanie)
        raise NormalizationError(f"symbol nie ma postaci BAZA-KWOTOWANIE: {symbol!r}")
    return parts[0], parts[1]


def parse_decimal(value: object, field: str) -> Decimal:
    """Tekst liczby dziesiętnej → `Decimal`; float, None, NaN i nieskończoność to błąd."""
    if not isinstance(value, str) or not _DECIMAL_RE.fullmatch(value):
        raise NormalizationError(f"{field}: oczekiwany tekst liczby dziesiętnej, jest {value!r}")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:  # pragma: no cover (wyklucza wyrażenie regularne)
        raise NormalizationError(f"{field}: {value!r}") from exc
    return result


def parse_ts_ms(value: object, interval_ms: int) -> int:
    """Tekst (albo liczba całkowita) milisekund UTC wyrównany do interwału."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise NormalizationError(f"ts: oczekiwane milisekundy, jest {value!r}")
    text = str(value)
    if not text.isdigit():
        raise NormalizationError(f"ts: oczekiwane milisekundy, jest {value!r}")
    ts = int(text)
    if ts % interval_ms:
        raise NormalizationError(f"ts {ts} nie jest wyrównany do interwału {interval_ms} ms")
    return ts


def candle_from_row(
    row: Sequence[object],
    *,
    exchange: str,
    symbol: str,
    timeframe: Timeframe,
    interval_ms: int,
) -> Candle:
    """[ts, open, high, low, close, volume, ...] → `Candle` (kolejność wspólna OKX i Bybit)."""
    if len(row) < 6:  # noqa: PLR2004 (ts + OHLCV)
        raise NormalizationError(f"wiersz świecy ma {len(row)} pól, oczekiwane ≥ 6")
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        ts_ms=parse_ts_ms(row[0], interval_ms),
        open=parse_decimal(row[1], "open"),
        high=parse_decimal(row[2], "high"),
        low=parse_decimal(row[3], "low"),
        close=parse_decimal(row[4], "close"),
        volume=parse_decimal(row[5], "volume"),
    )


def step_from_precision(value: object, field: str) -> Decimal:
    """Krok ceny/ilości z ccxt (tryb TICK_SIZE, liczba) → `Decimal` przez `repr` (bez szumu)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise NormalizationError(f"{field}: brak precyzji instrumentu ({value!r})")
    step = Decimal(repr(value)) if isinstance(value, float) else Decimal(str(value))
    if step <= 0:
        raise NormalizationError(f"{field}: krok musi być dodatni ({value!r})")
    return step.normalize()
