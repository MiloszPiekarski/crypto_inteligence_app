"""Zbiór cech `fs-1p` (roadmapa E5, zakres 2 i 4 ścieżki pracy) i jego wersja (hash).

Każda cecha deklaruje okno (`window`: liczba kolejnych świec 1 h do chwili t włącznie,
potrzebnych do pierwszej wartości) i źródła danych. Cechy rekurencyjne (EMA, wygładzanie
Wildera: ATR, RSI, MACD, ADX) startują od początku ciągłego odcinka danych z inicjalizacją
jak w TA-Lib (średnia prosta pierwszych n wartości); po luce startują od nowa.

Wersja zbioru = pierwsze 16 znaków SHA-256 kanonicznego JSON definicji: zmiana czegokolwiek
w definicji (parametr, okno, źródło, rewizja wzoru) daje nową wersję, a stare wartości
w `feature_values` zostają przy starej wersji (`feature_sets`, roadmapa E5, zakres 4).
Wzory: `docs/praca/metody.md`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

FEATURE_SET_NAME = "fs-1p"
TIMEFRAME = "1h"
SOURCE_PAIR = "candles_ref:1h"
SOURCE_BTC = "candles_ref:1h:BTC/<quote>"
# Rewizja reguł wspólnych dla wszystkich cech (statusy, odcinki po lukach, inicjalizacja
# rekurencji). Zmiana tych reguł bez zmiany parametrów cech też musi zmienić wersję.
RULES_REVISION = 1


@dataclass(frozen=True, slots=True)
class FeatureDef:
    name: str
    formula: str  # rodzaj wzoru (implementacja w compute.py)
    params: tuple[tuple[str, int | float], ...]
    window: int
    sources: tuple[str, ...]
    description: str
    revision: int = 1

    def param(self, key: str) -> int:
        value = dict(self.params)[key]
        if not isinstance(value, int):
            raise TypeError(f"{self.name}: parametr {key} nie jest liczbą całkowitą")
        return value

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "formula": self.formula,
            "params": dict(self.params),
            "window": self.window,
            "sources": list(self.sources),
            "revision": self.revision,
        }


def _f(
    name: str,
    formula: str,
    window: int,
    description: str,
    sources: tuple[str, ...] = (SOURCE_PAIR,),
    **params: int | float,
) -> FeatureDef:
    return FeatureDef(
        name=name,
        formula=formula,
        params=tuple(sorted(params.items())),
        window=window,
        sources=sources,
        description=description,
    )


FS_1P: tuple[FeatureDef, ...] = (
    _f("ret_log_1h", "log_return", 2, "ln(c_t / c_{t-1})", n=1),
    _f("ret_log_4h", "log_return", 5, "ln(c_t / c_{t-4})", n=4),
    _f("ret_log_24h", "log_return", 25, "ln(c_t / c_{t-24})", n=24),
    _f("ret_log_168h", "log_return", 169, "ln(c_t / c_{t-168})", n=168),
    _f("vol_realized_24h", "realized_vol", 25, "sqrt(suma r_1h^2 z 24 h)", n=24),
    _f("vol_parkinson_24h", "parkinson_vol", 24, "sqrt(suma ln(H/L)^2 / (4 ln 2 n))", n=24),
    _f("atr_14_rel", "atr_rel", 15, "ATR(14, Wilder) / c_t", n=14),
    _f("rsi_14", "rsi", 15, "RSI(14, Wilder), 0..100", n=14),
    _f("macd_rel", "macd_rel", 26, "(EMA12 - EMA26) / c_t", fast=12, slow=26),
    _f(
        "macd_hist_rel",
        "macd_hist_rel",
        34,
        "(MACD - EMA9(MACD)) / c_t",
        fast=12,
        slow=26,
        signal=9,
    ),
    _f("adx_14", "adx", 28, "ADX(14, Wilder), 0..100", n=14),
    _f("ema_20_dist", "ema_dist", 20, "c_t / EMA20 - 1", n=20),
    _f("ema_50_slope_24h", "ema_slope", 74, "EMA50_t / EMA50_{t-24} - 1", n=50, lag=24),
    _f("bb_pctb_20", "bb_pctb", 20, "(c - dolna) / (górna - dolna), SMA20 +- 2 sigma", n=20, k=2),
    _f("bb_width_20", "bb_width", 20, "(górna - dolna) / SMA20", n=20, k=2),
    _f("zscore_close_168h", "zscore", 168, "(c - SMA168) / sigma168", n=168),
    _f("donchian_pos_168h", "donchian_pos", 168, "(c - min L) / (max H - min L), 168 h", n=168),
    _f("volume_rel_168h", "volume_rel", 168, "v_t / średnia v z 168 h", n=168),
    _f(
        "corr_btc_168h",
        "corr_btc",
        169,
        "korelacja Pearsona r_1h pary i BTC z 168 h (BTC: nie dotyczy)",
        sources=(SOURCE_PAIR, SOURCE_BTC),
        n=168,
    ),
)

FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FS_1P)


def feature_set_definition() -> dict[str, Any]:
    """Kanoniczna definicja zbioru (zapisywana w `feature_sets.definition`)."""
    return {
        "name": FEATURE_SET_NAME,
        "timeframe": TIMEFRAME,
        "rules_revision": RULES_REVISION,
        "features": [f.as_json() for f in FS_1P],
    }


def definition_hash(definition: dict[str, Any]) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()[:16]


def feature_set_version() -> str:
    """Wersja `fs-1p` (hash definicji)."""
    return definition_hash(feature_set_definition())
