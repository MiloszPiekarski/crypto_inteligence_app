"""Niezależna implementacja cech `fs-1p` w czystym Pythonie (pętle, `math.fsum`), bez Polars.

Druga implementacja do wartości referencyjnych G5p (obok TA-Lib): liczy wprost z definicji
w `docs/praca/metody.md` na jednym ciągłym odcinku świec. `None` = brak wartości (przed
końcem okna). Celowo nie dzieli kodu z `goatcash.features`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from goatcash.features.api import RefBar

Series = list[float | None]


def _none(n: int) -> Series:
    return [None] * n


def _mean(xs: Sequence[float]) -> float:
    return math.fsum(xs) / len(xs)


def _pstdev(xs: Sequence[float]) -> float:
    m = _mean(xs)
    return math.sqrt(math.fsum((x - m) ** 2 for x in xs) / len(xs))


def ema(xs: Series, n: int, alpha: float | None = None) -> Series:
    """EMA od średniej prostej pierwszych n ważnych wartości (inicjalizacja jak w TA-Lib)."""
    a = 2.0 / (n + 1) if alpha is None else alpha
    out = _none(len(xs))
    start = next((i for i, x in enumerate(xs) if x is not None), None)
    if start is None or start + n > len(xs):
        return out
    seed_vals = [x for x in xs[start : start + n] if x is not None]
    y = _mean(seed_vals)
    out[start + n - 1] = y
    for i in range(start + n, len(xs)):
        x = xs[i]
        assert x is not None
        y = y + a * (x - y)
        out[i] = y
    return out


def wilder(xs: Series, n: int) -> Series:
    return ema(xs, n, alpha=1.0 / n)


def true_range(bars: Sequence[RefBar]) -> Series:
    out = _none(len(bars))
    for i in range(1, len(bars)):
        b, pc = bars[i], bars[i - 1].close
        out[i] = max(b.high - b.low, abs(b.high - pc), abs(b.low - pc))
    return out


def log_return(closes: Sequence[float], n: int) -> Series:
    return [math.log(closes[i] / closes[i - n]) if i >= n else None for i in range(len(closes))]


def realized_vol(closes: Sequence[float], n: int) -> Series:
    r = log_return(closes, 1)
    out = _none(len(closes))
    for i in range(n, len(closes)):
        window = [x for x in r[i - n + 1 : i + 1] if x is not None]
        out[i] = math.sqrt(math.fsum(x * x for x in window))
    return out


def parkinson_vol(bars: Sequence[RefBar], n: int) -> Series:
    out = _none(len(bars))
    for i in range(n - 1, len(bars)):
        s = math.fsum(math.log(b.high / b.low) ** 2 for b in bars[i - n + 1 : i + 1])
        out[i] = math.sqrt(s / (4.0 * math.log(2.0) * n))
    return out


def rsi(closes: Sequence[float], n: int) -> Series:
    gains: Series = [None] + [max(closes[i] - closes[i - 1], 0.0) for i in range(1, len(closes))]
    losses: Series = [None] + [max(closes[i - 1] - closes[i], 0.0) for i in range(1, len(closes))]
    ag, al = wilder(gains, n), wilder(losses, n)
    out = _none(len(closes))
    for i, (g, lo) in enumerate(zip(ag, al, strict=True)):
        if g is not None and lo is not None:
            out[i] = 50.0 if g + lo == 0 else 100.0 * g / (g + lo)
    return out


def adx(bars: Sequence[RefBar], n: int) -> Series:
    """ADX Wildera z sumami jak w TA-Lib: start z sumy n-1 wartości, potem S - S/n + x."""
    size = len(bars)
    out = _none(size)
    if size < 2 * n:
        return out
    tr = true_range(bars)
    pdm: list[float] = [0.0] * size
    mdm: list[float] = [0.0] * size
    for i in range(1, size):
        up = bars[i].high - bars[i - 1].high
        dn = bars[i - 1].low - bars[i].low
        if dn > 0 and up < dn:
            mdm[i] = dn
        elif up > 0 and up > dn:
            pdm[i] = up
    sp = math.fsum(pdm[1:n])
    sm = math.fsum(mdm[1:n])
    st = math.fsum(x for x in tr[1:n] if x is not None)
    dxs: list[float] = []
    adx_val: float | None = None
    for i in range(n, size):
        t = tr[i]
        assert t is not None
        sp = sp - sp / n + pdm[i]
        sm = sm - sm / n + mdm[i]
        st = st - st / n + t
        pdi, mdi = 100.0 * sp / st, 100.0 * sm / st
        dx = 0.0 if pdi + mdi == 0 else 100.0 * abs(pdi - mdi) / (pdi + mdi)
        if adx_val is None:
            dxs.append(dx)
            if len(dxs) == n:
                adx_val = math.fsum(dxs) / n
                out[i] = adx_val
        else:
            adx_val = (adx_val * (n - 1) + dx) / n
            out[i] = adx_val
    return out


def _rolling(xs: Sequence[float], n: int, fn: Callable[[Sequence[float]], float | None]) -> Series:
    return [fn(xs[i - n + 1 : i + 1]) if i >= n - 1 else None for i in range(len(xs))]


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def features(bars: Sequence[RefBar], btc_closes: Sequence[float] | None) -> dict[str, Series]:
    """Cechy `fs-1p` dla ciągłego odcinka `bars` (BTC: odcinek o tych samych godzinach)."""
    c = [b.close for b in bars]
    size = len(c)
    out: dict[str, Series] = {}
    for n in (1, 4, 24, 168):
        out[f"ret_log_{n}h"] = log_return(c, n)
    out["vol_realized_24h"] = realized_vol(c, 24)
    out["vol_parkinson_24h"] = parkinson_vol(bars, 24)
    atr = wilder(true_range(bars), 14)
    out["atr_14_rel"] = [None if a is None else a / c[i] for i, a in enumerate(atr)]
    out["rsi_14"] = rsi(c, 14)
    cs: Series = list(c)
    e12, e26 = ema(cs, 12), ema(cs, 26)
    macd: Series = [
        None if a is None or b is None else a - b for a, b in zip(e12, e26, strict=True)
    ]
    sig = ema(macd, 9)
    out["macd_rel"] = [None if m is None else m / c[i] for i, m in enumerate(macd)]
    out["macd_hist_rel"] = [
        None if m is None or s is None else (m - s) / c[i]
        for i, (m, s) in enumerate(zip(macd, sig, strict=True))
    ]
    out["adx_14"] = adx(bars, 14)
    e20, e50 = ema(cs, 20), ema(cs, 50)
    out["ema_20_dist"] = [None if e is None else c[i] / e - 1.0 for i, e in enumerate(e20)]
    slope = _none(size)
    for i in range(24, size):
        now, before = e50[i], e50[i - 24]
        if now is not None and before is not None:
            slope[i] = now / before - 1.0
    out["ema_50_slope_24h"] = slope

    def pctb(w: Sequence[float]) -> float | None:
        m, s = _mean(w), _pstdev(w)
        return _ratio(w[-1] - (m - 2 * s), 4 * s)

    def width(w: Sequence[float]) -> float | None:
        return 4 * _pstdev(w) / _mean(w)

    def zscore(w: Sequence[float]) -> float | None:
        return _ratio(w[-1] - _mean(w), _pstdev(w))

    out["bb_pctb_20"] = _rolling(c, 20, pctb)
    out["bb_width_20"] = _rolling(c, 20, width)
    out["zscore_close_168h"] = _rolling(c, 168, zscore)
    donch = _none(size)
    for i in range(167, size):
        hh = max(b.high for b in bars[i - 167 : i + 1])
        ll = min(b.low for b in bars[i - 167 : i + 1])
        donch[i] = _ratio(c[i] - ll, hh - ll)
    out["donchian_pos_168h"] = donch
    vols = [b.volume for b in bars]
    out["volume_rel_168h"] = _rolling(vols, 168, lambda w: _ratio(w[-1], _mean(w)))
    corr = _none(size)
    if btc_closes is not None:
        rp = log_return(c, 1)
        rb = log_return(btc_closes, 1)
        for i in range(168, size):
            xs = [x for x in rp[i - 167 : i + 1] if x is not None]
            ys = [y for y in rb[i - 167 : i + 1] if y is not None]
            mx, my = _mean(xs), _mean(ys)
            cov = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
            vx = math.fsum((x - mx) ** 2 for x in xs)
            vy = math.fsum((y - my) ** 2 for y in ys)
            corr[i] = None if vx == 0 or vy == 0 else cov / math.sqrt(vx * vy)
    out["corr_btc_168h"] = corr
    return out
