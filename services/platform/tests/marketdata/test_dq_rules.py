"""Reguły DQ: wartości referencyjne liczone ręcznie, właściwości i brak zaglądania w przyszłość."""

from __future__ import annotations

import math
from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from md_helpers import T0, candle, gbm_series, mirror

from goatcash.marketdata._impl.dq import (
    CROSS_DEVIATION,
    DUPLICATE,
    NEGATIVE_VOLUME,
    NONPOSITIVE_PRICE,
    OHLC_INCONSISTENT,
    PRICE_SPIKE,
    population_std,
    relative_deviation,
)
from goatcash.marketdata.api import HOUR_MS, Candle, DqConfig, DqResult, PairDq, is_stale


def alternating(n: int, a: float, start: float = 100.0, exchange: str = "okx") -> list[Candle]:
    """Stopy zwrotu na przemian +a i -a (log): odchylenie standardowe populacji = a."""
    out: list[Candle] = []
    price = start
    for i in range(n):
        out.append(candle(T0 + i * HOUR_MS, f"{price:.10f}", exchange=exchange))
        price *= math.exp(a if i % 2 == 0 else -a)
    return out


def kinds(result: DqResult) -> set[str]:
    return {e.kind for e in result.events}


# --- wartości referencyjne ---


def test_relative_deviation_reference_values() -> None:
    # |103 - 100| / ((103 + 100) / 2) = 3 / 101,5 = 0,029556...
    assert relative_deviation(Decimal(103), Decimal(100)) == Decimal(3) / Decimal("101.5")
    assert relative_deviation(Decimal(100), Decimal(100)) == 0


def test_deviation_threshold_exactly_3_percent_not_flagged() -> None:
    # Odchylenie dokładnie 3%: a = 100, b takie, że |a-b|/((a+b)/2) = 0,03 → b = 100*2,03/1,97.
    b = Decimal(100) * Decimal("2.03") / Decimal("1.97")
    assert relative_deviation(b, Decimal(100)) <= Decimal("0.03")
    dq = PairDq(("okx", "bybit"))
    result = dq.process([candle(T0, "100"), candle(T0, b, exchange="bybit")])
    assert CROSS_DEVIATION not in kinds(result)
    result = dq.process(
        [candle(T0 + HOUR_MS, "100"), candle(T0 + HOUR_MS, b * Decimal("1.0002"), exchange="bybit")]
    )
    assert CROSS_DEVIATION in kinds(result)


def test_population_std_reference_values() -> None:
    assert population_std([0.01, -0.01] * 50) == pytest.approx(0.01, abs=1e-15)
    # [1, 2, 3, 4]: średnia 2,5; wariancja (2,25 + 0,25 + 0,25 + 2,25) / 4 = 1,25.
    assert population_std([1, 2, 3, 4]) == pytest.approx(math.sqrt(1.25), abs=1e-15)


def test_spike_threshold_8_sigma_reference() -> None:
    a = 0.005  # sigma okna = 0,005; próg 8 sigma = 0,04 (log)
    history = alternating(169, a)  # 168 stóp zwrotu w oknie
    last = history[-1]
    below = last.close * Decimal(str(math.exp(0.0399)))
    above = last.close * Decimal(str(math.exp(0.0401)))
    dq = PairDq(("okx",))
    dq.warm_up("okx", history)
    assert PRICE_SPIKE not in kinds(dq.process([candle(last.ts_ms + HOUR_MS, below)]))
    dq = PairDq(("okx",))
    dq.warm_up("okx", history)
    assert PRICE_SPIKE in kinds(dq.process([candle(last.ts_ms + HOUR_MS, above)]))


def test_spike_needs_min_window() -> None:
    history = alternating(40, 0.001)  # 39 stóp zwrotu < 48
    dq = PairDq(("okx",))
    dq.warm_up("okx", history)
    jump = history[-1].close * 2
    assert PRICE_SPIKE not in kinds(dq.process([candle(history[-1].ts_ms + HOUR_MS, jump)]))


def test_spike_confirmed_by_second_exchange_is_not_flagged() -> None:
    okx = alternating(169, 0.002)
    bybit = alternating(169, 0.002, exchange="bybit")
    dq = PairDq(("okx", "bybit"))
    dq.warm_up("okx", okx)
    dq.warm_up("bybit", bybit)
    ts = okx[-1].ts_ms + HOUR_MS
    crash = okx[-1].close * Decimal("0.8")
    result = dq.process([candle(ts, crash), candle(ts, crash * Decimal("1.001"), exchange="bybit")])
    assert result.events == []  # prawdziwy ruch rynku, obie giełdy zgodne


def test_deviation_flags_the_exchange_that_jumped() -> None:
    okx = alternating(169, 0.002)
    bybit = alternating(169, 0.002, exchange="bybit")
    dq = PairDq(("okx", "bybit"))
    dq.warm_up("okx", okx)
    dq.warm_up("bybit", bybit)
    ts = okx[-1].ts_ms + HOUR_MS
    result = dq.process(
        [candle(ts, okx[-1].close), candle(ts, bybit[-1].close * Decimal("1.05"), exchange="bybit")]
    )
    assert [(e.exchange, e.kind) for e in result.events] == [("bybit", CROSS_DEVIATION)]
    assert result.flagged == {("bybit", ts)}
    assert [c.exchange for c in result.good()] == ["okx"]


