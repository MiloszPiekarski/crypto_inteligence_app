"""Proces ingest (cykl, pętla, dq_status) i raport danych G4p (kryteria i kod wyjścia)."""

from __future__ import annotations

from pathlib import Path

import pytest
from md_helpers import FakeSource, gbm_series, mirror

from goatcash.marketdata._impl import runtime
from goatcash.marketdata._impl.runtime import (
    next_cycle_ms,
    print_report,
    report_rows,
    run_cycle,
    serve,
    status_of,
)
from goatcash.marketdata._impl.universe import Asset, Universe
from goatcash.marketdata.api import HOUR_MS, Ingest, InMemoryStore, SourceUnavailableError

H = HOUR_MS
START = 1_672_531_200_000  # 2023-01-01T00:00:00Z
HOURS = 300


def universe() -> Universe:
    return Universe(
        start_ms=START,
        timeframe="1h",
        exchanges=("okx", "bybit"),
        quote=Asset("USDT", "Tether", "tether"),
        bases=(Asset("BTC", "Bitcoin", "bitcoin"), Asset("ETH", "Ethereum", "ethereum")),
    )


class Clock:
    def __init__(self, now: int) -> None:
        self.now = now

    def __call__(self) -> int:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += int(seconds * 1000)


def setup(
    *, broken: str | None = None, missing: set[int] | None = None, clock: Clock | None = None
) -> tuple[Ingest, InMemoryStore, Clock]:
    clk = clock or Clock(START + HOURS * H + 5 * 60_000)
    okx = [
        *gbm_series(HOURS + 48, seed=1, t0=START),
        *gbm_series(HOURS + 48, seed=2, t0=START, symbol="ETH-USDT"),
    ]
    bybit = mirror(okx, exchange="bybit", seed=3)

    okx_source = FakeSource("okx", okx, missing=missing or set())
    if broken is not None:
        # Awaria tylko dla jednej pary: atrapa rzuca błąd przy pytaniu o tę parę.
        original = okx_source.candles

        def candles(symbol: str, timeframe: str, time_range: object) -> list[object]:
            if symbol == broken:
                raise SourceUnavailableError("okx: przerwa testowa")
            return original(symbol, timeframe, time_range)  # type: ignore[arg-type]

        okx_source.candles = candles  # type: ignore[method-assign]
    store = InMemoryStore()
    ing = Ingest(
        store=store,
        sources={"okx": okx_source, "bybit": FakeSource("bybit", bybit)},  # pyright: ignore[reportArgumentType]
        universe=universe(),
        producer="ingest@test",
        now_ms=clk,
        window_ms=100 * H,
    )
    return ing, store, clk


def test_cycle_writes_all_pairs_and_sets_status() -> None:
    ing, store, _ = setup()
    published: list[int] = []
    result = run_cycle(ing, store, lambda: published.append(1) or 0, log=lambda _: None)
    assert result.failed_pairs == {}
    assert result.written == 2 * 2 * HOURS
    assert published == [1]
    assert {k: s.status for k, s in store.statuses.items()} == {
        (ex, sym): "ok" for ex in ("okx", "bybit") for sym in ("BTC-USDT", "ETH-USDT")
    }
    assert all(s.completeness == 1.0 for s in store.statuses.values())
    assert all(s.last_ts_ms == START + (HOURS - 1) * H for s in store.statuses.values())


def test_failure_of_one_pair_does_not_stop_others() -> None:
    ing, store, _ = setup(broken="ETH-USDT")
    logs: list[str] = []
    result = run_cycle(ing, store, lambda: 0, log=logs.append)
    assert list(result.failed_pairs) == ["ETH-USDT"]
    assert "SourceUnavailableError" in result.failed_pairs["ETH-USDT"]
    assert any("ETH-USDT BŁĄD" in line for line in logs)
    assert {sym for (_, sym, _) in store.candles} == {"BTC-USDT"}


def test_exchange_gap_is_described_and_status_ok() -> None:
    ing, store, _ = setup(missing={START + 100 * H})
    run_cycle(ing, store, lambda: 0, log=lambda _: None)
    report = {(r.exchange, r.symbol): r for r in report_rows(store, ing.universe, ing.now_ms())}
    okx_btc = report[("okx", "BTC-USDT")]
    assert okx_btc.exchange_missing == 1
    assert okx_btc.unexplained == 0
    assert okx_btc.problems == ()
    assert store.statuses[("okx", "BTC-USDT")].status == "ok"


