"""Zdarzenie `candle.closed` (kontrakt E2, ADR-0003): koperta, outbox i przekaźnik do Valkey.

Zdarzenie trafia do `event_outbox` w tej samej transakcji co zapis świecy (transactional
outbox). Przekaźnik publikuje nieopublikowane wiersze do strumienia `ev:candle.closed`
(`XADD … MAXLEN ~`) i oznacza je jako opublikowane. Przy awarii między publikacją
a oznaczeniem zdarzenie może zostać opublikowane drugi raz (co najmniej raz); konsumenci
rozpoznają powtórkę po `event_id`.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from goatcash.marketdata._impl.types import Candle, ms_to_datetime

EVENT_TYPE = "candle.closed"
SCHEMA_VERSION = 1
STREAM = f"ev:{EVENT_TYPE}"
# ADR-0003, punkt 5: strumień mieści co najmniej 7 dni ruchu. Ścieżka pracy: 40 instrumentów
# x 24 świece x 7 dni = 6720; zapas x3.
STREAM_MAXLEN = 20_000


def uuid7(now_ms: int | None = None) -> uuid.UUID:
    """UUIDv7 (RFC 9562): 48 bitów czasu w ms, wersja 7, wariant RFC, reszta losowa."""
    ts = int(time.time() * 1000) if now_ms is None else now_ms
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ts & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= (rand >> 68) << 64  # 12 bitów rand_a
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)  # 62 bity rand_b
    return uuid.UUID(int=value)


def _decimal_text(value: Decimal) -> str:
    """Liczba dziesiętna jako tekst bez notacji wykładniczej (kontrakt: ^\\d+(\\.\\d+)?$)."""
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return text


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Wiersz event_outbox przed zapisem."""

    event_id: uuid.UUID
    type: str
    schema_version: int
    payload: Mapping[str, Any]
    occurred_at: datetime


def candle_closed(
    candle: Candle,
    instrument_id: int,
    *,
    source: str,
    now_ms: int | None = None,
) -> OutboxEvent:
    """Zdarzenie `candle.closed` dla zapisanej świecy."""
    occurred_ms = int(time.time() * 1000) if now_ms is None else now_ms
    return OutboxEvent(
        event_id=uuid7(occurred_ms),
        type=EVENT_TYPE,
        schema_version=SCHEMA_VERSION,
        occurred_at=ms_to_datetime(occurred_ms),
        payload={
            "instrument_id": instrument_id,
            "exchange": candle.exchange,
            "symbol": candle.symbol,
            "timeframe": candle.timeframe,
            "ts": _iso(ms_to_datetime(candle.ts_ms)),
            "open": _decimal_text(candle.open),
            "high": _decimal_text(candle.high),
            "low": _decimal_text(candle.low),
            "close": _decimal_text(candle.close),
            "volume": _decimal_text(candle.volume),
            "source": source,
        },
    )


def envelope(event: OutboxEvent, producer: str) -> dict[str, Any]:
    """Koperta zdarzenia (packages/contracts/events/envelope.schema.json)."""
    return {
        "event_id": str(event.event_id),
        "type": event.type,
        "schema_version": event.schema_version,
        "occurred_at": _iso(event.occurred_at),
        "producer": producer,
        # Zdarzenie z ingestu nie jest skutkiem innego zdarzenia: korelacja = ono samo.
        "correlation_id": str(event.event_id),
        "payload": dict(event.payload),
    }


class StreamClient(Protocol):
    """Część klienta Valkey (redis-py) używana przez przekaźnik."""

    def xadd(
        self,
        name: str,
        fields: Mapping[str, str],
        *,
        maxlen: int | None = ...,
        approximate: bool = ...,
    ) -> Any: ...


class OutboxStore(Protocol):
    def unpublished(self, limit: int) -> Sequence[tuple[int, OutboxEvent]]: ...

    def mark_published(self, outbox_ids: Sequence[int], published_at: datetime) -> None: ...


def relay_outbox(
    store: OutboxStore,
    client: StreamClient,
    *,
    producer: str,
    batch: int = 500,
    now: datetime | None = None,
) -> int:
    """Publikuje nieopublikowane zdarzenia (kolejność outbox_id); zwraca ich liczbę."""
    total = 0
    while True:
        rows = store.unpublished(batch)
        if not rows:
            return total
        for _, event in rows:
            client.xadd(
                f"ev:{event.type}",
                {"event": json.dumps(envelope(event, producer), separators=(",", ":"))},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        store.mark_published([oid for oid, _ in rows], now or datetime.now(tz=UTC))
        total += len(rows)
