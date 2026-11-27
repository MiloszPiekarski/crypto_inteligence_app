"""DQ: wykrycie ≥ 95% z 200 wstrzykniętych błędów, fałszywe alarmy < 1% (bramka G4p, F-05).

Dane bazowe: dwie giełdy (seria GBM i jej odbicie z szumem ±0,05%, jak ceny tej samej pary
na dwóch giełdach). Błędy 7 rodzajów, każdy w innej chwili (odstęp ≥ 3 h, po 200 h
rozgrzania), na losowej giełdzie:

1. niespójne OHLC (high poniżej max(open, close)),
2. ujemny wolumen,
3. cena ≤ 0,
4. duplikat (ta sama chwila drugi raz, z innymi wartościami),
5. skok ceny 10-60% na jednej giełdzie, gdy druga nie ma świecy w tej chwili (reguła 8 sigma),
6. odchylenie od drugiej giełdy 3,5-20% (reguła 3%),
7. brakująca świeca (detektor luk).

Wykrycie = zdarzenie DQ dla tej giełdy i chwili (dla luki: luka obejmująca tę chwilę).
Fałszywy alarm = zdarzenie dla świecy, w której nic nie wstrzyknięto.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, replace
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from md_helpers import FIXTURES, gbm_series, mirror, replay_source

from goatcash.marketdata._impl.record import SERIES_PAIRS, series_window
from goatcash.marketdata.api import HOUR_MS, Candle, PairDq, TimeRange, find_gaps

KINDS = (
    "ohlc",
    "negative_volume",
    "nonpositive_price",
    "duplicate",
    "spike_single_source",
    "cross_deviation",
    "missing",
)
WARMUP_H = 200
N_HOURS = 3000


@dataclass(frozen=True)
class Injected:
    kind: str
    exchange: str
    ts: int


def corrupt_ohlc(c: Candle, rng: random.Random) -> Candle:
    """Różne naruszenia spójności: high za nisko, low za wysoko, close albo open poza zakresem."""
    variant = rng.randrange(4)
    if variant == 0:
        return replace(c, high=min(c.open, c.close) * Decimal("0.995"))
    if variant == 1:
        return replace(c, low=max(c.open, c.close) * Decimal("1.005"))
    if variant == 2:
        return replace(c, close=c.high * Decimal("1.002"))
    return replace(c, open=c.low * Decimal("0.998"))


def corrupt(c: Candle, kind: str, rng: random.Random) -> Candle:
    if kind == "ohlc":
        return corrupt_ohlc(c, rng)
    if kind == "negative_volume":
        return replace(c, volume=-abs(c.volume) - 1)
    if kind == "nonpositive_price":
        return replace(c, low=Decimal(0) if rng.random() < 0.5 else Decimal(-1))
    sign = 1 if rng.random() < 0.5 else -1
    if kind == "spike_single_source":
        f = Decimal(f"{1 + sign * rng.uniform(0.10, 0.60):.4f}")
    else:  # cross_deviation
        f = Decimal(f"{1 + sign * rng.uniform(0.035, 0.20):.4f}")
    return replace(c, open=c.open * f, high=c.high * f, low=c.low * f, close=c.close * f)


def build(
    seed: int, n_errors: int
) -> tuple[list[Candle], list[Injected], int, set[tuple[str, int]]]:
    rng = random.Random(seed)
    okx = gbm_series(N_HOURS, seed=seed, exchange="okx")
    bybit = mirror(okx, exchange="bybit", seed=seed + 1)
    t0 = okx[0].ts_ms
    data = {("okx", c.ts_ms): c for c in okx} | {("bybit", c.ts_ms): c for c in bybit}
    slots = list(range(WARMUP_H, N_HOURS, 3))
    rng.shuffle(slots)
    injected: list[Injected] = []
    extra: list[Candle] = []
    # Świece drugiej giełdy usunięte przy skoku z jednego źródła: prawdziwe braki, które
    # detektor luk słusznie zgłasza; nie są ani błędem z listy 200, ani fałszywym alarmem.
    collateral: set[tuple[str, int]] = set()
    kinds = [KINDS[i % len(KINDS)] for i in range(n_errors)]
    for kind, slot in zip(kinds, slots, strict=False):
        ts = t0 + slot * HOUR_MS
        ex = rng.choice(("okx", "bybit"))
        other = "bybit" if ex == "okx" else "okx"
        original = data[(ex, ts)]
        if kind == "missing":
            del data[(ex, ts)]
        elif kind == "duplicate":
            extra.append(replace(original, close=original.close, volume=original.volume + 1))
        elif kind == "spike_single_source":
            del data[(other, ts)]
            collateral.add((other, ts))
            data[(ex, ts)] = corrupt(original, kind, rng)
        else:
            data[(ex, ts)] = corrupt(original, kind, rng)
        injected.append(Injected(kind, ex, ts))
    candles = sorted([*data.values(), *extra], key=lambda c: (c.ts_ms, c.exchange))
    return candles, injected, t0, collateral


def run(candles: list[Candle], t0: int) -> tuple[set[tuple[str, int]], Counter[str], int]:
    dq = PairDq(("okx", "bybit"))
    # Partie po 500 h (jak okna uzupełniania historii): stan przechodzi między partiami.
    detected: set[tuple[str, int]] = set()
    kinds: Counter[str] = Counter()
    for start in range(0, N_HOURS, 500):
        lo, hi = t0 + start * HOUR_MS, t0 + (start + 500) * HOUR_MS
        result = dq.process([c for c in candles if lo <= c.ts_ms < hi])
        for e in result.events:
            detected.add((e.exchange, e.ts_ms))
            kinds[e.kind] += 1
    span = TimeRange(t0, t0 + N_HOURS * HOUR_MS)
    for ex in ("okx", "bybit"):
        present = {c.ts_ms for c in candles if c.exchange == ex}
        for gap in find_gaps(present, span, HOUR_MS):
            detected.update((ex, ts) for ts in range(gap.start_ms, gap.end_ms, HOUR_MS))
    return detected, kinds, len(candles)


def score(seed: int, n_errors: int) -> tuple[float, float, dict[str, tuple[int, int]]]:
    candles, injected, t0, collateral = build(seed, n_errors)
    detected, _, total = run(candles, t0)
    hits = {(i.exchange, i.ts) for i in injected}
    per_kind: dict[str, tuple[int, int]] = {}
    for kind in KINDS:
        mine = [i for i in injected if i.kind == kind]
        per_kind[kind] = (sum((i.exchange, i.ts) in detected for i in mine), len(mine))
    detection = sum(h in detected for h in hits) / len(hits)
    # Fałszywe alarmy: zdarzenia dla świec bez błędu, względem liczby świec bez błędu.
    false = len(detected - hits - collateral)
    false_rate = false / (total - len(hits))
    return detection, false_rate, per_kind


def test_200_injected_errors_detected_at_least_95_percent() -> None:
    detection, false_rate, per_kind = score(seed=2026, n_errors=200)
    print(f"wykrycie {detection:.1%}, fałszywe alarmy {false_rate:.3%}, typy: {per_kind}")
    assert sum(n for _, n in per_kind.values()) == 200
    assert detection >= 0.95
    assert false_rate < 0.01
    for kind, (hit, n) in per_kind.items():
        assert hit / n >= 0.95, f"{kind}: {hit}/{n}"


@settings(max_examples=15, deadline=None, derandomize=True)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_detection_holds_for_other_random_series(seed: int) -> None:
    detection, false_rate, _ = score(seed=seed, n_errors=200)
    assert detection >= 0.95
    assert false_rate < 0.01


def test_clean_two_source_data_has_under_1_percent_false_alarms() -> None:
    for seed in (1, 2, 3):
        okx = gbm_series(N_HOURS, seed=seed, exchange="okx")
        bybit = mirror(okx, exchange="bybit", seed=seed + 10)
        candles = sorted([*okx, *bybit], key=lambda c: c.ts_ms)
        detected, kinds, total = run(candles, okx[0].ts_ms)
        assert len(detected) / total < 0.01, kinds


def test_real_okx_series_single_source_under_1_percent_false_alarms() -> None:
    """Prawdziwe świece OKX (2000 h od 1.07.2024, w tym spadek 5.08.2024), jedna giełda.

    Bez drugiej giełdy reguła skoku nie ma potwierdzenia, więc to najtrudniejszy przypadek
    dla fałszywych alarmów (prawdziwe gwałtowne ruchy zostają oznaczone).
    """
    total = flagged = 0
    for symbol in SERIES_PAIRS:
        if not (FIXTURES / "okx" / f"series_{symbol}.json").exists():
            continue
        source, _ = replay_source("okx", [f"series_{symbol}"])
        candles = source.candles(symbol, "1h", series_window())
        result = PairDq(("okx",)).process(candles)
        total += len(candles)
        flagged += len({(e.exchange, e.ts_ms) for e in result.events})
    assert total > 9000
    print(f"OKX prawdziwe dane: {flagged}/{total} oznaczonych ({flagged / total:.3%})")
    assert flagged / total < 0.01


def test_real_two_exchange_series_under_1_percent_false_alarms() -> None:
    """Prawdziwe świece OKX i Bybit (te same 2000 h, 5 par): reguły z potwierdzeniem drugiej
    giełdy (odchylenie > 3%, skok bez potwierdzenia) na danych bez wstrzykniętych błędów."""
    total = flagged = 0
    for symbol in SERIES_PAIRS:
        okx, _ = replay_source("okx", [f"series_{symbol}"])
        bybit, _ = replay_source("bybit", [f"series_{symbol}"])
        candles = [
            *okx.candles(symbol, "1h", series_window()),
            *bybit.candles(symbol, "1h", series_window()),
        ]
        result = PairDq(("okx", "bybit")).process(candles)
        total += len(candles)
        flagged += len({(e.exchange, e.ts_ms) for e in result.events})
    assert total > 19_000
    print(f"OKX + Bybit prawdziwe dane: {flagged}/{total} oznaczonych ({flagged / total:.3%})")
    assert flagged / total < 0.01
