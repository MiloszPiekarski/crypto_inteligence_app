# ccxt nie ma plików typów (jak w sources.py).
# pyright: reportMissingTypeStubs=false
"""Wspólne narzędzia testów marketdata: kasety, źródła z odtworzeniem, syntetyczne serie."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import ccxt

from goatcash.marketdata._impl.cassette import Cassette, Interaction, ReplaySession
from goatcash.marketdata._impl.sources import SOURCES, RetryPolicy
from goatcash.marketdata._impl.types import HOUR_MS, Candle, InstrumentInfo, Timeframe, TimeRange
from goatcash.marketdata.api import MarketDataSource, SourceUnavailableError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXCHANGES = ("okx", "bybit")
T0 = 1_704_067_200_000  # 2024-01-01T00:00:00Z


def recorded_exchanges() -> list[str]:
    """Giełdy z nagranymi kasetami (Bybit: nagranie z serwera w Amsterdamie, PR 2 E4)."""
    return [ex for ex in EXCHANGES if (FIXTURES / ex / "instruments.json").exists()]


def cassette(exchange: str, name: str) -> Cassette:
    return Cassette.load(FIXTURES / exchange / f"{name}.json")


def recorded_ms(c: Cassette) -> int:
    return int(datetime.fromisoformat(c.recorded_at.replace("Z", "+00:00")).timestamp() * 1000)


def replay_source(
    exchange: str,
    names: Sequence[str],
    *,
    override: Callable[[str, str, int], Interaction | None] | None = None,
    retry: RetryPolicy | None = None,
) -> tuple[Any, ReplaySession]:
    """Prawdziwy adapter ccxt z sesją odtwarzającą kasety (bez sieci i bez limitu tempa)."""
    cassettes = [cassette(exchange, "instruments"), *(cassette(exchange, n) for n in names)]
    session = ReplaySession(cassettes, override)
    client = cast(
        ccxt.Exchange,
        getattr(ccxt, exchange)(
            {"enableRateLimit": False, "options": {"fetchMarkets": {"types": ["spot"]}}}
        ),
    )
    cast(Any, client).session = session
    now = max(recorded_ms(c) for c in cassettes)
    source = SOURCES[exchange](
        client, retry=retry or RetryPolicy(sleep=lambda _: None), now_ms=lambda: now
    )
    return source, session


def candle(  # noqa: PLR0913 (pola świecy testowej)
    ts: int,
    close: str | Decimal,
    *,
    exchange: str = "okx",
    symbol: str = "BTC-USDT",
    spread: str = "0.001",
    volume: str = "10",
) -> Candle:
    c = Decimal(close)
    s = Decimal(spread)
    return Candle(
        exchange=exchange,
        symbol=symbol,
        timeframe="1h",
        ts_ms=ts,
        open=c,
        high=c * (1 + s),
        low=c * (1 - s),
        close=c,
        volume=Decimal(volume),
    )


def gbm_series(  # noqa: PLR0913 (parametry serii testowej)
    n: int,
    *,
    seed: int,
    start: float = 50_000.0,
    sigma: float = 0.006,
    t0: int = T0,
    exchange: str = "okx",
    symbol: str = "BTC-USDT",
) -> list[Candle]:
    """Seria świec z geometrycznego ruchu Browna (stopy N(0, sigma)), spójne OHLC."""
    rng = random.Random(seed)
    price = start
    out: list[Candle] = []
    for i in range(n):
        opened = price
        price *= math.exp(rng.gauss(0.0, sigma))
        hi = max(opened, price) * (1 + abs(rng.gauss(0, sigma / 3)))
        lo = min(opened, price) * (1 - abs(rng.gauss(0, sigma / 3)))
        out.append(
            Candle(
                exchange=exchange,
                symbol=symbol,
                timeframe="1h",
                ts_ms=t0 + i * HOUR_MS,
                open=Decimal(f"{opened:.2f}"),
                high=Decimal(f"{hi:.2f}"),
                low=Decimal(f"{lo:.2f}"),
                close=Decimal(f"{price:.2f}"),
                volume=Decimal(f"{rng.uniform(1, 100):.4f}"),
            )
        )
    return [_fix_ohlc(c) for c in out]


def _fix_ohlc(c: Candle) -> Candle:
    """Zaokrąglenie do 2 miejsc mogło naruszyć spójność OHLC: korekta high/low."""
    return replace(c, high=max(c.high, c.open, c.close), low=min(c.low, c.open, c.close))


def mirror(
    series: Iterable[Candle], *, exchange: str, seed: int, noise: float = 0.0005
) -> list[Candle]:
    """Ta sama seria z drugiej giełdy: ceny z małym szumem (±noise), jak arbitraż giełd."""
    rng = random.Random(seed)
    out: list[Candle] = []
    for c in series:
        f = Decimal(f"{1 + rng.uniform(-noise, noise):.6f}")
        out.append(
            _fix_ohlc(
                replace(
                    c,
                    exchange=exchange,
                    open=c.open * f,
                    high=c.high * f,
                    low=c.low * f,
                    close=c.close * f,
                )
            )
        )
    return out


class FakeSource:
    """`MarketDataSource` z gotowych świec; opcjonalnie braki, duplikaty i awarie."""

    def __init__(
        self,
        exchange: str,
        candles: Iterable[Candle],
        *,
        missing: Iterable[int] = (),
        fail_on_call: Callable[[int], bool] | None = None,
    ) -> None:
        self._exchange = exchange
        self.data: dict[tuple[str, int], list[Candle]] = {}
        for c in candles:
            self.data.setdefault((c.symbol, c.ts_ms), []).append(c)
        self.missing = set(missing)
        self.fail_on_call = fail_on_call
        self.calls = 0

    @property
    def exchange(self) -> str:
        return self._exchange

    def instruments(self, symbols: Iterable[str]) -> list[InstrumentInfo]:
        have = {s for s, _ in self.data}
        return [
            InstrumentInfo(
                exchange=self._exchange,
                symbol=s,
                exchange_symbol=s.replace("-", ""),
                base=s.split("-")[0],
                quote=s.split("-")[1],
                price_tick=Decimal("0.01"),
                amount_step=Decimal("0.0001"),
                active=True,
            )
            for s in symbols
            if s in have
        ]

    def candles(self, symbol: str, timeframe: Timeframe, time_range: TimeRange) -> list[Candle]:
        self.calls += 1
        if self.fail_on_call is not None and self.fail_on_call(self.calls):
            raise SourceUnavailableError(
                f"{self._exchange}: awaria testowa (wywołanie {self.calls})"
            )
        out: list[Candle] = []
        for ts in range(time_range.start_ms, time_range.end_ms, HOUR_MS):
            if ts not in self.missing:
                out.extend(self.data.get((symbol, ts), []))
        return out

    def stream_candles(self, symbols: Iterable[str]) -> Iterable[Candle]:
        raise NotImplementedError

    def funding(self, symbol: str, time_range: TimeRange) -> list[object]:
        raise NotImplementedError

    def open_interest(self, symbol: str, time_range: TimeRange) -> list[object]:
        raise NotImplementedError

    def orderbook_top(self, symbol: str, depth: int) -> object:
        raise NotImplementedError


def as_source(s: FakeSource) -> MarketDataSource:
    return s
