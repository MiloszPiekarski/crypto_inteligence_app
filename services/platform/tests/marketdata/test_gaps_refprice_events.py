"""Detektor luk, cena referencyjna i zdarzenie candle.closed: wartości referencyjne, właściwości."""

from __future__ import annotations

import itertools
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from jsonschema import Draft202012Validator, FormatChecker
from md_helpers import T0, candle
from referencing import Registry, Resource

from goatcash.marketdata._impl.events import STREAM, STREAM_MAXLEN, uuid7
from goatcash.marketdata._impl.gaps import completeness, expected_ts
from goatcash.marketdata._impl.store import CommitBatch
from goatcash.marketdata.api import (
    HOUR_MS,
    Gap,
    InMemoryStore,
    TimeRange,
    candle_closed,
    classify_gap,
    envelope,
    find_gaps,
    reference_candles,
    relay_outbox,
)

H = HOUR_MS
EVENTS = Path(__file__).resolve().parents[4] / "packages/contracts/events"


# --- luki ---


def test_find_gaps_reference() -> None:
    span = TimeRange(T0, T0 + 10 * H)
    present = [T0 + i * H for i in (0, 1, 4, 5, 9)]
    assert find_gaps(present, span, H) == [Gap(T0 + 2 * H, T0 + 4 * H), Gap(T0 + 6 * H, T0 + 9 * H)]
    assert find_gaps([], span, H) == [Gap(T0, T0 + 10 * H)]
    assert find_gaps(range(T0, T0 + 10 * H, H), span, H) == []


def test_expected_ts_aligns_start_up() -> None:
    assert list(expected_ts(TimeRange(T0 + 1, T0 + 3 * H), H)) == [T0 + H, T0 + 2 * H]


@settings(max_examples=200)
@given(st.sets(st.integers(0, 199)), st.integers(1, 200))
def test_gaps_partition_missing_candles(present_idx: set[int], n: int) -> None:
    span = TimeRange(T0, T0 + n * H)
    present = {T0 + i * H for i in present_idx if i < n}
    gaps = find_gaps(present, span, H)
    covered = [ts for g in gaps for ts in range(g.start_ms, g.end_ms, H)]
    assert len(covered) == len(set(covered))  # luki rozłączne
    assert set(covered) | present == set(range(T0, T0 + n * H, H))
    assert not set(covered) & present
    for a, b in itertools.pairwise(gaps):
        assert a.end_ms < b.start_ms  # maksymalne ciągi (między lukami jest świeca)


def test_classify_gap_splits_ours_and_exchange() -> None:
    gap = Gap(T0, T0 + 5 * H)
    exchange_has = {T0 + H: candle(T0 + H, "1"), T0 + 2 * H: candle(T0 + 2 * H, "1")}

    def refetch(r: TimeRange) -> list[Any]:
        return [c for ts, c in exchange_has.items() if r.start_ms <= ts < r.end_ms]

    parts = classify_gap(gap, refetch, H)
    assert [(p.start_ms, p.end_ms, p.kind) for p in parts] == [
        (T0, T0 + H, "exchange"),
        (T0 + H, T0 + 3 * H, "ours"),
        (T0 + 3 * H, T0 + 5 * H, "exchange"),
    ]
    assert [c.ts_ms for c in parts[1].candles] == [T0 + H, T0 + 2 * H]


def test_completeness_reference_values() -> None:
    # 1000 oczekiwanych, 10 po stronie giełdy, zapisane 989: 989 / 990.
    assert completeness(1000, 989, 10) == pytest.approx(989 / 990)
    assert completeness(0, 0, 0) == 1.0
    with pytest.raises(ValueError, match="niespójne"):
        completeness(10, 11, 0)


# --- cena referencyjna ---


def test_reference_median_of_two_is_mean_exactly() -> None:
    a = candle(T0, "100.1", spread="0.01", volume="2")
    b = candle(T0, "100.4", exchange="bybit", spread="0.02", volume="3")
    (ref,) = reference_candles([a, b])
    assert ref.close == Decimal("100.25")
    assert ref.open == Decimal("100.25")
    assert ref.high == (a.high + b.high) / 2
    assert ref.low == (a.low + b.low) / 2
    assert ref.volume == Decimal("2.5")
    assert ref.sources == ("bybit", "okx")
    assert ref.source == "median"
    assert (ref.base, ref.quote, ref.ts_ms) == ("BTC", "USDT", T0)


