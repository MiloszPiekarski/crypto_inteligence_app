"""Typy modułu features (roadmapa E5, ścieżka pracy: ADR-0008, bramka G5p).

Czas jak w `marketdata`: liczba milisekund UTC od epoki. Świeca `ts_ms` to początek
godziny; świeca jest zamknięta (dostępna) w chwili `ts_ms + 1 h`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from goatcash.marketdata.api import HOUR_MS

__all__ = ["HOUR_MS", "FeatureStatus", "FeatureVector", "Pair", "RefBar", "floor_hour"]

# Status wartości cechy (roadmapa E5, zakres 5 ścieżki pracy: brak danych = NaN + status):
# - ok: wartość policzona z pełnego okna danych;
# - warmup: za mało historii od początku danych pary (okres rozgrzewki);
# - missing_data: luka w danych w oknie cechy albo brak świecy w tej godzinie (nigdy cicha
#   interpolacja: po luce cecha czeka na pełne okno nowych danych);
# - not_applicable: cecha nie dotyczy pary (korelacja BTC z samym BTC, decyzja 27.11.2026);
# - undefined: wzór nie ma wartości (dzielenie przez zero: brak zmienności w oknie).
FeatureStatus = Literal["ok", "warmup", "missing_data", "not_applicable", "undefined"]
STATUSES: tuple[FeatureStatus, ...] = (
    "ok",
    "warmup",
    "missing_data",
    "not_applicable",
    "undefined",
)


def floor_hour(ts_ms: int) -> int:
    """Początek godziny zawierającej `ts_ms`."""
    return ts_ms - ts_ms % HOUR_MS


@dataclass(frozen=True, slots=True, order=True)
class Pair:
    """Para aktywów ceny referencyjnej (`candles_ref`: asset i kwotowanie, bez giełdy)."""

    base: str
    quote: str

    def __str__(self) -> str:
        return f"{self.base}/{self.quote}"


@dataclass(frozen=True, slots=True)
class RefBar:
    """Świeca 1 h ceny referencyjnej (wiersz `candles_ref`) z chwilą zapisu (`ingested_at`)."""

    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    ingested_at_ms: int


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """Cechy jednej pary w chwili `as_of` (wartość NaN, gdy status inny niż `ok`)."""

    pair: Pair
    as_of_ms: int
    data_cutoff_ms: int | None  # zamknięcie ostatniej użytej świecy; None: brak danych
    values: dict[str, float]
    statuses: dict[str, FeatureStatus]
