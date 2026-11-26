"""Pobieranie, luki i raport danych (kryterium G4p: 100% luk opisanych, kompletność ≥ 99,9%).

Scenariusz na atrapach dwóch giełd: giełda nie udostępnia kilku świec (luka po stronie
giełdy), część świec „gubimy” sami (luka nasza: usunięte z magazynu po zapisie), jedna
świeca giełdy jest błędna (odrzucona przez DQ). Raport musi opisać każdą brakującą świecę.
"""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from md_helpers import FakeSource, gbm_series, mirror

from goatcash.marketdata._impl.dq import GAP_EXCHANGE, GAP_OURS, OHLC_INCONSISTENT
from goatcash.marketdata._impl.store import BACKFILL_JOB
from goatcash.marketdata._impl.universe import Asset, Universe
from goatcash.marketdata.api import (
    HOUR_MS,
    Ingest,
    InMemoryStore,
    MarketStore,
    instrument_report,
    load_universe,
)

H = HOUR_MS
START = 1_672_531_200_000  # 2023-01-01T00:00:00Z
HOURS = 1500
NOW = START + HOURS * H + 10 * 60_000


def universe(symbols: tuple[str, ...] = ("BTC",)) -> Universe:
    return Universe(
        start_ms=START,
        timeframe="1h",
        exchanges=("okx", "bybit"),
        quote=Asset("USDT", "Tether", "tether"),
        bases=tuple(Asset(s, s, s.lower()) for s in symbols),
    )


def scenario(
    store: MarketStore | None = None,
) -> tuple[Ingest, InMemoryStore, dict[str, set[int]]]:
    """Scenariusz wspólny z testem na Postgresie (`test_pgstore.py`)."""
    okx = gbm_series(HOURS, seed=11, t0=START)
    bybit = mirror(okx, exchange="bybit", seed=12)
    # Bybit: para notowana dopiero od 50. godziny (przed nią giełda nic nie udostępnia).
    bybit = bybit[50:]
    exchange_missing = {
        "okx": {START + i * H for i in (300, 301, 302, 900)},
        "bybit": {START + 700 * H},
    }
    bad_ts = START + 1200 * H
    okx = [replace(c, high=c.low / 2) if c.ts_ms == bad_ts else c for c in okx]
    target = store if store is not None else InMemoryStore()
    ing = Ingest(
        store=target,
        sources={
            "okx": FakeSource("okx", okx, missing=exchange_missing["okx"]),
            "bybit": FakeSource("bybit", bybit, missing=exchange_missing["bybit"]),
        },  # pyright: ignore[reportArgumentType]
        universe=universe(),
        producer="ingest@test",
        now_ms=lambda: NOW,
        window_ms=400 * H,
    )
    ing.setup_instruments()
    return ing, target, exchange_missing  # pyright: ignore[reportReturnType]


