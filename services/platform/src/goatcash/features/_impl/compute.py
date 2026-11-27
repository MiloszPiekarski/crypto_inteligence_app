"""Liczenie cech `fs-1p` w Polars (roadmapa E5, zakres 2, 3 i 5 ścieżki pracy).

Model danych jednej pary: siatka godzin od pierwszej świecy do `end_ts` (świece brakujące
= wiersze bez danych). Ciągłe odcinki świec liczymy osobno: każda cecha w chwili t zależy
tylko od świec jej odcinka do t włącznie (nic z przyszłości, nic sprzed luki), więc
przeliczenie całej historii i liczenie na żywo z `MarketView(as_of)` dają te same liczby.

Wiersz siatki ze świecą `ts` to cechy w chwili `as_of = ts + 1 h` (świeca zamknięta).
Wartość cechy jest NaN zawsze, gdy status nie jest `ok` (bez interpolacji braków).
"""

from __future__ import annotations

import math
from collections.abc import Callable

import polars as pl

from goatcash.features._impl.definitions import FS_1P, FeatureDef
from goatcash.features._impl.types import HOUR_MS

STATUS_SUFFIX = ":status"
CORR_FEATURE = "corr_btc_168h"
# Odchylenie standardowe względnie mniejsze niż to traktujemy jako zero (płaska cena
# w oknie): z-score i %B nie mają wtedy wartości (status `undefined`), zamiast liczby
# z błędu zaokrągleń.
_FLAT_REL = 1e-12

_K = "_k"  # indeks świecy w odcinku (0 = pierwsza świeca po luce albo początku danych)


def status_column(name: str) -> str:
    return f"{name}{STATUS_SUFFIX}"


def _k() -> pl.Expr:
    return pl.col(_K)


def _null() -> pl.Expr:
    return pl.lit(None, dtype=pl.Float64)


def _seeded_ewm(x: pl.Expr, seed: pl.Expr, seed_idx: int, alpha: float) -> pl.Expr:
    """Rekurencja y_k = (1 - alpha) y_{k-1} + alpha x_k od y_{seed_idx} = seed (jak TA-Lib)."""
    return (
        pl.when(_k() < seed_idx)
        .then(_null())
        .when(_k() == seed_idx)
        .then(seed)
        .otherwise(x)
        .ewm_mean(alpha=alpha, adjust=False)
    )


def _ema(x: pl.Expr, n: int, start: int = 0) -> pl.Expr:
    """EMA(n) jak w TA-Lib: x ważne od indeksu `start`, start rekurencji od SMA(n)."""
    return _seeded_ewm(x, x.rolling_mean(n), start + n - 1, 2.0 / (n + 1))


def _wilder(x: pl.Expr, n: int, start: int) -> pl.Expr:
    """Wygładzanie Wildera (alpha = 1/n) od SMA(n) wartości x ważnych od `start`."""
    return _seeded_ewm(x, x.rolling_mean(n), start + n - 1, 1.0 / n)


def _from_k(value: pl.Expr, first_k: int) -> pl.Expr:
    return pl.when(_k() >= first_k).then(value).otherwise(_null())


def _safe_div(num: pl.Expr, den: pl.Expr, scale: pl.Expr | None = None) -> pl.Expr:
    """num / den; NaN, gdy mianownik zerowy (względem `scale`, jeśli podana)."""
    zero = den.abs() <= (scale.abs() * _FLAT_REL if scale is not None else pl.lit(0.0))
    return pl.when(zero).then(pl.lit(math.nan)).otherwise(num / den)


def _prev_close() -> pl.Expr:
    return pl.col("close").shift(1)


def _true_range() -> pl.Expr:
    h, low, pc = pl.col("high"), pl.col("low"), _prev_close()
    tr = pl.max_horizontal(h - low, (h - pc).abs(), (low - pc).abs())
    return _from_k(tr, 1)  # TR od drugiej świecy (wymaga poprzedniego zamknięcia)


