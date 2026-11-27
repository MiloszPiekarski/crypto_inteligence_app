"""Konsument strumienia Valkey dla zadania cech (ADR-0003, punkt 4).

Grupa konsumentów (`XREADGROUP`), potwierdzenie `XACK` dopiero po skutku (zapis cech
i outbox w jednej transakcji), wiadomości zawieszone dłużej niż 60 s przejmuje konsument
(`XAUTOCLAIM`), a po 5 nieudanych dostarczeniach komunikat trafia do `ev:dead-letter`
z powodem i jest potwierdzany. Obsługa jest idempotentna: ponowne przeliczenie tych
samych danych niczego nie zmienia i nie wysyła zdarzeń.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

GROUP = "features"
STREAM_IN = "ev:candle.closed"
DEAD_LETTER = "ev:dead-letter"
CLAIM_IDLE_MS = 60_000
MAX_DELIVERIES = 5
DEAD_LETTER_MAXLEN = 10_000

Message = tuple[str, Mapping[str, str]]


class StreamGroupClient(Protocol):
    """Część klienta Valkey (redis-py, `decode_responses=True`) używana przez konsumenta."""

    def xgroup_create(
        self, name: str, groupname: str, id: str = ..., mkstream: bool = ...
    ) -> Any: ...

    def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: Mapping[str, str],
        count: int | None = ...,
        block: int | None = ...,
    ) -> Any: ...

    def xautoclaim(  # noqa: PLR0913, PLR0917 (podpis redis-py)
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str = ...,
        count: int | None = ...,
    ) -> Any: ...

    def xpending_range(self, name: str, groupname: str, min: str, max: str, count: int) -> Any: ...

    def xack(self, name: str, groupname: str, *ids: str) -> Any: ...

    def xadd(
        self,
        name: str,
        fields: Mapping[str, str],
        *,
        maxlen: int | None = ...,
        approximate: bool = ...,
    ) -> Any: ...


class StreamConsumer:
    """Pętla jednego konsumenta grupy `features` na strumieniu `ev:candle.closed`."""

    def __init__(  # noqa: PLR0913 (zależności konsumenta)
        self,
        client: StreamGroupClient,
        handler: Callable[[dict[str, Any]], object],
        *,
        consumer: str,
        stream: str = STREAM_IN,
        group: str = GROUP,
        claim_idle_ms: int = CLAIM_IDLE_MS,
    ) -> None:
        self.client = client
        self.handler = handler
        self.consumer = consumer
        self.stream = stream
        self.group = group
        self.claim_idle_ms = claim_idle_ms

    def ensure_group(self) -> None:
        try:
            self.client.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception as exc:  # grupa już istnieje (BUSYGROUP)
            if "BUSYGROUP" not in str(exc):
                raise

    def _deliveries(self, message_id: str) -> int:
        pending = self.client.xpending_range(
            self.stream, self.group, min=message_id, max=message_id, count=1
        )
        return int(pending[0]["times_delivered"]) if pending else 1

    def _handle(self, message_id: str, fields: Mapping[str, str]) -> bool:
        """True: obsłużone (potwierdzone, także do dead-letter); False: zostaje w oczekujących."""
        try:
            self.handler(json.loads(fields["event"]))
        except Exception as exc:
            if self._deliveries(message_id) < MAX_DELIVERIES:
                return False  # przejmie go XAUTOCLAIM po claim_idle_ms
            self.client.xadd(
                DEAD_LETTER,
                {
                    "stream": self.stream,
                    "group": self.group,
                    "message_id": message_id,
                    "event": fields.get("event", ""),
                    "reason": f"{type(exc).__name__}: {exc}"[:500],
                },
                maxlen=DEAD_LETTER_MAXLEN,
                approximate=True,
            )
        self.client.xack(self.stream, self.group, message_id)
        return True

    @staticmethod
    def _messages(raw: Any) -> list[Message]:
        if not raw:
            return []
        out: list[Message] = []
        for _stream, entries in raw:
            out.extend((str(mid), fields) for mid, fields in entries)
        return out

    def step(self, *, block_ms: int = 5_000, count: int = 50) -> int:
        """Jedna runda: przejęte zawieszone, potem nowe; zwraca liczbę potwierdzonych."""
        claimed = self.client.xautoclaim(
            self.stream, self.group, self.consumer, self.claim_idle_ms, start_id="0-0", count=count
        )
        batch: list[Message] = [(str(mid), f) for mid, f in claimed[1] if f is not None]
        fresh = self.client.xreadgroup(
            self.group, self.consumer, {self.stream: ">"}, count=count, block=block_ms
        )
        batch.extend(self._messages(fresh))
        return sum(1 for mid, fields in batch if self._handle(mid, fields))

    def run(
        self, should_stop: Callable[[], bool], *, after_step: Sequence[Callable[[], object]] = ()
    ) -> None:
        self.ensure_group()
        while not should_stop():
            self.step()
            for hook in after_step:
                hook()