def test_reference_single_source_is_annotated_copy() -> None:
    a = candle(T0, "99.5")
    (ref,) = reference_candles([a])
    assert (ref.close, ref.sources, ref.source) == (Decimal("99.5"), ("okx",), "single")


def test_reference_median_of_three_is_middle() -> None:
    cs = [candle(T0, p, exchange=e) for p, e in (("1", "a"), ("5", "b"), ("2", "c"))]
    assert reference_candles(cs)[0].close == Decimal(2)


def test_reference_rejects_two_candles_of_one_exchange() -> None:
    with pytest.raises(ValueError, match="dwie świece"):
        reference_candles([candle(T0, "1"), candle(T0, "2")])


@given(
    st.lists(st.decimals(min_value="0.0001", max_value="100000", places=4), min_size=2, max_size=2)
)
def test_reference_between_sources(prices: list[Decimal]) -> None:
    cs = [candle(T0, p, exchange=e) for p, e in zip(prices, ("okx", "bybit"), strict=True)]
    (ref,) = reference_candles(cs)
    assert min(prices) <= ref.close <= max(prices)
    assert ref.low <= ref.close <= ref.high


# --- candle.closed ---


def validator() -> Draft202012Validator:
    schemas = [json.loads(p.read_text("utf-8")) for p in EVENTS.glob("*.schema.json")]
    registry = Registry[Any]().with_resources(
        (str(s["$id"]), Resource.from_contents(s)) for s in schemas
    )
    schema = json.loads((EVENTS / "candle.closed.v1.schema.json").read_text("utf-8"))
    return Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())


def test_candle_closed_envelope_matches_contract() -> None:
    c = candle(T0, "0.00001234", volume="0")
    event = candle_closed(c, 7, source="okx-rest", now_ms=T0 + H + 5000)
    env = envelope(event, "ingest@0.1.0")
    validator().validate(env)  # pyright: ignore[reportUnknownMemberType]
    assert env["payload"]["close"] == "0.00001234"  # bez notacji wykładniczej
    assert env["payload"]["ts"] == "2024-01-01T00:00:00Z"
    assert env["payload"]["symbol"] == "BTC-USDT"
    assert env["occurred_at"] == "2024-01-01T01:00:05Z"


@given(st.integers(min_value=0, max_value=2**48 - 1))
def test_uuid7_layout(ts: int) -> None:
    u = uuid7(ts)
    assert u.version == 7
    assert u.variant == uuid.RFC_4122
    assert u.int >> 80 == ts


class FakeStream:
    def __init__(self) -> None:
        self.added: list[tuple[str, dict[str, str], int | None, bool]] = []

    def xadd(
        self, name: str, fields: Any, *, maxlen: int | None = None, approximate: bool = True
    ) -> str:
        self.added.append((name, dict(fields), maxlen, approximate))
        return f"{len(self.added)}-0"


def test_relay_publishes_in_order_and_marks_published() -> None:
    store = InMemoryStore()

    events = [
        candle_closed(candle(T0 + i * H, "1"), 1, source="okx-rest", now_ms=T0) for i in range(3)
    ]
    store.commit(CommitBatch(outbox=events))
    stream = FakeStream()
    assert (
        relay_outbox(
            store, stream, producer="ingest@t", batch=2, now=datetime(2024, 1, 1, tzinfo=UTC)
        )
        == 3
    )
    assert [json.loads(f["event"])["event_id"] for _, f, _, _ in stream.added] == [
        str(e.event_id) for e in events
    ]
    assert {(n, m, a) for n, _, m, a in stream.added} == {(STREAM, STREAM_MAXLEN, True)}
    assert store.unpublished(10) == []
    assert relay_outbox(store, stream, producer="ingest@t") == 0  # nic do ponownej publikacji