def _log_return(n: int) -> pl.Expr:
    return (pl.col("close") / pl.col("close").shift(n)).log()


def _adx(n: int) -> pl.Expr:
    h, low = pl.col("high"), pl.col("low")
    up = h - h.shift(1)
    dn = low.shift(1) - low
    # Reguła ruchu kierunkowego jak w TA-Lib (ta_ADX.c): -DM, gdy spadek dołka > 0 i większy
    # niż wzrost szczytu; +DM, gdy wzrost szczytu > 0 i większy niż spadek dołka.
    mdm = _from_k(pl.when((dn > 0) & (up < dn)).then(dn).otherwise(0.0), 1)
    pdm = _from_k(pl.when((up > 0) & (up > dn)).then(up).otherwise(0.0), 1)
    tr = _true_range()
    # TA-Lib: suma Wildera z n-1 pierwszych wartości, potem S = S - S/n + x; po podzieleniu
    # przez n to EMA z alpha = 1/n i startem (suma n-1 wartości) / n w indeksie n-1.
    seed_idx = n - 1

    def smooth(x: pl.Expr) -> pl.Expr:
        return _seeded_ewm(x, x.rolling_sum(n - 1) / n, seed_idx, 1.0 / n)

    s_p, s_m, s_tr = smooth(pdm), smooth(mdm), smooth(tr)
    pdi = 100.0 * s_p / s_tr
    mdi = 100.0 * s_m / s_tr
    di_sum = pdi + mdi
    dx = pl.when(di_sum == 0).then(0.0).otherwise(100.0 * (pdi - mdi).abs() / di_sum)
    dx = _from_k(dx, n)  # pierwsze DX po pierwszym kroku wygładzania (indeks n)
    return _wilder(dx, n, n)


def _rsi(n: int) -> pl.Expr:
    d = pl.col("close") - _prev_close()
    gain = _from_k(d.clip(lower_bound=0.0), 1)
    loss = _from_k((-d).clip(lower_bound=0.0), 1)
    ag, al = _wilder(gain, n, 1), _wilder(loss, n, 1)
    total = ag + al
    # Brak ruchu w oknie (suma zer): stan neutralny 50 (TA-Lib zwraca wtedy 0).
    return pl.when(total == 0).then(50.0).otherwise(100.0 * ag / total)


def _macd_line(fast: int, slow: int) -> pl.Expr:
    c = pl.col("close")
    return _from_k(_ema(c, fast) - _ema(c, slow), slow - 1)


def _bands(n: int, k: float) -> tuple[pl.Expr, pl.Expr, pl.Expr]:
    c = pl.col("close")
    mid = c.rolling_mean(n)
    sd = c.rolling_std(n, ddof=0)
    return mid, sd, pl.lit(k) * sd


def _feature_expr(f: FeatureDef) -> pl.Expr:  # noqa: PLR0911, PLR0912 (jeden przypadek na wzór)
    c, h, low, v = pl.col("close"), pl.col("high"), pl.col("low"), pl.col("volume")
    p: Callable[[str], int] = f.param
    match f.formula:
        case "log_return":
            return _log_return(p("n"))
        case "realized_vol":
            return (_log_return(1) ** 2).rolling_sum(p("n")).sqrt()
        case "parkinson_vol":
            n = p("n")
            return ((h / low).log() ** 2).rolling_sum(n).truediv(4.0 * math.log(2.0) * n).sqrt()
        case "atr_rel":
            return _wilder(_true_range(), p("n"), 1) / c
        case "rsi":
            return _rsi(p("n"))
        case "macd_rel":
            return _macd_line(p("fast"), p("slow")) / c
        case "macd_hist_rel":
            line = _macd_line(p("fast"), p("slow"))
            signal = _ema(line, p("signal"), start=p("slow") - 1)
            return (line - signal) / c
        case "adx":
            return _adx(p("n"))
        case "ema_dist":
            return c / _ema(c, p("n")) - 1.0
        case "ema_slope":
            e = _ema(c, p("n"))
            return e / e.shift(p("lag")) - 1.0
        case "bb_pctb":
            mid, _sd, width = _bands(p("n"), float(p("k")))
            return _safe_div(c - (mid - width), 2.0 * width, scale=mid)
        case "bb_width":
            mid, _sd, width = _bands(p("n"), float(p("k")))
            return 2.0 * width / mid
        case "zscore":
            n = p("n")
            mid = c.rolling_mean(n)
            return _safe_div(c - mid, c.rolling_std(n, ddof=0), scale=mid)
        case "donchian_pos":
            n = p("n")
            hh, ll = h.rolling_max(n), low.rolling_min(n)
            return _safe_div(c - ll, hh - ll)
        case "volume_rel":
            return _safe_div(v, v.rolling_mean(p("n")))
        case _:
            raise ValueError(f"nieznany wzór cechy {f.name}: {f.formula}")


