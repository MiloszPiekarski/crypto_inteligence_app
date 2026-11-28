"""Wartości referencyjne cech `fs-1p` (bramka G5p, testy.md 3a; tabela testów E5).

Każda cecha porównana z dwiema niezależnymi implementacjami: TA-Lib (C) i czystym Pythonem
(`reference.py`), na danych syntetycznych i na prawdziwej cenie referencyjnej z kaset E4
(OKX + Bybit, 5 par x 2000 h). Kryterium: |nasza - wzorcowa| <= 1e-9 · max(1, |wzorcowa|)
po okresie rozgrzewki, a wartość jest (status `ok`) dokładnie tam, gdzie wzorzec ją ma.
Do tego przykłady policzone ręcznie (wynik w komentarzu).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np
import numpy.typing as npt
import polars as pl
import pytest
import talib
from fs_helpers import BTC, ETH, SOL, T0, H, close_enough, gbm_bars, real_series_source
from reference import features as py_features

from goatcash.features.api import (
    FEATURE_NAMES,
    FS_1P,
    InMemoryRefSource,
    MarketView,
    Pair,
    RefBar,
    btc_pair,
    pair_frame,
    status_column,
)

Arr = npt.NDArray[np.float64]


def _talib_features(bars: Sequence[RefBar], btc: Sequence[RefBar] | None) -> dict[str, Arr]:
    """Cechy z prymitywów TA-Lib (ten sam odcinek świec; NaN = brak wartości)."""
    o = np.array([b.open for b in bars])
    h = np.array([b.high for b in bars])
    lo = np.array([b.low for b in bars])
    c = np.array([b.close for b in bars])
    v = np.array([b.volume for b in bars])
    del o
    out: dict[str, Arr] = {}
    for n in (1, 4, 24, 168):
        out[f"ret_log_{n}h"] = np.log(talib.ROCR(c, n))
    r1 = np.log(talib.ROCR(c, 1))
    r1_valid = r1.copy()
    out["vol_realized_24h"] = np.full_like(c, np.nan)
    out["vol_realized_24h"][1:] = np.sqrt(talib.SUM(r1_valid[1:] ** 2, 24))
    out["vol_parkinson_24h"] = np.sqrt(talib.SUM(np.log(h / lo) ** 2, 24) / (4 * math.log(2) * 24))
    out["atr_14_rel"] = talib.ATR(h, lo, c, 14) / c
    out["rsi_14"] = talib.RSI(c, 14)
    macd = talib.EMA(c, 12) - talib.EMA(c, 26)
    sig = np.full_like(c, np.nan)
    if len(c) > 25:
        sig[25:] = talib.EMA(macd[25:], 9)
    out["macd_rel"] = macd / c
    out["macd_hist_rel"] = (macd - sig) / c
    out["adx_14"] = talib.ADX(h, lo, c, 14)
    out["ema_20_dist"] = c / talib.EMA(c, 20) - 1
    e50 = talib.EMA(c, 50)
    slope = np.full_like(c, np.nan)
    slope[24:] = e50[24:] / e50[:-24] - 1
    out["ema_50_slope_24h"] = slope
    upper, middle, lower = talib.BBANDS(c, 20, 2, 2)
    out["bb_pctb_20"] = (c - lower) / (upper - lower)
    out["bb_width_20"] = (upper - lower) / middle
    out["zscore_close_168h"] = (c - talib.SMA(c, 168)) / talib.STDDEV(c, 168, 1)
    hh, ll = talib.MAX(h, 168), talib.MIN(lo, 168)
    out["donchian_pos_168h"] = (c - ll) / (hh - ll)
    out["volume_rel_168h"] = v / talib.SMA(v, 168)
    corr = np.full_like(c, np.nan)
    if btc is not None:
        cb = np.array([b.close for b in btc])
        rb = np.log(talib.ROCR(cb, 1))
        corr[1:] = talib.CORREL(r1[1:], rb[1:], 168)
    out["corr_btc_168h"] = corr
    return out


def _python_features(bars: Sequence[RefBar], btc: Sequence[RefBar] | None) -> dict[str, Arr]:
    raw = py_features(bars, None if btc is None else [b.close for b in btc])
    return {k: np.array([math.nan if x is None else x for x in xs]) for k, xs in raw.items()}


Reference = Callable[[Sequence[RefBar], Sequence[RefBar] | None], dict[str, Arr]]


def _runs(bars: Sequence[RefBar]) -> list[list[RefBar]]:
    runs: list[list[RefBar]] = []
    for b in bars:
        if runs and b.ts_ms == runs[-1][-1].ts_ms + H:
            runs[-1].append(b)
        else:
            runs.append([b])
    return runs


def _compare(src: InMemoryRefSource, pairs: Sequence[Pair], reference: Reference) -> dict[str, int]:
    """Porównuje cechy par z wzorcem na każdym ciągłym odcinku; zwraca liczbę porównań."""
    until = (
        max(
            b.ts_ms
            for p in src.pairs()
            for b in src.ref_bars(p, close_until_ms=2**62, known_at_ms=None)
        )
        + H
    )
    view = MarketView(src, until)
    compared = dict.fromkeys(FEATURE_NAMES, 0)
    errors: list[str] = []
    for pair in pairs:
        frame = pair_frame(view, pair).with_columns((pl.col("as_of") - H).alias("ts"))
        rows = {int(r["ts"]): r for r in frame.iter_rows(named=True)}
        bars = list(src.ref_bars(pair, close_until_ms=until, known_at_ms=None))
        btc_all = {
            b.ts_ms: b for b in src.ref_bars(btc_pair(pair), close_until_ms=until, known_at_ms=None)
        }
        for run in _runs(bars):
            btc_run = [btc_all[b.ts_ms] for b in run if b.ts_ms in btc_all]
            has_btc = pair.base != "BTC" and len(btc_run) == len(run)
            ref = reference(run, btc_run if has_btc else None)
            for k, bar in enumerate(run):
                row = rows[bar.ts_ms]
                for name in FEATURE_NAMES:
                    if name == "corr_btc_168h" and not has_btc:
                        continue
                    expected = float(ref[name][k])
                    ok = row[status_column(name)] == "ok"
                    if math.isnan(expected):
                        if ok:
                            errors.append(f"{pair} {name} k={k}: wartość, wzorzec jej nie ma")
                        continue
                    if not ok:
                        errors.append(
                            f"{pair} {name} k={k}: brak wartości ({row[status_column(name)]})"
                        )
                        continue
                    if not close_enough(float(row[name]), expected):
                        errors.append(f"{pair} {name} k={k}: {row[name]!r} != {expected!r}")
                    compared[name] += 1
    assert not errors, "\n".join(errors[:20])
    return compared


def _synthetic(seed: int) -> InMemoryRefSource:
    return InMemoryRefSource(
        {
            BTC: gbm_bars(700, seed=seed, price=40_000.0),
            ETH: gbm_bars(700, seed=seed + 1, price=2_500.0, sigma=0.015),
            SOL: gbm_bars(700, seed=seed + 2, price=0.35, sigma=0.03, drift=0.0005),
        }
    )


@pytest.mark.parametrize("reference", [_talib_features, _python_features], ids=["talib", "python"])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_synthetic_matches_reference(reference: Reference, seed: int) -> None:
    compared = _compare(_synthetic(seed), [BTC, ETH, SOL], reference)
    # Każda cecha porównana na setkach chwil (nie pusto): 700 h minus okno rozgrzewki.
    for f in FS_1P:
        expected_pairs = 2 if f.name == "corr_btc_168h" else 3
        assert compared[f.name] == expected_pairs * (700 - f.window + 1), f.name


@pytest.fixture(scope="module")
def real_source() -> InMemoryRefSource:
    return real_series_source()


@pytest.mark.parametrize("reference", [_talib_features, _python_features], ids=["talib", "python"])
def test_real_prices_match_reference(reference: Reference, real_source: InMemoryRefSource) -> None:
    pairs = real_source.pairs()
    assert [str(p) for p in pairs] == ["APT/USDT", "BTC/USDT", "DOGE/USDT", "ETH/USDT", "SOL/USDT"]
    compared = _compare(real_source, pairs, reference)
    for f in FS_1P:
        assert compared[f.name] > 1500 * (4 if f.name == "corr_btc_168h" else 5), f.name


# --- przykłady policzone ręcznie ---


def _bars(
    closes: Sequence[float], *, spread: float = 0.0, volumes: Sequence[float] | None = None
) -> list[RefBar]:
    out: list[RefBar] = []
    prev = closes[0]
    for i, c in enumerate(closes):
        ts = T0 + i * H
        hi, lo = max(prev, c) + spread, min(prev, c) - spread
        vol = 1.0 if volumes is None else volumes[i]
        out.append(RefBar(ts, prev, hi, lo, c, vol, ts + H))
        prev = c
    return out


def _last(bars: list[RefBar], btc: list[RefBar] | None = None) -> dict[str, tuple[float, str]]:
    pair = Pair("X", "USDT")
    data = {pair: bars} if btc is None else {pair: bars, Pair("BTC", "USDT"): btc}
    src = InMemoryRefSource(data)
    frame = pair_frame(MarketView(src, bars[-1].ts_ms + H), pair)
    row = frame.row(-1, named=True)
    return {n: (float(row[n]), str(row[status_column(n)])) for n in FEATURE_NAMES}


def test_hand_computed_returns_and_volatility() -> None:
    # Zamknięcia na przemian 100 i 101: |r_1h| = ln(1.01) w każdej godzinie.
    closes = [100.0 if i % 2 == 0 else 101.0 for i in range(170)]
    got = _last(_bars(closes))
    r = math.log(1.01)
    assert got["ret_log_1h"] == (pytest.approx(r, abs=1e-15), "ok")  # 169 nieparzyste: 100 -> 101
    assert got["ret_log_4h"][0] == pytest.approx(0.0, abs=1e-15)
    assert got["ret_log_168h"][0] == pytest.approx(0.0, abs=1e-15)
    # Zmienność zrealizowana 24 h: sqrt(24 · r^2) = r · sqrt(24).
    assert got["vol_realized_24h"][0] == pytest.approx(r * math.sqrt(24), rel=1e-12)
    # Parkinson przy H/L = 101/100 w każdej świecy:
    # sqrt(24 r^2 / (4 ln2 · 24)) = r / (2 sqrt(ln 2)).
    assert got["vol_parkinson_24h"][0] == pytest.approx(r / (2 * math.sqrt(math.log(2))), rel=1e-12)


def test_hand_computed_oscillators() -> None:
    # Na przemian +2 i -1 (14 zmian: 7 wzrostów, 7 spadków): średni zysk 14/14 = 1,
    # średnia strata 7/14 = 0,5, RSI = 100 · 1 / 1,5 = 66,67 (pierwsza wartość, k = 14).
    closes = [100.0]
    for i in range(14):
        closes.append(closes[-1] + (2.0 if i % 2 == 0 else -1.0))
    assert _last(_bars(closes))["rsi_14"][0] == pytest.approx(200.0 / 3.0, rel=1e-12)
    # Same wzrosty: RSI 100; płaska cena: brak ruchu, RSI 50 (decyzja, TA-Lib daje 0).
    assert _last(_bars([100.0 + i for i in range(15)]))["rsi_14"][0] == 100.0
    flat = _last(_bars([100.0] * 200))
    assert flat["rsi_14"] == (50.0, "ok")
    # Płaska cena: odchylenie 0, więc %B i z-score nie mają wartości (status undefined),
    # a szerokość wstęgi to 0; zakres Donchiana 0 (H = L = c): undefined.
    assert math.isnan(flat["bb_pctb_20"][0])
    assert flat["bb_pctb_20"][1] == "undefined"
    assert flat["zscore_close_168h"][1] == "undefined"
    assert flat["donchian_pos_168h"][1] == "undefined"
    assert flat["bb_width_20"] == (0.0, "ok")
    assert flat["ema_20_dist"] == (0.0, "ok")
    assert flat["ema_50_slope_24h"] == (0.0, "ok")
    assert flat["macd_rel"] == (0.0, "ok")
    assert flat["macd_hist_rel"] == (0.0, "ok")


def test_hand_computed_bands_and_ranges() -> None:
    # Zamknięcia 1 i 3 na przemian: średnia 2, odchylenie (populacyjne) 1, wstęgi 0 i 4.
    closes = [1.0 if i % 2 == 0 else 3.0 for i in range(168)]
    got = _last(_bars(closes))
    assert got["bb_pctb_20"][0] == pytest.approx(0.75, rel=1e-12)  # (3 - 0) / (4 - 0)
    assert got["bb_width_20"][0] == pytest.approx(2.0, rel=1e-12)  # (4 - 0) / 2
    assert got["zscore_close_168h"][0] == pytest.approx(1.0, rel=1e-12)  # (3 - 2) / 1
    # Donchian: H = max(1, 3) = 3, L = min = 1 w każdej świecy; c = 3 -> pozycja 1.
    assert got["donchian_pos_168h"][0] == pytest.approx(1.0, rel=1e-12)
    # Wolumen 10 przez 167 h i 20 w ostatniej: 20 / ((167 · 10 + 20) / 168) = 3360 / 1690.
    vols = [10.0] * 167 + [20.0]
    assert _last(_bars([100.0] * 168, volumes=vols))["volume_rel_168h"][0] == pytest.approx(
        3360.0 / 1690.0, rel=1e-12
    )


def test_hand_computed_trend_strength_and_atr() -> None:
    # Stały wzrost o 1 i świece bez cieni: +DM = 1, -DM = 0 -> -DI = 0, DX = 100, ADX = 100.
    up = _last(_bars([100.0 + i for i in range(60)]))
    assert up["adx_14"][0] == pytest.approx(100.0, rel=1e-12)
    # Zakres świecy stały: TR = 1 (ruch o 1) + 2 · 0,5 (cienie) = 2 -> ATR = 2.
    got = _last(_bars([100.0 + i for i in range(20)], spread=0.5))
    assert got["atr_14_rel"][0] == pytest.approx(2.0 / 119.0, rel=1e-12)


def test_hand_computed_correlation() -> None:
    # Zwroty pary = 2 * zwroty BTC (ceny w potędze 2): korelacja 1; odwrotne: -1.
    btc_closes = [100.0 * math.exp(0.01 * math.sin(i)) for i in range(170)]
    btc = _bars(btc_closes)
    pair = _bars([c * c / 100.0 for c in btc_closes])
    inverse = _bars([1e4 / c for c in btc_closes])
    assert _last(pair, btc)["corr_btc_168h"][0] == pytest.approx(1.0, abs=1e-12)
    assert _last(inverse, btc)["corr_btc_168h"][0] == pytest.approx(-1.0, abs=1e-12)


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_macd_definition_vs_talib_macd_function(seed: int) -> None:
    # `macd_rel` to (EMA12 - EMA26) / c z EMA zaczynającymi się jak w TA-Lib (średnia
    # prosta pierwszych n wartości); funkcja talib.MACD zaczyna szybką EMA inaczej (od
    # świecy, w której startuje wolna). Różnica jest więc tylko na początku odcinka i wygasa:
    # po 130 h od początku danych (albo od luki) jest < 1e-9, a na starcie rzędu 1e-4..1e-2.
    # Audyt E5 (28.11.2026), definicja w docs/praca/metody.md, sekcja 2.
    bars = gbm_bars(700, seed=seed, price=2_500.0, sigma=0.02)
    pair = Pair("X", "USDT")
    frame = pair_frame(MarketView(InMemoryRefSource({pair: bars}), bars[-1].ts_ms + H), pair)
    c = np.array([b.close for b in bars])
    macd_talib, _signal, _hist = talib.MACD(c, 12, 26, 9)
    ours = np.array(frame["macd_rel"].to_list())
    diff = np.abs(ours - macd_talib / c)
    assert np.nanmax(diff[33:60]) > 1e-6  # różnica na starcie jest (definicje nie są te same)
    assert np.nanmax(diff[130:]) < 1e-9  # i wygasa: dalej obie definicje są zgodne
