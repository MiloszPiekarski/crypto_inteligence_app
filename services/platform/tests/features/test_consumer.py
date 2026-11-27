"""Konsument strumienia (ADR-0003, punkt 4) na atrapie Valkey, bez Dockera.

Atrapa odwzorowuje to, z czego korzysta konsument: grupa z listą oczekujących i licznikiem
dostarczeń (XREADGROUP zwiększa go przy pierwszym dostarczeniu, XAUTOCLAIM przy każdym
przejęciu), XACK usuwa z oczekujących. Ten sam scenariusz na prawdziwym Valkey:
`test_feature_db.py` (marker `db`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from goatcash.features.api import DEAD_LETTER, MAX_DELIVERIES, StreamConsumer


class FakeStreams:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.groups: dict[tuple[str, str], int] = {}  # (strumień, grupa) -> ostatni odczytany
        self.pending: dict[str, dict[str, Any]] = {}  # id -> {consumer, idle, delivered}
        self.acked: list[str] = []
        self._seq = 0

    def xgroup_create(
        self, name: str, groupname: str, id: str = "$", mkstream: bool = False
    ) -> bool:
        if (name, groupname) in self.groups:
            raise RuntimeError("BUSYGROUP Consumer Group name already exists")
        self.streams.setdefault(name, [])
        self.groups[(name, groupname)] = 0
        return True

    def xadd(
        self,
        name: str,
        fields: Mapping[str, str],
        *,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        self._seq += 1
        mid = f"{self._seq}-0"
        self.streams.setdefault(name, []).append((mid, dict(fields)))
        return mid

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Mapping[str, str],
        count: int | None = None,
        block: int | None = None,
    ) -> list[Any]:
        out: list[Any] = []
        for name in streams:
            start = self.groups[(name, groupname)]
            fresh = self.streams[name][start : start + (count or 10**9)]
            self.groups[(name, groupname)] = start + len(fresh)
            for mid, _ in fresh:
                self.pending[mid] = {"consumer": consumername, "idle": 0, "delivered": 1}
            if fresh:
                out.append((name, fresh))
        return out

    def xautoclaim(  # noqa: PLR0913, PLR0917 (podpis redis-py)
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str = "0-0",
        count: int | None = None,
    ) -> list[Any]:
        claimed: list[tuple[str, dict[str, str]]] = []
        for mid, fields in self.streams.get(name, []):
            entry = self.pending.get(mid)
            if entry is not None and entry["idle"] >= min_idle_time:
                entry.update(consumer=consumername, idle=0, delivered=entry["delivered"] + 1)
                claimed.append((mid, fields))
        return ["0-0", claimed, []]

    def xpending_range(
        self, name: str, groupname: str, min: str, max: str, count: int
    ) -> list[Any]:
        entry = self.pending.get(min)
        return [] if entry is None else [{"message_id": min, "times_delivered": entry["delivered"]}]

    def xack(self, name: str, groupname: str, *ids: str) -> int:
        for mid in ids:
            self.pending.pop(mid, None)
            self.acked.append(mid)
        return len(ids)

    def age(self, ms: int) -> None:
        for entry in self.pending.values():
            entry["idle"] += ms


def _event(n: int) -> dict[str, str]:
    return {"event": json.dumps({"n": n})}


def test_handled_messages_are_acked_after_effect() -> None:
    fake = FakeStreams()
    seen: list[int] = []
    consumer = StreamConsumer(fake, lambda e: seen.append(e["n"]), consumer="c1")
    consumer.ensure_group()
    consumer.ensure_group()  # grupa już istnieje: bez błędu
    for n in range(3):
        fake.xadd("ev:candle.closed", _event(n))
    assert consumer.step(block_ms=0) == 3
    assert seen == [0, 1, 2]
    assert fake.pending == {}


def test_failure_stays_pending_then_is_retried_after_idle() -> None:
    fake = FakeStreams()
    attempts: list[int] = []

    def flaky(e: dict[str, Any]) -> None:
        attempts.append(e["n"])
        if len(attempts) == 1:
            raise RuntimeError("baza chwilowo niedostępna")

    consumer = StreamConsumer(fake, flaky, consumer="c1")
    consumer.ensure_group()
    fake.xadd("ev:candle.closed", _event(7))
    assert consumer.step(block_ms=0) == 0  # błąd: bez XACK
    assert "1-0" in fake.pending
    assert consumer.step(block_ms=0) == 0  # za wcześnie na przejęcie (< 60 s)
    fake.age(60_000)
    assert consumer.step(block_ms=0) == 1  # przejęte po 60 s i obsłużone
    assert attempts == [7, 7]
    assert fake.pending == {}
    assert DEAD_LETTER not in fake.streams


def test_dead_letter_after_max_deliveries() -> None:
    fake = FakeStreams()

    def broken(_e: dict[str, Any]) -> None:
        raise ValueError("zdarzenie nie do obsłużenia")

    consumer = StreamConsumer(fake, broken, consumer="c1", claim_idle_ms=0)
    consumer.ensure_group()
    fake.xadd("ev:candle.closed", _event(1))
    for _ in range(MAX_DELIVERIES - 1):
        consumer.step(block_ms=0)
        assert DEAD_LETTER not in fake.streams
    consumer.step(block_ms=0)  # piąte dostarczenie
    (dead,) = fake.streams[DEAD_LETTER]
    assert dead[1]["reason"] == "ValueError: zdarzenie nie do obsłużenia"
    assert dead[1]["message_id"] == "1-0"
    assert json.loads(dead[1]["event"]) == {"n": 1}
    assert fake.pending == {}


def test_unexpected_group_error_is_raised() -> None:
    class Broken(FakeStreams):
        def xgroup_create(
            self, name: str, groupname: str, id: str = "$", mkstream: bool = False
        ) -> bool:
            raise RuntimeError("NOAUTH")

    with pytest.raises(RuntimeError, match="NOAUTH"):
        StreamConsumer(Broken(), lambda _e: None, consumer="c1").ensure_group()


def test_run_loop_stops_and_calls_hooks() -> None:
    fake = FakeStreams()
    calls: list[str] = []
    steps = iter([False, False, True])
    consumer = StreamConsumer(fake, lambda _e: None, consumer="c1")
    consumer.run(lambda: next(steps), after_step=[lambda: calls.append("relay")])
    assert calls == ["relay", "relay"]


def test_cli_rejects_until_without_timezone_and_missing_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from goatcash.features.__main__ import main  # noqa: PLC0415

    with pytest.raises(SystemExit, match="strefy"):
        main(["recompute", "--until", "2026-11-27T10:00:00"])
    monkeypatch.delenv("GOATCASH_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="GOATCASH_DATABASE_URL"):
        main(["recompute", "--until", "2026-11-27T10:00:00Z"])
    monkeypatch.delenv("GOATCASH_VALKEY_URL", raising=False)
    with pytest.raises(SystemExit, match="GOATCASH_DATABASE_URL"):
        main(["worker"])
