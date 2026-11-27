"""Cechy w chwili `as_of` (na żywo / replay) i pełne przeliczenie historii (zadanie wsadowe).

Obie drogi liczą tą samą funkcją `compute_pair` na danych z `MarketView`, więc wynik
w chwili t nie zależy od tego, czy liczymy na żywo, czy odtwarzamy historię (G5p: test
point-in-time i dwa pełne przeliczenia identyczne bit w bit).
"""

from __future__ import annotations

import hashlib
import math
import struct
from collections.abc import Iterable, Sequence

import polars as pl

from goatcash.features._impl.compute import compute_pair, status_column
from goatcash.features._impl.definitions import FEATURE_NAMES, FS_1P
from goatcash.features._impl.types import FeatureStatus, FeatureVector, Pair
from goatcash.features._impl.view import MarketView, RefCandleSource

BTC = "BTC"


def btc_pair(pair: Pair) -> Pair:
    return Pair(BTC, pair.quote)


def pair_frame(view: MarketView, pair: Pair) -> pl.DataFrame:
    """Cechy pary dla każdej godziny w widoku (do ostatniej zamkniętej przed `as_of`)."""
    bars = view.bars(pair)
    is_btc = pair.base == BTC
    btc_bars = None if is_btc else view.bars(btc_pair(pair))
    return compute_pair(bars, end_ts_ms=view.last_bar_ts_ms, btc_bars=btc_bars, is_btc=is_btc)


def features_at(view: MarketView, pair: Pair) -> FeatureVector:
    """Cechy `fs-1p` pary w chwili `view.as_of_ms` (ostatnia godzina zamknięta w widoku)."""
    frame = pair_frame(view, pair)
    if frame.is_empty():
        return FeatureVector(
            pair=pair,
            as_of_ms=view.as_of_ms,
            data_cutoff_ms=None,
            values=dict.fromkeys(FEATURE_NAMES, math.nan),
            statuses=dict.fromkeys(FEATURE_NAMES, "missing_data"),
        )
    row = frame.row(-1, named=True)
    statuses: dict[str, FeatureStatus] = {name: row[status_column(name)] for name in FEATURE_NAMES}
    return FeatureVector(
        pair=pair,
        as_of_ms=view.as_of_ms,
        data_cutoff_ms=int(row["data_cutoff"]),
        values={name: float(row[name]) for name in FEATURE_NAMES},
        statuses=statuses,
    )


def recompute_history(
    source: RefCandleSource,
    *,
    until_ms: int,
    known_at_ms: int | None = None,
    pairs: Iterable[Pair] | None = None,
) -> pl.DataFrame:
    """Pełne przeliczenie historii: cechy wszystkich par dla każdej godziny do `until_ms`.

    Format długi (jak `feature_values`): base, quote, feature, as_of, data_cutoff, value,
    status; posortowany po (base, quote, feature, as_of).
    """
    view = MarketView(source, until_ms, known_at_ms)
    chosen: Sequence[Pair] = sorted(pairs) if pairs is not None else source.pairs()
    frames: list[pl.DataFrame] = []
    for pair in chosen:
        wide = pair_frame(view, pair)
        if wide.is_empty():
            continue
        for f in FS_1P:
            frames.append(
                wide.select(
                    pl.lit(pair.base).alias("base"),
                    pl.lit(pair.quote).alias("quote"),
                    pl.lit(f.name).alias("feature"),
                    "as_of",
                    "data_cutoff",
                    pl.col(f.name).alias("value"),
                    pl.col(status_column(f.name)).alias("status"),
                )
            )
    if not frames:
        return pl.DataFrame(
            schema={
                "base": pl.String,
                "quote": pl.String,
                "feature": pl.String,
                "as_of": pl.Int64,
                "data_cutoff": pl.Int64,
                "value": pl.Float64,
                "status": pl.String,
            }
        )
    return pl.concat(frames).sort(["base", "quote", "feature", "as_of"])


def values_digest(frame: pl.DataFrame) -> str:
    """SHA-256 wyniku przeliczenia: bity każdej wartości (IEEE 754), status i klucze.

    Porównanie skrótów = porównanie bit w bit (NaN porównywane po bitach, nie przez `==`).
    """
    digest = hashlib.sha256()
    for base, quote, feature, as_of, cutoff, value, status in frame.iter_rows():
        digest.update(f"{base}|{quote}|{feature}|{as_of}|{cutoff}|{status}|".encode())
        digest.update(struct.pack("<d", value))
    return digest.hexdigest()
