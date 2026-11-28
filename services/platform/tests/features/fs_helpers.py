# ccxt nie ma plików typów (jak w marketdata/sources.py).
# pyright: reportMissingTypeStubs=false
"""Wspólne narzędzia testów features: dane syntetyczne, prawdziwe serie z kaset E4, porównania."""

from __future__ import annotations

import math
import random
import struct
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import ccxt

from goatcash.features.api import FEATURE_NAMES, FeatureVector, InMemoryRefSource, Pair, RefBar
from goatcash.marketdata._impl.cassette import Cassette, ReplaySession
from goatcash.marketdata._impl.record import SERIES_PAIRS, series_window
from goatcash.marketdata._impl.sources import SOURCES, RetryPolicy
from goatcash.marketdata.api import HOUR_MS, Candle, RefCandle, reference_candles

H = HOUR_MS
T0 = 1_704_067_200_000  # 2024-01-01T00:00:00Z
MD_FIXTURES = Path(__file__).resolve().parents[1] / "marketdata" / "fixtures"
BTC = Pair("BTC", "USDT")
ETH = Pair("ETH", "USDT")
SOL = Pair("SOL", "USDT")

# Tolerancja wartości referencyjnych dokładnie jak w kryterium G5p (testy.md 3a): różnica
# bezwzględna < 1e-9, dla każdej cechy (także RSI i ADX w skali 0..100). Audyt E5
# (28.11.2026): wcześniejszy próg 1e-9 · max(1, |wzorzec|) przepuszczał odchylenie RSI
# o 1,5e-8. Zmierzone różnice wobec TA-Lib i czystego Pythona: ok. 1e-13..2e-12.
TOLERANCE = 1e-9


def close_enough(ours: float, ref: float) -> bool:
    return abs(ours - ref) < TOLERANCE


def bits(x: float) -> bytes:
    return struct.pack("<d", x)


def gbm_bars(  # noqa: PLR0913 (parametry serii testowej)
    n: int,
    *,
    seed: int,
    start_ms: int = T0,
    price: float = 100.0,
    sigma: float = 0.01,
    drift: float = 0.0,
    ingest_delay_ms: int = 60_000,
) -> list[RefBar]:
    """Losowa seria świec (ruch Browna geometryczny), poprawne OHLC, zapis po zamknięciu."""
    rng = random.Random(seed)
    bars: list[RefBar] = []
    close = price
    for i in range(n):
        open_ = close
        close = open_ * math.exp(rng.gauss(drift, sigma))
        high = max(open_, close) * (1 + abs(rng.gauss(0, sigma / 3)))
        low = min(open_, close) * (1 - abs(rng.gauss(0, sigma / 3)))
        ts = start_ms + i * H
        bars.append(
            RefBar(
                ts_ms=ts,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=rng.uniform(10, 1000),
                ingested_at_ms=ts + H + ingest_delay_ms,
            )
        )
    return bars


def drop_hours(bars: Iterable[RefBar], hours: Iterable[int], start_ms: int = T0) -> list[RefBar]:
    """Seria z lukami: usuwa świece o podanych numerach godzin od `start_ms`."""
    gone = {start_ms + h * H for h in hours}
    return [b for b in bars if b.ts_ms not in gone]


def source(bars: Mapping[Pair, Sequence[RefBar]]) -> InMemoryRefSource:
    return InMemoryRefSource(bars)


def _replay(exchange: str, name: str) -> Any:
    cassettes = [
        Cassette.load(MD_FIXTURES / exchange / "instruments.json"),
        Cassette.load(MD_FIXTURES / exchange / f"{name}.json"),
    ]
    client = cast(
        ccxt.Exchange,
        getattr(ccxt, exchange)(
            {"enableRateLimit": False, "options": {"fetchMarkets": {"types": ["spot"]}}}
        ),
    )
    cast(Any, client).session = ReplaySession(cassettes, None)
    recorded = max(
        int(datetime.fromisoformat(c.recorded_at.replace("Z", "+00:00")).timestamp() * 1000)
        for c in cassettes
    )
    return SOURCES[exchange](
        client, retry=RetryPolicy(sleep=lambda _: None), now_ms=lambda: recorded
    )


def real_series_refs() -> list[RefCandle]:
    """Cena referencyjna (mediana OKX i Bybit, kod E4) z nagranych serii 2000 h z E4."""
    candles: list[Candle] = []
    for exchange in ("okx", "bybit"):
        for symbol in SERIES_PAIRS:
            src = _replay(exchange, f"series_{symbol}")
            candles.extend(src.candles(symbol, "1h", series_window()))
    return reference_candles(candles)


def real_series_source() -> InMemoryRefSource:
    """Cena referencyjna (mediana OKX i Bybit, kod E4) z nagranych serii 2000 h z E4.

    Prawdziwe dane: 5 par (BTC, ETH, SOL, DOGE, APT) od 2024-07-01, z ewentualnymi lukami
    po stronie giełdy. Zapis (`ingested_at`) godzinę po zamknięciu świecy.
    """
    refs = real_series_refs()
    ingested = {(r.base, r.quote, r.ts_ms): r.ts_ms + 2 * H for r in refs}
    return InMemoryRefSource.from_ref_candles(refs, ingested_at_ms=ingested)


def vector_mismatches(a: FeatureVector, b: FeatureVector) -> list[str]:
    """Cechy, których wartość (bit w bit) albo status się różnią."""
    return [
        name
        for name in FEATURE_NAMES
        if bits(a.values[name]) != bits(b.values[name]) or a.statuses[name] != b.statuses[name]
    ]