def test_serve_runs_hourly_after_offset_and_beats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    beat_file = tmp_path / "hb"
    monkeypatch.setattr(runtime, "HEARTBEAT", beat_file)
    clk = Clock(START + HOURS * H + 5 * 60_000)
    ing, store, _ = setup(clock=clk)
    cycles: list[int] = []

    def publish() -> int:
        cycles.append(clk.now)
        return 0

    beats: list[int] = []
    monkeypatch.setattr(runtime, "beat", lambda path=beat_file: beats.append(clk.now))
    serve(ing, store, publish, sleep=clk.sleep, cycles=2, log=lambda _: None)
    assert len(cycles) == 2
    assert cycles[1] == START + (HOURS + 1) * H + 2 * 60_000  # pełna godzina + 2 min
    assert len(beats) >= 55  # co minutę w oczekiwaniu i po każdej parze


def test_next_cycle_reference() -> None:
    assert next_cycle_ms(START) == START + H + 120_000
    assert next_cycle_ms(START + H - 1) == START + H + 120_000


def test_status_of_reference() -> None:
    ing, store, _ = setup()
    run_cycle(ing, store, lambda: 0, log=lambda _: None)
    from goatcash.marketdata.api import instrument_report  # noqa: PLC0415

    r = instrument_report(store, "okx", "BTC-USDT", ing.now_ms())
    assert status_of(r).status == "ok"
    assert (
        status_of(instrument_report(store, "okx", "BTC-USDT", ing.now_ms() + 3 * H)).status
        == "stale"
    )
    assert status_of(instrument_report(InMemoryStore(), "okx", "BTC-USDT", 0)).status == "down"


def test_report_ok_and_failures_exit_codes() -> None:
    ing, store, _ = setup()
    run_cycle(ing, store, lambda: 0, log=lambda _: None)
    lines: list[str] = []
    assert (
        print_report(report_rows(store, ing.universe, ing.now_ms()), ing.universe, lines.append)
        == 0
    )
    assert lines[-1] == "RAPORT WYNIK: OK"
    # Świeca zgubiona po zapisie, bez przebiegu detektora: brak opisu → kod 1.
    del store.candles[("bybit", "ETH-USDT", START + 50 * H)]
    lines.clear()
    rows = report_rows(store, ing.universe, ing.now_ms())
    assert print_report(rows, ing.universe, lines.append) == 1
    bad = [r for r in rows if r.problems]
    assert [(r.exchange, r.symbol) for r in bad] == [("bybit", "ETH-USDT")]
    assert "1 brakujących bez opisu" in bad[0].problems[0]
    # Brak ceny referencyjnej (F-06) też jest błędem raportu.
    del store.refs[("BTC", "USDT", START + 10 * H)]
    rows = report_rows(store, ing.universe, ing.now_ms())
    assert any("bez ceny referencyjnej" in p for r in rows for p in r.problems)


def test_report_requires_history_from_universe_start() -> None:
    ing, store, _ = setup()
    run_cycle(ing, store, lambda: 0, log=lambda _: None)
    for ts in range(START, START + 10 * H, H):
        del store.candles[("okx", "BTC-USDT", ts)]
    rows = report_rows(store, ing.universe, ing.now_ms())
    okx_btc = next(r for r in rows if (r.exchange, r.symbol) == ("okx", "BTC-USDT"))
    assert "pierwsza świeca ≠ początek uniwersum" in okx_btc.problems


def test_report_counts_missing_rows_as_failure() -> None:
    ing, store, _ = setup()
    run_cycle(ing, store, lambda: 0, log=lambda _: None)
    rows = report_rows(store, ing.universe, ing.now_ms())[:-1]
    assert print_report(rows, ing.universe, lambda _: None) == 1


def test_connect_rejects_unknown_role() -> None:
    # Rola sprawdzana przed połączeniem: właściciel bazy (`postgres`) jest odrzucony.
    with pytest.raises(ValueError, match="niedozwolona rola"):
        runtime.connect("postgresql://127.0.0.1:1/x", "postgres")


def test_setup_failure_skips_cycle_without_crash() -> None:
    ing, store, _ = setup()

    def boom(symbols: object) -> list[object]:
        raise SourceUnavailableError("okx: 403")

    ing.sources["okx"].instruments = boom  # type: ignore[method-assign]
    logs: list[str] = []
    result = run_cycle(ing, store, lambda: 0, log=logs.append)
    assert result.failed_pairs == {"*": "SourceUnavailableError: okx: 403"}
    assert store.candles == {}
    assert any("instrumenty BŁĄD" in line for line in logs)


def test_paused_serve_does_not_call_exchanges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clk = Clock(START + HOURS * H)
    ing, store, _ = setup(clock=clk)
    monkeypatch.setattr(runtime, "beat", lambda path=tmp_path: None)
    calls: list[int] = []
    serve(
        ing,
        store,
        lambda: calls.append(1) or 0,
        sleep=clk.sleep,
        cycles=3,
        log=lambda _: None,
        paused=True,
    )
    assert calls == []
    assert store.candles == {}