def test_row_rules() -> None:
    good = candle(T0, "100")
    cases = [
        (OHLC_INCONSISTENT, replace(good, high=Decimal("99"))),  # high < open i close
        (OHLC_INCONSISTENT, replace(good, close=good.high + 1)),  # tylko close > high
        (OHLC_INCONSISTENT, replace(good, close=good.low - 1)),  # tylko close < low
        (OHLC_INCONSISTENT, replace(good, open=good.high + 1)),  # tylko open > high
        (OHLC_INCONSISTENT, replace(good, open=good.low - 1)),  # tylko open < low
        (NEGATIVE_VOLUME, replace(good, volume=Decimal("-0.1"))),
        (NONPOSITIVE_PRICE, replace(good, low=Decimal("0"))),
    ]
    for kind, bad in cases:
        result = PairDq(("okx",)).process([bad])
        assert kind in kinds(result), bad
        assert result.accepted == []
    assert PairDq(("okx",)).process([replace(good, volume=Decimal(0))]).events == []


def test_duplicates_in_batch_and_across_batches() -> None:
    dq = PairDq(("okx",))
    a = candle(T0, "100")
    result = dq.process([a, replace(a, close=Decimal("100.05"))])
    assert [e.kind for e in result.events] == [DUPLICATE]
    assert result.accepted == [a]  # zostaje pierwsza
    later = dq.process([candle(T0, "100")])  # ta sama chwila w kolejnej partii
    assert [e.kind for e in later.events] == [DUPLICATE]


def test_flagged_spike_does_not_poison_next_candle() -> None:
    history = alternating(169, 0.002)
    dq = PairDq(("okx",))
    dq.warm_up("okx", history)
    ts = history[-1].ts_ms + HOUR_MS
    normal = history[-1].close
    result = dq.process([candle(ts, normal * 3), candle(ts + HOUR_MS, normal)])
    assert [(e.kind, e.ts_ms) for e in result.events] == [(PRICE_SPIKE, ts)]


def test_level_shift_accepted_after_consistent_run() -> None:
    history = alternating(169, 0.002)
    dq = PairDq(("okx",), DqConfig(level_shift_after=3))
    dq.warm_up("okx", history)
    ts = history[-1].ts_ms + HOUR_MS
    level = history[-1].close * 2
    seq = [candle(ts + i * HOUR_MS, level * Decimal(str(1 + 0.001 * i))) for i in range(6)]
    result = dq.process(seq)
    flagged_ts = sorted(t for _, t in result.flagged)
    assert flagged_ts == [ts, ts + HOUR_MS, ts + 2 * HOUR_MS]  # potem nowy poziom przyjęty


def test_stale_after_2_hours() -> None:
    last = T0
    closes = last + HOUR_MS
    assert not is_stale(last, closes + 2 * HOUR_MS)
    assert is_stale(last, closes + 2 * HOUR_MS + 1)
    assert is_stale(None, closes)


# --- właściwości ---


@settings(max_examples=40, deadline=None)
@given(
    seed=st.integers(0, 10_000),
    cut=st.integers(min_value=1, max_value=599),
    batch=st.sampled_from([1, 7, 100, 600]),
)
def test_no_lookahead_prefix_gives_same_verdicts(seed: int, cut: int, batch: int) -> None:
    """Werdykty dla świec ≤ t nie zależą od świec po t (ani od podziału na partie)."""
    okx = gbm_series(600, seed=seed, sigma=0.01)
    bybit = mirror(okx, exchange="bybit", seed=seed, noise=0.02)  # część odchyleń > 3%
    data = sorted([*okx, *bybit], key=lambda c: c.ts_ms)

    def verdicts(
        candles: list[Candle], step: int
    ) -> tuple[set[tuple[str, int, str]], set[tuple[str, int]]]:
        dq = PairDq(("okx", "bybit"))
        events: set[tuple[str, int, str]] = set()
        flagged: set[tuple[str, int]] = set()
        times = sorted({c.ts_ms for c in candles})
        for i in range(0, len(times), step):
            chunk = set(times[i : i + step])
            r = dq.process([c for c in candles if c.ts_ms in chunk])
            events |= {(e.exchange, e.ts_ms, e.kind) for e in r.events}
            flagged |= r.flagged
        return events, flagged

    limit = T0 + cut * HOUR_MS
    full_events, full_flagged = verdicts(data, 600)
    pre_events, pre_flagged = verdicts([c for c in data if c.ts_ms < limit], batch)
    assert pre_events == {e for e in full_events if e[1] < limit}
    assert pre_flagged == {f for f in full_flagged if f[1] < limit}


@settings(max_examples=50, deadline=None)
@given(seed=st.integers(0, 10_000))
def test_accepted_candles_always_pass_row_rules(seed: int) -> None:
    okx = gbm_series(300, seed=seed)
    bad = [replace(c, high=c.low / 2) if i % 17 == 0 else c for i, c in enumerate(okx)]
    result = PairDq(("okx",)).process(bad)
    for c in result.accepted:
        assert c.low <= min(c.open, c.close) <= max(c.open, c.close) <= c.high
        assert c.volume >= 0
    assert len(result.accepted) + sum(1 for e in result.events if e.decision == "rejected") == 300