def test_backfill_report_describes_every_missing_candle() -> None:
    ing, store, exchange_missing = scenario()
    ing.backfill_pair("BTC-USDT")
    # Luka nasza: świece zapisane, a potem utracone (np. błąd zapisu w innej wersji kodu).
    lost = {START + i * H for i in (100, 101, 1400)}
    for ts in lost:
        del store.candles[("okx", "BTC-USDT", ts)]
    before = instrument_report(store, "okx", "BTC-USDT", NOW)
    assert set(before.unexplained) == lost | exchange_missing["okx"]  # detektor jeszcze nie działał

    parts = ing.repair_gaps("BTC-USDT", "okx")
    ing.repair_gaps("BTC-USDT", "bybit")
    kinds = sorted((p.kind, (p.end_ms - p.start_ms) // H) for p in parts)
    # Luki: 100-101 (nasza, 2), 300-302 (giełdy, 3), 900 (giełdy, 1), 1200 (nasza: giełda
    # ma świecę, ale błędną → DQ odrzuca), 1400 (nasza, 1).
    assert kinds == [("exchange", 1), ("exchange", 3), ("ours", 1), ("ours", 1), ("ours", 2)]

    okx = instrument_report(store, "okx", "BTC-USDT", NOW)
    assert okx.unexplained == ()
    assert okx.expected == HOURS
    assert okx.exchange_missing == 4
    assert okx.rejected == 1
    assert okx.stored == HOURS - 4 - 1
    assert okx.completeness == (HOURS - 5) / (HOURS - 4)
    assert not okx.stale

    bybit = instrument_report(store, "bybit", "BTC-USDT", NOW)
    assert bybit.first_ts_ms == START + 50 * H  # oczekiwane od pierwszej świecy giełdy
    assert bybit.expected == HOURS - 50
    assert bybit.unexplained == ()
    assert bybit.exchange_missing == 1
    assert bybit.completeness == 1.0

    events = {(e.exchange, e.kind) for e in store.dq_events}
    assert {("okx", GAP_EXCHANGE), ("okx", GAP_OURS), ("okx", OHLC_INCONSISTENT)} <= events


def test_known_exchange_gaps_are_not_requeried() -> None:
    ing, _, _ = scenario()
    ing.backfill_pair("BTC-USDT")
    ing.repair_gaps("BTC-USDT", "okx")
    source = cast(FakeSource, ing.sources["okx"])
    calls = source.calls
    again = ing.repair_gaps("BTC-USDT", "okx")
    # Zostaje tylko świeca, którą giełda udostępnia błędną (odrzuca ją DQ): jedno zapytanie.
    assert [(p.kind, p.start_ms) for p in again] == [("ours", START + 1200 * H)]
    assert source.calls - calls == 1


def test_repaired_candles_get_reference_price_from_both_sources() -> None:
    ing, store, _ = scenario()
    ing.backfill_pair("BTC-USDT")
    ts = START + 600 * H
    del store.candles[("okx", "BTC-USDT", ts)]
    del store.refs[("BTC", "USDT", ts)]
    ing.repair_gaps("BTC-USDT", "okx")
    ref = store.refs[("BTC", "USDT", ts)]
    assert ref.sources == ("bybit", "okx")
    assert ref.source == "median"


def test_reference_for_every_good_candle_time() -> None:
    """F-06 (ścieżka pracy): cena referencyjna dla 100% chwil z poprawną świecą."""
    ing, store, _ = scenario()
    ing.backfill_pair("BTC-USDT")
    good_ts = {ts for (_, _, ts) in store.candles} - {ts for (_, _, ts) in store.flagged}
    assert {ts for (_, _, ts) in store.refs} >= good_ts
    single = [r for r in store.refs.values() if r.source == "single"]
    assert all(len(r.sources) == 1 for r in single)
    assert len(single) >= 50  # pierwsze 50 h: tylko OKX


def test_outbox_only_for_last_day() -> None:
    ing, store, _ = scenario()
    ing.backfill_pair("BTC-USDT")
    payload_ts = {str(ev.payload["ts"]) for _, ev, _ in store.outbox}
    assert 0 < len(store.outbox) <= 2 * 24
    assert all(p.startswith("2023-03-") for p in payload_ts)


def test_setup_requires_pair_on_both_exchanges() -> None:
    ing, _, _ = scenario()
    ing.universe = universe(("BTC", "ETH"))
    with pytest.raises(RuntimeError, match="ETH-USDT"):
        ing.setup_instruments()


def test_report_without_data_is_stale_and_empty() -> None:
    report = instrument_report(InMemoryStore(), "okx", "BTC-USDT", NOW)
    assert report.stale
    assert report.expected == 0


def test_checkpoint_written_with_window() -> None:
    ing, store, _ = scenario()
    ing.backfill_pair("BTC-USDT")
    cp = store.checkpoint(BACKFILL_JOB, "BTC-USDT")
    assert cp is not None
    assert cp.cursor_ms == START + HOURS * H


def test_universe_file_has_20_pairs_on_usdt() -> None:
    u = load_universe()
    assert len(u.symbols) == 20
    assert all(s.endswith("-USDT") for s in u.symbols)
    assert u.exchanges == ("okx", "bybit")
    assert u.start_ms == START
    assert len({a.coingecko_id for a in u.bases}) == 20
