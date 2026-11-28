"""Dane syntetyczne testów API (E6): cena referencyjna 1h trzech aktywów z lukami.

- BTC: 10 pełnych dni od 2026-01-05 00:00 UTC bez luk;
- ETH: te same dni, ale bez świecy 2026-01-07 05:00 (okres 4h 04:00-08:00 i cały
  2026-01-07 niepełne) i bez ostatniej doby poza ostatnią świecą (wolumen 24 h = null);
- SOL: 30 świec, ostatnia doba niepełna;
- DOGE: aktywo bez świec (jest na liście aktywów, nie ma go w przeglądzie).
Ceny to liczby dziesiętne z 8 miejscami po przecinku (jak z giełd), deterministyczne.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

import schemathesis
from fastapi import FastAPI
from hypothesis import strategies as st
from schemathesis.specs.openapi import checks as openapi_checks

from goatcash.marketdata.api import HOUR_MS, InMemoryReader, RefCandle, asset_public_id

QUOTE = "USDT"
NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "DOGE": "Dogecoin", "USDT": "Tether"}
START_MS = int(datetime(2026, 1, 5, tzinfo=UTC).timestamp() * 1000)
DAYS = 10
ETH_MISSING_MS = int(datetime(2026, 1, 7, 5, tzinfo=UTC).timestamp() * 1000)
DQ = {"BTC": ["ok", "ok"], "ETH": ["ok", "degraded"], "SOL": ["stale", "ok"]}
Q8 = Decimal("0.00000001")


def _series(base: str, start_ms: int, hours: int, rng: random.Random) -> list[RefCandle]:
    price = Decimal(rng.randint(50, 50_000))
    out: list[RefCandle] = []
    for i in range(hours):
        o = price
        c = (o * Decimal(1 + rng.uniform(-0.02, 0.02))).quantize(Q8)
        h = (max(o, c) * Decimal(1 + rng.uniform(0, 0.01))).quantize(Q8)
        low = (min(o, c) * Decimal(1 - rng.uniform(0, 0.01))).quantize(Q8)
        v = Decimal(rng.randint(0, 10**9)) / 1000
        out.append(
            RefCandle(
                base,
                QUOTE,
                "1h",
                start_ms + i * HOUR_MS,
                o,
                h,
                low,
                c,
                v,
                ("okx", "bybit"),
                "median",
            )
        )
        price = c
    return out


def refs() -> list[RefCandle]:
    rng = random.Random(20261128)
    btc = _series("BTC", START_MS, DAYS * 24, rng)
    eth = [r for r in _series("ETH", START_MS, DAYS * 24, rng) if r.ts_ms != ETH_MISSING_MS]
    last = START_MS + (DAYS * 24 - 1) * HOUR_MS
    eth = [r for r in eth if r.ts_ms < last - 23 * HOUR_MS or r.ts_ms == last]
    sol = _series("SOL", START_MS + 5 * 24 * HOUR_MS, 30, rng)
    return btc + eth + sol


def reader() -> InMemoryReader:
    return InMemoryReader(QUOTE, NAMES, refs(), DQ)


class Failing:
    """Czytnik, którego baza nie odpowiada (albo który ma błąd w kodzie)."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def list_assets(self, after: str | None, limit: int) -> Any:
        raise self.exc

    def get_asset(self, public_id: UUID) -> Any:
        raise self.exc

    def candles(self, public_id: UUID, timeframe: Any, before_ms: int | None, limit: int) -> Any:
        raise self.exc

    def overview(self) -> Any:
        raise self.exc


# Endpointy E7 i E9 celowo zwracają 501 do swoich etapów (test_http_api.py), więc
# Schemathesis ich nie sprawdza (każdy 5xx byłby błędem).
POSITIVE_DATA_ACCEPTANCE = cast(Any, openapi_checks.positive_data_acceptance)  # pyright: ignore[reportUnknownMemberType]
LATER_STAGES = {"listEvidence", "getAssessment", "listAgents"}
KNOWN_ASSETS = [str(asset_public_id(s)) for s in sorted(NAMES) if s != QUOTE]


def conformance_schema(app: FastAPI) -> Any:
    """Specyfikacja aplikacji dla Schemathesis, bez endpointów E7 i E9.

    Losowy UUID prawie zawsze daje 404, więc bez haka kod za sprawdzeniem aktywa (świece
    z interwałem, limitem i kursorem) byłby prawie nietestowany: połowa przypadków dostaje
    identyfikator istniejącego aktywa (także DOGE bez świec), reszta zostaje losowa.
    """
    loaded: Any = schemathesis.openapi.from_asgi("/openapi.json", app)
    schema: Any = loaded.exclude(operation_id=sorted(LATER_STAGES))

    @schema.hook
    def before_generate_path_parameters(_: Any, strategy: st.SearchStrategy[Any]) -> Any:  # pyright: ignore[reportUnusedFunction]
        return st.one_of(strategy, st.sampled_from(KNOWN_ASSETS).map(lambda i: {"asset_id": i}))

    return schema


def validate(case: Any) -> None:
    """Wszystkie sprawdzenia Schemathesis; jeden wyjątek: nieprzezroczysty kursor.

    Kursor (opis parametru w specyfikacji) to tylko `next_cursor` wydany przez serwer; inny
    tekst jest odrzucany jako 400 w formacie RFC 9457, choć pasuje do typu `string`. Wtedy
    wyłączamy tylko sprawdzenie „poprawne dane przyjęte” (pozostałe działają, a treść
    błędu musi być błędem kursora).
    """
    response = case.call()
    excluded: list[Any] = []
    if response.status_code == 400 and "cursor" in (case.query or {}):
        assert response.json()["detail"] == "Niepoprawny kursor paginacji."
        excluded = [POSITIVE_DATA_ACCEPTANCE]
    case.validate_response(response, excluded_checks=excluded)
