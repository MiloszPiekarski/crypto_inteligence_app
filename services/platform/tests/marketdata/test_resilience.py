"""Obsługa 429, błędów sieci, przerwania i wznowienia uzupełniania historii (bramka G4p).

Atrapy działają na poziomie HTTP (sesja ccxt), więc mapowanie odpowiedzi giełdy na wyjątek
robi prawdziwy ccxt (np. 429 OKX → `RateLimitExceeded`), a nie test.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import requests
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from md_helpers import FakeSource, gbm_series, mirror, replay_source

from goatcash.marketdata._impl.cassette import Interaction, ReplaySession
from goatcash.marketdata._impl.record import series_window
from goatcash.marketdata._impl.store import BACKFILL_JOB
from goatcash.marketdata._impl.universe import Asset, Universe
from goatcash.marketdata.api import (
    HOUR_MS,
    Ingest,
    InMemoryStore,
    MarketStore,
    RetryPolicy,
    SourceUnavailableError,
    TimeRange,
)

OKX_429 = Interaction("GET", "", 429, '{"msg":"Too Many Requests","code":"50011"}')
CANDLES = "history-candles"


def fail_first(n: int, response: Interaction = OKX_429):
    """Pierwsze `n` zapytań o świece dostaje podaną odpowiedź (np. 429)."""
    state = {"count": 0}

    def override(method: str, url: str, _: int) -> Interaction | None:
        if CANDLES not in url or state["count"] >= n:
            return None
        state["count"] += 1
        return response

    return override


def test_429_is_retried_with_exponential_backoff() -> None:
    sleeps: list[float] = []
    retry = RetryPolicy(max_attempts=5, base_delay_s=1.0, max_delay_s=60.0, sleep=sleeps.append)
    source, session = replay_source("okx", ["series_BTC-USDT"], override=fail_first(3), retry=retry)
    tr = TimeRange(series_window().start_ms, series_window().start_ms + 100 * HOUR_MS)
    candles = source.candles("BTC-USDT", "1h", tr)
    assert len(candles) == 100
    assert sleeps == [1.0, 2.0, 4.0]  # trzy odpowiedzi 429, potem sukces
    assert sum(1 for _, url in session.requests if CANDLES in url) == 4


def test_429_after_max_attempts_raises_without_partial_result() -> None:
    sleeps: list[float] = []
    retry = RetryPolicy(max_attempts=3, sleep=sleeps.append)
    source, _ = replay_source("okx", ["series_BTC-USDT"], override=fail_first(10), retry=retry)
    with pytest.raises(SourceUnavailableError, match="po 3 próbach"):
        source.candles("BTC-USDT", "1h", series_window())
    assert len(sleeps) == 2


def test_backoff_is_capped() -> None:
    policy = RetryPolicy(base_delay_s=1.0, max_delay_s=60.0)
    assert [policy.delay(i) for i in range(8)] == [1, 2, 4, 8, 16, 32, 60, 60]


def test_network_error_is_retried() -> None:
    state = {"left": 2}

    def override(method: str, url: str, _: int) -> Interaction | None:
        if CANDLES in url and state["left"] > 0:
            state["left"] -= 1
            raise requests.ConnectionError("połączenie zerwane")
        return None

    source, _ = replay_source("okx", ["series_BTC-USDT"], override=override)
    tr = TimeRange(series_window().start_ms, series_window().start_ms + 100 * HOUR_MS)
    assert len(source.candles("BTC-USDT", "1h", tr)) == 100
    assert state["left"] == 0


def test_bad_request_is_not_retried() -> None:
    bad = Interaction("GET", "", 400, '{"msg":"Parameter instId error","code":"51001"}')
    sleeps: list[float] = []
    source, _ = replay_source(
        "okx",
        ["series_BTC-USDT"],
        override=fail_first(1, bad),
        retry=RetryPolicy(sleep=sleeps.append),
    )
    with pytest.raises(Exception) as info:  # noqa: PT011 (dowolny błąd ccxt poza siecią)
        source.candles("BTC-USDT", "1h", series_window())
    assert not isinstance(info.value, SourceUnavailableError)
    assert sleeps == []


# --- przerwanie i wznowienie uzupełniania historii ---

START = series_window().start_ms
HOURS = 2000


def universe() -> Universe:
    return Universe(
        start_ms=START,
        timeframe="1h",
        exchanges=("okx", "bybit"),
        quote=Asset("USDT", "Tether", "tether"),
        bases=(Asset("BTC", "Bitcoin", "bitcoin"),),
    )


def ingest(store: MarketStore, okx: object, bybit: object, window_h: int = 300) -> Ingest:
    ing = Ingest(
        store=store,
        sources={"okx": okx, "bybit": bybit},  # pyright: ignore[reportArgumentType]
        universe=universe(),
        producer="ingest@test",
        now_ms=lambda: START + HOURS * HOUR_MS + 5 * 60_000,
        window_ms=window_h * HOUR_MS,
    )
    ing.setup_instruments()
    return ing


def snapshot(store: InMemoryStore) -> tuple[object, ...]:
    return (
        sorted(store.candles.items()),
        sorted(store.flagged),
        sorted((e.exchange, e.ts_ms, e.kind) for e in store.dq_events),
        sorted(store.refs.items()),
        store.checkpoints,
    )


def real_okx_and_mirror(
    override: Callable[[str, str, int], Interaction | None] | None = None,
) -> tuple[Any, FakeSource, ReplaySession]:
    okx, _ = replay_source("okx", ["series_BTC-USDT"], override=override)
    data = okx.candles("BTC-USDT", "1h", series_window())
    okx_replay, session = replay_source("okx", ["series_BTC-USDT"], override=override)
    return okx_replay, FakeSource("bybit", mirror(data, exchange="bybit", seed=7)), session


def test_backfill_with_429_equals_backfill_without() -> None:
    okx, bybit, _ = real_okx_and_mirror()
    clean = InMemoryStore()
    ingest(clean, okx, bybit).backfill_pair("BTC-USDT")
    okx2, bybit2, _ = real_okx_and_mirror(override=fail_first(4))
    noisy = InMemoryStore()
    ingest(noisy, okx2, bybit2).backfill_pair("BTC-USDT")
    assert snapshot(noisy) == snapshot(clean)
    assert len(clean.candles) >= 2 * 1900
    assert clean.checkpoints[(BACKFILL_JOB, "BTC-USDT")].cursor_ms == START + HOURS * HOUR_MS


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(raw_fail=st.integers(min_value=0, max_value=100), window_h=st.sampled_from([100, 250, 700]))
def test_interrupted_backfill_resumes_to_identical_state(raw_fail: int, window_h: int) -> None:
    """Awaria w dowolnym oknie: brak zapisu połowy okna; wznowienie = przebieg bez awarii."""
    windows = -(-HOURS // window_h)
    fail_at = 1 + raw_fail % windows  # numer okna (jedno wywołanie atrapy na okno)
    okx = gbm_series(HOURS, seed=1, t0=START, exchange="okx")
    bybit = mirror(okx, exchange="bybit", seed=2)
    reference = InMemoryStore()
    ingest(reference, FakeSource("okx", okx), FakeSource("bybit", bybit), window_h).backfill_pair(
        "BTC-USDT"
    )

    store = InMemoryStore()
    failing = FakeSource("okx", okx, fail_on_call=lambda n: n == fail_at)
    with pytest.raises(SourceUnavailableError):
        ingest(store, failing, FakeSource("bybit", bybit), window_h).backfill_pair("BTC-USDT")
    cp = store.checkpoint(BACKFILL_JOB, "BTC-USDT")
    done = 0 if cp is None else (cp.cursor_ms - START) // HOUR_MS
    assert done == (fail_at - 1) * window_h  # zapisane dokładnie pełne okna przed awarią
    assert all(ts < START + done * HOUR_MS for (_, _, ts) in store.candles)
    # Nowy proces (nowy obiekt Ingest), te same dane: wznowienie od punktu kontrolnego.
    ingest(store, FakeSource("okx", okx), FakeSource("bybit", bybit), window_h).backfill_pair(
        "BTC-USDT"
    )
    assert snapshot(store) == snapshot(reference)


def test_second_run_is_noop_until_new_candle_closes() -> None:
    okx = gbm_series(HOURS, seed=3, t0=START)
    bybit = mirror(okx, exchange="bybit", seed=4)
    store = InMemoryStore()
    ing = ingest(store, FakeSource("okx", okx), FakeSource("bybit", bybit))
    first = ing.backfill_pair("BTC-USDT")
    commits = store.commits
    assert ing.backfill_pair("BTC-USDT") == 0
    assert store.commits == commits
    assert first == 2 * HOURS
