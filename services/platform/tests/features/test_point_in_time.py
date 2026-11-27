"""Brak zaglądania w przyszłość (bramka G5p, F-07; tabela testów E5, pierwszy wiersz).

Dla 1000 losowych chwil t (Hypothesis): cechy z danych obciętych do t (`MarketView(t)`,
jak na żywo) = cechy z pełnych danych w chwili t (pełne przeliczenie historii), bit w bit,
dla każdej z 19 cech `fs-1p` (100% cech) i każdej pary. Do tego replay z `known_at`,
niezmienność wyniku przy zmianie danych spoza widoku i testy mutacyjne: celowo
„zaglądające” warianty cech i źródła są wykrywane.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

import polars as pl
import pytest
from fs_helpers import BTC, ETH, SOL, T0, H, bits, drop_hours, gbm_bars, vector_mismatches
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from goatcash.features._impl import compute
from goatcash.features.api import (
    FEATURE_NAMES,
    FeatureDef,
    FeatureVector,
    InMemoryRefSource,
    LookAheadError,
    MarketView,
    Pair,
    RefBar,
    features_at,
    floor_hour,
    pair_frame,
    status_column,
)

N_HOURS = 900
END_MS = T0 + N_HOURS * H
PAIRS = (BTC, ETH, SOL)
# 1000 chwil, deterministycznie (derandomize): bramka na main musi dawać ten sam wynik
# przy każdym przebiegu; ziarno Hypothesis zależy od kodu testu.
PIT = settings(
    max_examples=1000,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _late(bars: list[RefBar], every: int, delay_ms: int) -> list[RefBar]:
    """Co `every`-ta świeca zapisana z opóźnieniem (np. uzupełniona później)."""
    return [
        replace(b, ingested_at_ms=b.ingested_at_ms + delay_ms) if i % every == 0 else b
        for i, b in enumerate(bars)
    ]


def _dataset() -> dict[Pair, list[RefBar]]:
    btc = drop_hours(gbm_bars(N_HOURS, seed=11, price=40_000.0), [500, 501, 502])
    eth = drop_hours(gbm_bars(N_HOURS, seed=12, price=2_500.0), [150, 700])
    # SOL notowany później (start po 80 h) i z długą luką: rozgrzewka i luki po drodze.
    sol = drop_hours(
        gbm_bars(N_HOURS - 80, seed=13, price=20.0, start_ms=T0 + 80 * H, sigma=0.02),
        range(300, 330),
        start_ms=T0 + 80 * H,
    )
    return {
        BTC: _late(btc, 7, 5 * H),
        ETH: _late(eth, 11, 3 * H),
        SOL: _late(sol, 13, 100 * H),
    }


DATA = _dataset()
SOURCE = InMemoryRefSource(DATA)


def _vector(pair: Pair, as_of_ms: int, row: Mapping[str, object] | None) -> FeatureVector:
    if row is None:
        return FeatureVector(
            pair,
            as_of_ms,
            None,
            dict.fromkeys(FEATURE_NAMES, math.nan),
            dict.fromkeys(FEATURE_NAMES, "missing_data"),
        )
    return FeatureVector(
        pair=pair,
        as_of_ms=as_of_ms,
        data_cutoff_ms=int(str(row["data_cutoff"])),
        values={n: float(str(row[n])) for n in FEATURE_NAMES},
        statuses={n: row[status_column(n)] for n in FEATURE_NAMES},  # type: ignore[misc]
    )


def _history(src: InMemoryRefSource, until_ms: int) -> dict[Pair, dict[int, dict[str, object]]]:
    """Pełne przeliczenie historii (wszystkie dane do `until_ms`): para → as_of → wiersz."""
    view = MarketView(src, until_ms)
    return {
        p: {int(r["as_of"]): r for r in pair_frame(view, p).iter_rows(named=True)}
        for p in src.pairs()
    }


def _expected(
    history: Mapping[Pair, Mapping[int, dict[str, object]]], pair: Pair, t: int
) -> FeatureVector:
    return _vector(pair, t, history[pair].get(floor_hour(t)))


FULL = _history(SOURCE, END_MS + 3 * H)  # siatka do najpóźniejszej losowanej chwili
moments = st.integers(min_value=T0, max_value=END_MS + 2 * H)  # także chwile w środku godziny
pairs = st.sampled_from(PAIRS)


def _check(
    t: int,
    pair: Pair,
    history: Mapping[Pair, Mapping[int, dict[str, object]]],
    src: InMemoryRefSource,
) -> list[str]:
    live = features_at(MarketView(src, t), pair)
    expected = _expected(history, pair, t)
    diff = vector_mismatches(live, expected)
    if live.data_cutoff_ms != expected.data_cutoff_ms:
        diff.append("data_cutoff")
    return diff


def test_point_in_time_1000_moments_all_features() -> None:
    seen: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    calls = [0]

    @PIT
    @given(t=moments, pair=pairs)
    def run(t: int, pair: Pair) -> None:
        calls[0] += 1
        live = features_at(MarketView(SOURCE, t), pair)
        expected = _expected(FULL, pair, t)
        assert vector_mismatches(live, expected) == [], (pair, t)
        assert live.data_cutoff_ms == expected.data_cutoff_ms
        if live.data_cutoff_ms is not None:
            assert live.data_cutoff_ms <= t  # nic zamkniętego po t
        for name, status in live.statuses.items():
            statuses[status] += 1
            if status == "ok":
                seen[name] += 1
                assert math.isfinite(live.values[name])
            else:
                assert math.isnan(live.values[name])  # poza ok zawsze NaN

    run()
    assert calls[0] >= 1000
    # 100% cech sprawdzone na prawdziwych wartościach (nie tylko na NaN): każda cecha ma
    # status ok w wielu z 1000 chwil; korelacja nie dotyczy BTC (1/3 chwil).
    assert set(seen) == set(FEATURE_NAMES)
    assert min(seen.values()) >= 100, seen
    assert {"ok", "warmup", "missing_data", "not_applicable"} <= set(statuses), statuses


def _known(src_data: Mapping[Pair, Sequence[RefBar]], known_at: int) -> InMemoryRefSource:
    return InMemoryRefSource(
        {p: [b for b in bars if b.ingested_at_ms <= known_at] for p, bars in src_data.items()}
    )


@settings(max_examples=300, deadline=None, derandomize=True, database=None)
@given(t=moments, lag=st.integers(min_value=-10 * H, max_value=120 * H), pair=pairs)
def test_replay_with_known_at_sees_only_rows_ingested_by_then(t: int, lag: int, pair: Pair) -> None:
    # Replay okresu zbieranego na żywo: w chwili t znaliśmy tylko wiersze zapisane do known_at
    # (świece uzupełnione później są wtedy luką). Wynik = pełne przeliczenie danych, które
    # istniały w known_at.
    known_at = t + lag
    live = features_at(MarketView(SOURCE, t, known_at), pair)
    known_src = _known(DATA, known_at)
    view = MarketView(known_src, t)
    frame = pair_frame(view, pair)
    row = None if frame.is_empty() else frame.row(-1, named=True)
    expected = _vector(pair, t, row)
    assert vector_mismatches(live, expected) == []


@st.composite
def _future_noise(draw: st.DrawFn, cutoff_ms: int) -> dict[Pair, list[RefBar]]:
    """Dane, w których wszystko zamknięte po `cutoff_ms` jest zmienione (inne ceny, luki)."""
    out: dict[Pair, list[RefBar]] = {}
    factor = draw(st.floats(min_value=0.5, max_value=2.0))
    drop_every = draw(st.integers(min_value=2, max_value=9))
    for pair, bars in DATA.items():
        kept: list[RefBar] = []
        for i, b in enumerate(bars):
            if b.ts_ms + H <= cutoff_ms:
                kept.append(b)
            elif i % drop_every:
                kept.append(
                    replace(
                        b,
                        open=b.open * factor,
                        high=b.high * factor * 1.01,
                        low=b.low * factor,
                        close=b.close * factor,
                        volume=b.volume * 3,
                    )
                )
        out[pair] = kept
    return out


@settings(max_examples=200, deadline=None, derandomize=True, database=None)
@given(data=st.data(), t=moments, pair=pairs)
def test_changing_the_future_does_not_change_features_at_t(
    data: st.DataObject, t: int, pair: Pair
) -> None:
    noisy = InMemoryRefSource(data.draw(_future_noise(t)))
    assert (
        vector_mismatches(
            features_at(MarketView(SOURCE, t), pair), features_at(MarketView(noisy, t), pair)
        )
        == []
    )


# --- testy mutacyjne: test point-in-time wykrywa cechę i źródło, które zaglądają w przyszłość ---

MUTATION_MOMENTS = [T0 + k * 37 * H + 1234 for k in range(16)]


def _leaky(name: str, expr: pl.Expr) -> Callable[..., pl.Expr]:
    original = compute._feature_expr  # pyright: ignore[reportPrivateUsage]

    def patched(f: FeatureDef) -> pl.Expr:
        return expr if f.name == name else original(f)

    return patched


@pytest.mark.parametrize(
    ("name", "expr"),
    [
        # zwrot z następnej godziny (przesunięcie w złą stronę)
        ("ret_log_1h", (pl.col("close").shift(-1) / pl.col("close")).log()),
        # normalizacja średnią i odchyleniem całej serii (także przyszłości)
        (
            "zscore_close_168h",
            (pl.col("close") - pl.col("close").mean()) / pl.col("close").std(),
        ),
        # okno wycentrowane (połowa okna z przyszłości)
        ("bb_width_20", pl.col("close").rolling_std(20, center=True) / pl.col("close")),
    ],
)
def test_point_in_time_detects_leaky_feature(
    monkeypatch: pytest.MonkeyPatch, name: str, expr: pl.Expr
) -> None:
    monkeypatch.setattr(compute, "_feature_expr", _leaky(name, expr))
    history = _history(SOURCE, END_MS + H)
    found = {m for t in MUTATION_MOMENTS for m in _check(t, ETH, history, SOURCE)}
    assert name in found
    assert found == {name}  # pozostałe cechy dalej zgodne


def test_view_rejects_source_returning_bars_closed_after_as_of() -> None:
    class Leaky(InMemoryRefSource):
        def ref_bars(
            self, pair: Pair, *, close_until_ms: int, known_at_ms: int | None
        ) -> Sequence[RefBar]:
            return super().ref_bars(
                pair, close_until_ms=close_until_ms + H, known_at_ms=known_at_ms
            )

    with pytest.raises(LookAheadError, match="po as_of"):
        features_at(MarketView(Leaky(DATA), T0 + 200 * H), ETH)


def test_view_rejects_source_ignoring_known_at() -> None:
    class Leaky(InMemoryRefSource):
        def ref_bars(
            self, pair: Pair, *, close_until_ms: int, known_at_ms: int | None
        ) -> Sequence[RefBar]:
            return super().ref_bars(pair, close_until_ms=close_until_ms, known_at_ms=None)

    t = T0 + 200 * H
    with pytest.raises(LookAheadError, match="po known_at"):
        features_at(MarketView(Leaky(DATA), t, known_at=t - 50 * H), SOL)


def test_unaligned_as_of_uses_only_closed_candles() -> None:
    # 10:59:59.999 -> ostatnia zamknięta świeca to 09:00-10:00, nie 10:00-11:00.
    t = T0 + 300 * H - 1
    view = MarketView(SOURCE, t)
    assert view.last_bar_ts_ms == T0 + 298 * H
    assert int(view.bars(ETH)["ts"].max()) == T0 + 298 * H  # type: ignore[arg-type]
    live = features_at(view, ETH)
    assert live.data_cutoff_ms == T0 + 299 * H
    assert bits(live.values["ret_log_1h"]) == bits(
        features_at(MarketView(SOURCE, T0 + 299 * H), ETH).values["ret_log_1h"]
    )
