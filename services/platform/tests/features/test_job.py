"""Zadanie liczenia cech po `candle.closed` i przeliczenie wsadowe (magazyn w pamięci).

Te same scenariusze na Postgresie: `test_feature_db.py` (marker `db`). Najważniejsze:
cechy zapisywane godzina po godzinie (jak na żywo, po każdym `candle.closed`) są bit w bit
równe pełnemu przeliczeniu historii; ponowne przeliczenie nic nie zmienia i nie wysyła
zdarzeń; `features.ready` v2 zgodne z kontraktem; zapis cech i zdarzeń jest atomowy.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from fs_helpers import BTC, ETH, SOL, T0, H, drop_hours, gbm_bars
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from goatcash.features.api import (
    FEATURE_NAMES,
    FeatureJob,
    FeatureSetMismatchError,
    InMemoryFeatureStore,
    InMemoryRefSource,
    Pair,
    RefBar,
    UnsupportedEventError,
    feature_set_definition,
    feature_set_version,
    recompute_history,
    values_digest,
)
from goatcash.marketdata.api import OutboxEvent, envelope, uuid7

CONTRACTS = Path(__file__).resolve().parents[4] / "packages" / "contracts" / "events"
ASSETS = {"USDT": 1, "BTC": 2, "ETH": 3, "SOL": 4}
N = 260


def contract(event_type: str, version: int) -> Draft202012Validator:
    schemas = [json.loads(p.read_text("utf-8")) for p in CONTRACTS.glob("*.schema.json")]
    registry = Registry[Any]().with_resources(
        (str(s["$id"]), Resource.from_contents(s)) for s in schemas
    )
    schema = json.loads((CONTRACTS / f"{event_type}.v{version}.schema.json").read_text("utf-8"))
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def candle_event(pair: Pair, ts_ms: int, exchange: str = "okx") -> dict[str, Any]:
    """Koperta `candle.closed` v1 (pola jak z ingestu E4)."""
    event = OutboxEvent(
        event_id=uuid7(ts_ms + H),
        type="candle.closed",
        schema_version=1,
        payload={
            "instrument_id": 1,
            "exchange": exchange,
            "symbol": f"{pair.base}-{pair.quote}",
            "timeframe": "1h",
            "ts": datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat().replace("+00:00", "Z"),
            "open": "1",
            "high": "1",
            "low": "1",
            "close": "1",
            "volume": "1",
            "source": "rest",
        },
        occurred_at=datetime.fromtimestamp((ts_ms + H) / 1000, tz=UTC),
    )
    return envelope(event, "ingest@0.1.0")


def _data() -> dict[Pair, list[RefBar]]:
    return {
        BTC: gbm_bars(N, seed=31, price=40_000.0),
        ETH: drop_hours(gbm_bars(N, seed=32, price=2_500.0), [20, 21]),
        SOL: gbm_bars(N - 30, seed=33, price=20.0, start_ms=T0 + 30 * H),
    }


def _job(data: dict[Pair, list[RefBar]] | None = None) -> tuple[FeatureJob, InMemoryFeatureStore]:
    store = InMemoryFeatureStore(ASSETS)
    clock = iter(range(T0 + 10 * N * H, T0 + 10 * N * H + 10**9, 1000))
    job = FeatureJob(
        store, InMemoryRefSource(data or _data()), code_version="test", now_ms=lambda: next(clock)
    )
    return job, store


def test_candle_closed_writes_features_and_contract_event() -> None:
    job, store = _job()
    ts = T0 + 200 * H
    trigger = candle_event(ETH, ts)
    events = job.on_candle_closed(trigger)
    assert len(events) == 1
    frame = store.values(job.feature_set_id)
    assert frame.height == len(FEATURE_NAMES)
    assert set(frame["as_of"].to_list()) == {ts + H}
    doc = envelope(events[0], "worker@0.1.0")
    assert list(contract("features.ready", 2).iter_errors(doc)) == []  # pyright: ignore[reportUnknownMemberType]
    assert doc["correlation_id"] == trigger["event_id"]  # skutek konkretnego candle.closed
    assert doc["payload"]["asset_id"] == ASSETS["ETH"]
    assert doc["payload"]["quote_asset_id"] == ASSETS["USDT"]
    assert doc["payload"]["ok_count"] == len(FEATURE_NAMES)  # 200 h historii: wszystkie ok
    assert store.outbox == events


def test_same_candle_from_second_exchange_is_idempotent() -> None:
    job, store = _job()
    ts = T0 + 200 * H
    job.on_candle_closed(candle_event(ETH, ts, "okx"))
    before = values_digest(store.values(job.feature_set_id))
    assert job.on_candle_closed(candle_event(ETH, ts, "bybit")) == []  # nic się nie zmieniło
    assert values_digest(store.values(job.feature_set_id)) == before
    assert len(store.outbox) == 1


def test_changed_reference_price_gives_new_event() -> None:
    data = _data()
    job, store = _job(data)
    ts = T0 + 200 * H
    job.on_candle_closed(candle_event(ETH, ts, "okx"))
    # Druga giełda zmienia medianę ceny referencyjnej tej godziny: inne cechy, nowe zdarzenie.
    data[ETH] = [replace(b, close=b.close * 1.001) if b.ts_ms == ts else b for b in data[ETH]]
    job.source = InMemoryRefSource(data)
    assert len(job.on_candle_closed(candle_event(ETH, ts, "bybit"))) == 1
    assert len(store.outbox) == 2


def test_btc_candle_recomputes_correlation_of_other_pairs() -> None:
    data = _data()
    ts = T0 + 220 * H
    # ETH policzone, zanim przyszła cena BTC tej godziny: korelacja bez danych BTC.
    without_btc = {**data, BTC: [b for b in data[BTC] if b.ts_ms != ts]}
    job, store = _job(without_btc)
    job.on_candle_closed(candle_event(ETH, ts))
    eth_corr = store.values(job.feature_set_id).filter(pl.col("feature") == "corr_btc_168h")
    assert eth_corr["status"].to_list() == ["missing_data"]
    job.source = InMemoryRefSource(data)
    events = job.on_candle_closed(candle_event(BTC, ts))
    bases = sorted(e.payload["base"] for e in events)
    assert bases == ["BTC", "ETH", "SOL"]  # SOL liczony pierwszy raz, ETH: nowa korelacja
    eth_corr = store.values(job.feature_set_id).filter(
        (pl.col("feature") == "corr_btc_168h") & (pl.col("base") == "ETH")
    )
    assert eth_corr["status"].to_list() == ["ok"]


def test_hour_by_hour_live_equals_full_recomputation() -> None:
    # Miniatura „live vs replay” (pełny test 7 dni na staging: produkt): cechy zapisane po
    # każdym candle.closed są bit w bit takie jak z pełnego przeliczenia historii.
    data = _data()
    job, store = _job(data)
    for hour in range(N - 80, N):  # ostatnie 80 h: pełne okna 168 h, test szybszy
        for pair in (BTC, ETH, SOL):
            ts = T0 + hour * H
            if any(b.ts_ms == ts for b in data[pair]):
                job.on_candle_closed(candle_event(pair, ts))
    live = store.values(job.feature_set_id)
    batch = recompute_history(InMemoryRefSource(data), until_ms=T0 + N * H)
    keys = live.select("base", "quote", "feature", "as_of")
    expected = batch.join(keys, on=["base", "quote", "feature", "as_of"], how="semi")
    assert live.height == expected.height > 0
    assert values_digest(live) == values_digest(expected)


def test_recompute_writes_history_once() -> None:
    data = _data()
    job, store = _job(data)
    until = T0 + N * H
    changed = job.recompute(until)
    frame = store.values(job.feature_set_id)
    expected = recompute_history(InMemoryRefSource(data), until_ms=until)
    assert values_digest(frame) == values_digest(expected)
    assert changed == expected.select("base", "quote", "as_of").unique().height
    assert job.recompute(until) == 0  # drugie przeliczenie: nic się nie zmienia
    assert values_digest(store.values(job.feature_set_id)) == values_digest(expected)
    assert store.outbox == []  # przeliczenie wsadowe nie wysyła zdarzeń


def test_write_and_outbox_are_atomic() -> None:
    job, store = _job()

    class BrokenError(Exception):
        pass

    def fail(_events: Sequence[OutboxEvent]) -> None:
        raise BrokenError

    store.add_outbox = fail  # type: ignore[method-assign]
    _ = job.feature_set_id
    with pytest.raises(BrokenError):
        job.on_candle_closed(candle_event(ETH, T0 + 200 * H))
    assert store.values(job.feature_set_id).height == 0  # cechy wycofane razem ze zdarzeniem


@pytest.mark.parametrize(
    ("field", "value"),
    [("type", "features.ready"), ("schema_version", 9)],
)
def test_unsupported_events_rejected(field: str, value: object) -> None:
    job, _ = _job()
    with pytest.raises(UnsupportedEventError):
        job.on_candle_closed({**candle_event(ETH, T0), field: value})


def test_unsupported_timeframe_rejected() -> None:
    job, _ = _job()
    event = candle_event(ETH, T0)
    event["payload"] = {**event["payload"], "timeframe": "4h"}
    with pytest.raises(UnsupportedEventError, match="interwał"):
        job.on_candle_closed(event)


def test_feature_set_registered_with_definition_and_mismatch_detected() -> None:
    store = InMemoryFeatureStore(ASSETS)
    version = feature_set_version()
    sid = store.ensure_feature_set("fs-1p", version, feature_set_definition(), "a")
    assert store.ensure_feature_set("fs-1p", version, feature_set_definition(), "b") == sid
    other = feature_set_definition()
    other["rules_revision"] = 99
    with pytest.raises(FeatureSetMismatchError):
        store.ensure_feature_set("fs-1p", version, other, "a")


def test_pair_without_any_data_writes_nothing() -> None:
    job, store = _job({BTC: gbm_bars(10, seed=1)})
    assert job.on_candle_closed(candle_event(ETH, T0 + 5 * H)) == []
    assert store.values(job.feature_set_id).height == 0
