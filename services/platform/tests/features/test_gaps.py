"""Braki danych: cecha = NaN + status, nigdy cicha interpolacja (G5p; tabela testów E5).

Luka w cenie referencyjnej (świeca nie przyszła albo obie giełdy oznaczone przez DQ E4)
daje w tej godzinie `missing_data` dla wszystkich cech, a po luce każda cecha czeka na
pełne okno nowych danych. Wartości po luce są liczone wyłącznie z danych po luce.
Test mutacyjny: wariant z wypełnianiem luk poprzednią świecą jest wykrywany.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal

import polars as pl
import pytest
from fs_helpers import BTC, ETH, T0, H, bits, drop_hours, gbm_bars

from goatcash.features._impl import compute
from goatcash.features.api import (
    FEATURE_NAMES,
    FS_1P,
    InMemoryRefSource,
    MarketView,
    Pair,
    RefBar,
    features_at,
    pair_frame,
    status_column,
)
from goatcash.marketdata.api import Candle, PairDq, reference_candles

N = 500
GAP = [200, 201, 202, 203]  # 4 godziny bez ceny referencyjnej


def _frame(data: Mapping[Pair, Sequence[RefBar]], pair: Pair, until: int) -> pl.DataFrame:
    return pair_frame(MarketView(InMemoryRefSource(data), until), pair)


def _row(frame: pl.DataFrame, ts: int) -> dict[str, object]:
    return frame.filter(pl.col("as_of") == ts + H).row(0, named=True)


def gap_violations(frame: pl.DataFrame, gap_ts: Sequence[int], after_gap: int) -> list[str]:
    """Naruszenia reguł braków: wartość w luce, wartość przed pełnym oknem po luce itd."""
    found: list[str] = []
    for ts in gap_ts:
        row = _row(frame, ts)
        for n in FEATURE_NAMES:
            if row[status_column(n)] != "missing_data" or not math.isnan(float(str(row[n]))):
                found.append(f"luka {ts}: {n} = {row[n]} ({row[status_column(n)]})")
        if row["data_cutoff"] != gap_ts[0]:  # ostatnia świeca przed luką zamknięta w gap_ts[0]
            found.append(f"luka {ts}: data_cutoff {row['data_cutoff']}")
    for f in FS_1P:
        for k in range(f.window + 2):
            row = _row(frame, after_gap + k * H)
            status = row[status_column(f.name)]
            want = "missing_data" if k < f.window - 1 else "ok"
            if status != want:
                found.append(f"{f.name} k={k} po luce: {status}, oczekiwano {want}")
    return found


def test_gap_gives_nan_with_status_and_restart_after_gap() -> None:
    btc = gbm_bars(N, seed=1, price=40_000.0)
    eth = drop_hours(gbm_bars(N, seed=2, price=2_000.0), GAP)
    frame = _frame({BTC: btc, ETH: eth}, ETH, T0 + N * H)
    gap_ts = [T0 + h * H for h in GAP]
    after = T0 + (GAP[-1] + 1) * H
    assert gap_violations(frame, gap_ts, after) == []
    # Na początku danych: rozgrzewka (warmup), nie brak danych.
    first = _row(frame, T0)
    assert first[status_column("ret_log_1h")] == "warmup"
    assert first[status_column("ret_log_168h")] == "warmup"


def test_values_after_gap_use_only_data_after_gap() -> None:
    # Bez interpolacji i bez przenoszenia stanu przez lukę: cechy po luce są takie same, jak
    # gdyby danych sprzed luki w ogóle nie było (bit w bit, także EMA i wygładzanie Wildera).
    btc = gbm_bars(N, seed=3, price=40_000.0)
    eth = drop_hours(gbm_bars(N, seed=4, price=2_000.0), GAP)
    after = T0 + (GAP[-1] + 1) * H
    full = _frame({BTC: btc, ETH: eth}, ETH, T0 + N * H)
    only_after = _frame(
        {BTC: [b for b in btc if b.ts_ms >= after], ETH: [b for b in eth if b.ts_ms >= after]},
        ETH,
        T0 + N * H,
    )
    tail = full.filter(pl.col("as_of") > after)
    expected = only_after.filter(pl.col("as_of") > after)
    for n in FEATURE_NAMES:
        values = [bits(x) for x in tail[n].to_list()]
        assert values == [bits(x) for x in expected[n].to_list()], n
        # statusy różnią się tylko nazwą przyczyny braku (po luce: missing_data, a bez
        # historii przed nią: warmup)
        got = [s.replace("missing_data", "warmup") for s in tail[status_column(n)].to_list()]
        assert got == expected[status_column(n)].to_list(), n


def test_forward_fill_mutation_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mutacja: „uzupełnienie” luki poprzednią świecą (cicha interpolacja) musi oblać test.
    original = compute._grid  # pyright: ignore[reportPrivateUsage]

    def filled_grid(bars: pl.DataFrame, start: int, end_ts_ms: int) -> pl.DataFrame:
        return original(bars, start, end_ts_ms).fill_null(strategy="forward")

    original_runs = compute._runs  # pyright: ignore[reportPrivateUsage]

    def filled_runs(frame: pl.DataFrame) -> list[pl.DataFrame]:
        grid = filled_grid(frame, int(frame["ts"][0]), int(frame["ts"][-1]))
        return original_runs(grid)

    monkeypatch.setattr(compute, "_grid", filled_grid)
    monkeypatch.setattr(compute, "_runs", filled_runs)
    btc = gbm_bars(N, seed=1, price=40_000.0)
    eth = drop_hours(gbm_bars(N, seed=2, price=2_000.0), GAP)
    frame = _frame({BTC: btc, ETH: eth}, ETH, T0 + N * H)
    found = gap_violations(frame, [T0 + h * H for h in GAP], T0 + (GAP[-1] + 1) * H)
    assert found  # mutacja wykryta


def _candle(exchange: str, bar: RefBar, *, bad: bool = False) -> Candle:
    close = Decimal(repr(bar.close))
    high = Decimal(repr(bar.high))
    return Candle(
        exchange=exchange,
        symbol="ETH-USDT",
        timeframe="1h",
        ts_ms=bar.ts_ms,
        open=Decimal(repr(bar.open)),
        # zła świeca: zamknięcie ponad szczytem (reguła OHLC w DQ E4)
        high=high if not bad else close - Decimal(1),
        low=Decimal(repr(bar.low)),
        close=close,
        volume=Decimal(repr(bar.volume)),
    )


def test_bad_dq_on_both_exchanges_is_a_gap_and_single_source_is_data() -> None:
    bars = gbm_bars(400, seed=5, price=2_000.0)
    both_bad, okx_bad = 250, 300
    candles: list[Candle] = []
    for i, b in enumerate(bars):
        candles.append(_candle("okx", b, bad=i in (both_bad, okx_bad)))
        candles.append(_candle("bybit", replace(b, volume=b.volume * 1.1), bad=i == both_bad))
    good = PairDq(["okx", "bybit"]).process(candles).good()
    refs = reference_candles(good)
    by_ts = {r.ts_ms: r for r in refs}
    assert T0 + both_bad * H not in by_ts  # obie giełdy złe: ceny referencyjnej nie ma
    assert by_ts[T0 + okx_bad * H].source == "single"  # jedna dobra giełda: cena z adnotacją
    src = InMemoryRefSource.from_ref_candles(
        refs, ingested_at_ms={(r.base, r.quote, r.ts_ms): r.ts_ms + H for r in refs}
    )
    gap = features_at(MarketView(src, T0 + (both_bad + 1) * H), ETH)
    assert set(gap.statuses.values()) == {"missing_data"}
    assert all(math.isnan(v) for v in gap.values.values())
    single = features_at(MarketView(src, T0 + (okx_bad + 1) * H), ETH)
    assert single.statuses["ret_log_1h"] == "ok"  # godzina z jednym źródłem ma dane


def test_btc_correlation_not_applicable_and_missing_btc() -> None:
    btc = gbm_bars(N, seed=6, price=40_000.0)
    eth = gbm_bars(N, seed=7, price=2_000.0)
    btc_frame = _frame({BTC: btc, ETH: eth}, BTC, T0 + N * H)
    assert set(btc_frame[status_column("corr_btc_168h")].to_list()) == {"not_applicable"}
    assert btc_frame["corr_btc_168h"].is_nan().all()
    # Luka tylko w BTC: korelacja ETH nie ma wartości, pozostałe cechy ETH mają.
    hole = drop_hours(btc, [400])
    eth_frame = _frame({BTC: hole, ETH: eth}, ETH, T0 + N * H)
    row = _row(eth_frame, T0 + 400 * H)
    assert row[status_column("corr_btc_168h")] == "missing_data"
    assert row[status_column("ret_log_168h")] == "ok"
    # Brak BTC w ogóle: korelacja missing_data.
    alone = _frame({ETH: eth}, ETH, T0 + N * H)
    assert set(alone[status_column("corr_btc_168h")].to_list()) == {"missing_data"}


def test_no_data_and_trailing_missing_hours() -> None:
    eth = gbm_bars(300, seed=8, price=2_000.0)
    src = InMemoryRefSource({ETH: eth})
    before = features_at(MarketView(src, T0), ETH)  # przed pierwszą świecą
    assert before.data_cutoff_ms is None
    assert set(before.statuses.values()) == {"missing_data"}
    # Dane się urwały 5 h przed as_of: brak danych, nie ostatnia znana wartość.
    late = features_at(MarketView(src, T0 + 305 * H), ETH)
    assert set(late.statuses.values()) == {"missing_data"}
    assert late.data_cutoff_ms == T0 + 300 * H


def test_declared_window_is_first_value_on_clean_data() -> None:
    btc = gbm_bars(N, seed=9, price=40_000.0)
    eth = gbm_bars(N, seed=10, price=2_000.0)
    frame = _frame({BTC: btc, ETH: eth}, ETH, T0 + N * H)
    for f in FS_1P:
        statuses = frame[status_column(f.name)].to_list()
        assert statuses.index("ok") == f.window - 1, f.name
        assert set(statuses[: f.window - 1]) == {"warmup"}, f.name
        assert set(statuses[f.window - 1 :]) == {"ok"}, f.name
