"""Dwa pełne przeliczenia historii identyczne bit w bit (G5p, F-08) i wersja zbioru cech.

Przeliczenie: wszystkie pary, każda godzina, 19 cech; porównanie po skrócie SHA-256 bitów
wartości (IEEE 754), statusów i kluczy. Drugie przeliczenie także w osobnym procesie
z jednym wątkiem Polars (inna pula wątków nie może zmienić wyniku).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from fs_helpers import BTC, ETH, SOL, T0, H, drop_hours, gbm_bars, real_series_source

from goatcash.features.api import (
    FEATURE_NAMES,
    FEATURE_SET_NAME,
    FS_1P,
    InMemoryRefSource,
    definition_hash,
    feature_set_definition,
    feature_set_version,
    recompute_history,
    values_digest,
)

HERE = Path(__file__).resolve().parent
UNTIL = T0 + 1200 * H


def _synthetic() -> InMemoryRefSource:
    return InMemoryRefSource(
        {
            BTC: drop_hours(gbm_bars(1200, seed=21, price=40_000.0), [600]),
            ETH: drop_hours(gbm_bars(1200, seed=22, price=2_500.0), range(300, 310)),
            SOL: gbm_bars(1000, seed=23, price=20.0, start_ms=T0 + 200 * H, sigma=0.03),
        }
    )


def test_two_full_recomputations_are_bit_identical() -> None:
    src = _synthetic()
    first = recompute_history(src, until_ms=UNTIL)
    second = recompute_history(src, until_ms=UNTIL)
    assert first.height == 3 * len(FEATURE_NAMES) * 1200 - len(FEATURE_NAMES) * 200
    assert values_digest(first) == values_digest(second)
    # kolejność par na wejściu nie zmienia wyniku
    reordered = recompute_history(src, until_ms=UNTIL, pairs=[SOL, BTC, ETH])
    assert values_digest(reordered) == values_digest(first)


def test_real_prices_recomputation_is_bit_identical() -> None:
    src = real_series_source()
    until = T0 + 2 * 365 * 24 * H  # po końcu serii (2024-07-01 + 2000 h)
    a = recompute_history(src, until_ms=until)
    b = recompute_history(real_series_source(), until_ms=until)
    assert a.height > 0
    assert values_digest(a) == values_digest(b)


def test_recomputation_in_other_process_with_one_polars_thread() -> None:
    expected = values_digest(recompute_history(_synthetic(), until_ms=UNTIL))
    env = {
        **os.environ,
        "POLARS_MAX_THREADS": "1",
        "PYTHONPATH": os.pathsep.join([str(HERE), os.environ.get("PYTHONPATH", "")]),
    }
    code = (
        "from test_determinism import _synthetic, UNTIL\n"
        "from goatcash.features.api import recompute_history, values_digest\n"
        "print(values_digest(recompute_history(_synthetic(), until_ms=UNTIL)))\n"
    )
    out = subprocess.run(  # noqa: S603 (ten sam interpreter, kod testu)
        [sys.executable, "-c", code], env=env, cwd=HERE, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == expected


def test_digest_sees_every_bit_and_status() -> None:
    frame = recompute_history(_synthetic(), until_ms=UNTIL)
    base = values_digest(frame)
    idx = frame["status"].to_list().index("ok")
    value = float(frame["value"][idx])
    nudged = frame.with_columns(frame["value"].scatter(idx, value * (1 + 2**-52)))
    assert values_digest(nudged) != base  # zmiana o 1 ulp
    restatus = frame.with_columns(frame["status"].scatter(idx, "undefined"))
    assert values_digest(restatus) != base


# --- wersjonowanie zbioru cech (feature_sets: hash definicji) ---

# Wersja fs-1p. Zmiana definicji (cecha, parametr, okno, źródło, rewizja wzoru albo reguł)
# zmienia hash; test pilnuje, że to świadoma zmiana (nowa wersja w feature_sets).
FS_1P_VERSION = "66ce07b92a443614"


def test_feature_set_version_is_pinned() -> None:
    assert FEATURE_SET_NAME == "fs-1p"
    assert feature_set_version() == FS_1P_VERSION
    assert len(FS_1P) == 19  # roadmapa: ok. 15-20 cech
    assert len(set(FEATURE_NAMES)) == len(FEATURE_NAMES)


@pytest.mark.parametrize(
    ("index", "key", "value"),
    [
        (0, "params", {"n": 2}),  # parametr
        (6, "window", 16),  # okno
        (18, "sources", ["candles_ref:1h"]),  # źródła
        (3, "revision", 2),  # rewizja wzoru
        (None, "rules_revision", 2),  # reguły wspólne (statusy, odcinki po lukach)
        (None, "features", []),  # usunięte cechy
    ],
)
def test_any_definition_change_gives_new_version(
    index: int | None, key: str, value: object
) -> None:
    definition = feature_set_definition()
    target: dict[str, Any] = definition if index is None else definition["features"][index]
    assert key in target
    target[key] = value
    assert definition_hash(definition) != FS_1P_VERSION


def test_definition_declares_window_and_sources() -> None:
    for f in FS_1P:
        assert f.window >= 2, f.name
        assert f.sources, f.name
        assert all(s.startswith("candles_ref:1h") for s in f.sources), f.name
    corr = next(f for f in FS_1P if f.name == "corr_btc_168h")
    assert len(corr.sources) == 2  # para i BTC