PAIR_FEATURES: tuple[FeatureDef, ...] = tuple(f for f in FS_1P if f.formula != "corr_btc")
_CORR_DEF = next(f for f in FS_1P if f.formula == "corr_btc")


def _runs(frame: pl.DataFrame) -> list[pl.DataFrame]:
    """Ciągłe odcinki świec (kolejne godziny bez przerwy), z indeksem `_k` w odcinku."""
    if frame.is_empty():
        return []
    marked = frame.with_columns(
        (pl.col("ts").diff() != HOUR_MS).fill_null(True).cum_sum().alias("_run")
    )
    return [
        run.drop("_run").with_columns(pl.int_range(pl.len(), dtype=pl.Int64).alias(_K))
        for run in marked.partition_by("_run", maintain_order=True)
    ]


def _status(value: str, window: int, present: pl.Expr, warm: pl.Expr) -> tuple[pl.Expr, pl.Expr]:
    """Status i wartość wyjściowa (NaN poza `ok`) dla kolumny `value` z oknem `window`."""
    raw = pl.col(value)
    status = (
        pl.when(~present)
        .then(pl.lit("missing_data"))
        .when(_k() < window - 1)
        .then(pl.when(warm).then(pl.lit("warmup")).otherwise(pl.lit("missing_data")))
        .when(raw.is_null() | ~raw.is_finite())
        .then(pl.lit("undefined"))
        .otherwise(pl.lit("ok"))
    )
    out = pl.when(status == "ok").then(raw).otherwise(pl.lit(math.nan))
    return status, out


def _empty_output() -> pl.DataFrame:
    schema: dict[str, type[pl.DataType]] = {"as_of": pl.Int64, "data_cutoff": pl.Int64}
    for f in FS_1P:
        schema[f.name] = pl.Float64
        schema[status_column(f.name)] = pl.String
    return pl.DataFrame(schema=schema)


def _grid(bars: pl.DataFrame, start: int, end_ts_ms: int) -> pl.DataFrame:
    hours = pl.DataFrame({"ts": pl.int_range(start, end_ts_ms + HOUR_MS, HOUR_MS, eager=True)})
    return hours.join(bars, on="ts", how="left", maintain_order="left")


def _pair_block(bars: pl.DataFrame, grid: pl.DataFrame, first_ts: int) -> pl.DataFrame:
    computed = [
        run.with_columns(
            pl.lit(run["ts"][0] == first_ts).alias("_warm"),
            *[_feature_expr(f).alias(f.name) for f in PAIR_FEATURES],
        ).select("ts", _K, "_warm", *[f.name for f in PAIR_FEATURES])
        for run in _runs(bars)
    ]
    joined = grid.select("ts", "close").join(
        pl.concat(computed), on="ts", how="left", maintain_order="left"
    )
    present = pl.col("close").is_not_null()
    exprs: list[pl.Expr] = []
    for f in PAIR_FEATURES:
        status, out = _status(f.name, f.window, present, pl.col("_warm"))
        exprs.extend([out.alias(f.name), status.alias(status_column(f.name))])
    return joined.select("ts", *exprs)


def _corr_block(
    bars: pl.DataFrame, grid: pl.DataFrame, btc_bars: pl.DataFrame | None, *, is_btc: bool
) -> pl.DataFrame:
    name, window, n = _CORR_DEF.name, _CORR_DEF.window, _CORR_DEF.param("n")
    if is_btc:
        return grid.select(
            "ts",
            pl.lit(math.nan).alias(name),
            pl.lit("not_applicable").alias(status_column(name)),
        )
    if btc_bars is None or btc_bars.is_empty():
        return grid.select(
            "ts",
            pl.lit(math.nan).alias(name),
            pl.lit("missing_data").alias(status_column(name)),
        )
    btc = btc_bars.select("ts", pl.col("close").alias("btc_close"))
    joint = (
        bars.select("ts", "close").join(btc, on="ts", how="inner", maintain_order="left").sort("ts")
    )
    first_joint = max(int(bars["ts"][0]), int(btc_bars["ts"][0]))
    computed = [
        run.with_columns(
            pl.lit(run["ts"][0] == first_joint).alias("_warm"),
            pl.rolling_corr(
                _log_return(1),
                (pl.col("btc_close") / pl.col("btc_close").shift(1)).log(),
                window_size=n,
            ).alias(name),
        ).select("ts", _K, "_warm", name)
        for run in _runs(joint)
    ]
    base = grid.select("ts").join(btc, on="ts", how="left", maintain_order="left")
    joined = base.join(grid.select("ts", "close"), on="ts", how="left", maintain_order="left")
    if computed:
        joined = joined.join(pl.concat(computed), on="ts", how="left", maintain_order="left")
    else:
        joined = joined.with_columns(
            pl.lit(None, dtype=pl.Int64).alias(_K),
            pl.lit(None, dtype=pl.Boolean).alias("_warm"),
            _null().alias(name),
        )
    present = pl.col("close").is_not_null() & pl.col("btc_close").is_not_null()
    status, out = _status(name, window, present, pl.col("_warm"))
    return joined.select("ts", out.alias(name), status.alias(status_column(name)))


def compute_pair(
    bars: pl.DataFrame,
    *,
    end_ts_ms: int,
    btc_bars: pl.DataFrame | None,
    is_btc: bool,
) -> pl.DataFrame:
    """Cechy `fs-1p` jednej pary dla każdej godziny od pierwszej świecy do `end_ts_ms`.

    `bars` i `btc_bars`: świece z `MarketView.bars` (rosnąco, bez powtórzeń). Kolumny
    wyniku: `as_of`, `data_cutoff` (ms UTC), dla każdej cechy wartość i `<cecha>:status`.
    """
    if bars.is_empty():
        return _empty_output()
    first_ts = int(bars["ts"][0])
    last_ts = int(bars["ts"][-1])
    if end_ts_ms < last_ts:
        raise ValueError(f"end_ts {end_ts_ms} przed ostatnią świecą {last_ts}")
    grid = _grid(bars, first_ts, end_ts_ms)
    pair_block = _pair_block(bars, grid, first_ts)
    corr_block = _corr_block(bars, grid, btc_bars, is_btc=is_btc)
    cutoff = (
        pl.when(pl.col("close").is_not_null())
        .then(pl.col("ts") + HOUR_MS)
        .otherwise(None)
        .forward_fill()
        .alias("data_cutoff")
    )
    head = grid.select("ts", (pl.col("ts") + HOUR_MS).alias("as_of"), cutoff)
    out = head.join(pair_block, on="ts", how="left", maintain_order="left").join(
        corr_block, on="ts", how="left", maintain_order="left"
    )
    columns: list[str] = ["as_of", "data_cutoff"]
    for f in FS_1P:
        columns.extend([f.name, status_column(f.name)])
    return out.select(columns)
