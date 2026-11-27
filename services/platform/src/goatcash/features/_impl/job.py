"""Zadanie liczenia cech (roadmapa E5, zakres 7 i punkt 4 ścieżki pracy).

- `on_candle_closed`: po `candle.closed` (świeca 1 h jednej giełdy) liczy cechy pary w chwili
  `as_of = ts + 1 h` przez `MarketView(as_of)`, zapisuje je i, jeśli coś się zmieniło,
  dodaje `features.ready` v2 do outbox w tej samej transakcji. Obie giełdy wysyłają
  `candle.closed` dla tej samej godziny: drugie przeliczenie albo nic nie zmienia (bez
  zdarzenia), albo uwzględnia cenę referencyjną z dwóch giełd (nowe zdarzenie). Świeca BTC
  przelicza też pozostałe pary z tym kwotowaniem (korelacja z BTC zależy od BTC).
- `recompute`: pełne przeliczenie historii (zadanie wsadowe), bez zdarzeń: konsumenci
  reagują na nowe dane, a historię czytają z bazy.

Worker na staging uruchamiamy dopiero w E7 (decyzja właściciela 27.11.2026, karta E5).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import polars as pl

from goatcash.features._impl.definitions import (
    FEATURE_NAMES,
    FEATURE_SET_NAME,
    feature_set_definition,
    feature_set_version,
)
from goatcash.features._impl.service import BTC, features_at, recompute_history
from goatcash.features._impl.store import LONG_SCHEMA, FeatureStore
from goatcash.features._impl.types import HOUR_MS, FeatureVector, Pair
from goatcash.features._impl.view import MarketView, RefCandleSource
from goatcash.marketdata.api import OutboxEvent, uuid7

FEATURES_READY = "features.ready"
FEATURES_READY_VERSION = 2
CANDLE_CLOSED = "candle.closed"
CANDLE_CLOSED_VERSIONS = (1,)  # obsługiwane wersje wejścia (ADR-0003: bieżąca i poprzednia)


class UnsupportedEventError(ValueError):
    """Zdarzenie innego typu, wersji albo interwału niż obsługiwane przez zadanie cech."""


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat().replace("+00:00", "Z")


def _parse_ms(text: str) -> int:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise UnsupportedEventError(f"czas bez strefy: {text!r}")
    return round(dt.timestamp() * 1000)


def vector_frame(fv: FeatureVector) -> pl.DataFrame:
    """Wektor cech w formacie długim (wiersze `feature_values`)."""
    if fv.data_cutoff_ms is None:
        return pl.DataFrame(schema=LONG_SCHEMA)
    return pl.DataFrame(
        [
            (
                fv.pair.base,
                fv.pair.quote,
                n,
                fv.as_of_ms,
                fv.data_cutoff_ms,
                fv.values[n],
                fv.statuses[n],
            )
            for n in FEATURE_NAMES
        ],
        schema=LONG_SCHEMA,
        orient="row",
    )


def features_ready(
    fv: FeatureVector,
    asset_ids: tuple[int, int],
    *,
    version: str,
    correlation_id: UUID | None,
    now_ms: int,
) -> OutboxEvent:
    """Zdarzenie `features.ready` v2 (packages/contracts/events/features.ready.v2.schema.json)."""
    if fv.data_cutoff_ms is None:
        raise ValueError("features.ready bez danych (data_cutoff)")
    return OutboxEvent(
        event_id=uuid7(now_ms),
        type=FEATURES_READY,
        schema_version=FEATURES_READY_VERSION,
        payload={
            "feature_set": FEATURE_SET_NAME,
            "feature_set_version": version,
            "asset_id": asset_ids[0],
            "quote_asset_id": asset_ids[1],
            "base": fv.pair.base,
            "quote": fv.pair.quote,
            "as_of": _iso(fv.as_of_ms),
            "data_cutoff": _iso(fv.data_cutoff_ms),
            "features_count": len(FEATURE_NAMES),
            "ok_count": sum(1 for s in fv.statuses.values() if s == "ok"),
        },
        occurred_at=datetime.fromtimestamp(now_ms / 1000, tz=UTC),
        correlation_id=correlation_id,
    )


class FeatureJob:
    """Liczenie i zapis cech `fs-1p` (na żywo po `candle.closed` i wsadowo)."""

    def __init__(
        self,
        store: FeatureStore,
        source: RefCandleSource,
        *,
        code_version: str,
        now_ms: Callable[[], int] | None = None,
    ) -> None:
        self.store = store
        self.source = source
        self.code_version = code_version
        self.version = feature_set_version()
        self._now_ms = now_ms or (lambda: round(datetime.now(tz=UTC).timestamp() * 1000))
        self._set_id: int | None = None

    @property
    def feature_set_id(self) -> int:
        if self._set_id is None:
            self._set_id = self.store.ensure_feature_set(
                FEATURE_SET_NAME, self.version, feature_set_definition(), self.code_version
            )
        return self._set_id

    def _pairs_for(self, pair: Pair) -> list[Pair]:
        if pair.base != BTC:
            return [pair]
        return [pair, *(p for p in self.source.pairs() if p.quote == pair.quote and p != pair)]

    def compute_and_store(
        self, pairs: Sequence[Pair], as_of_ms: int, correlation_id: UUID | None
    ) -> list[OutboxEvent]:
        """Cechy par w chwili `as_of`: zapis i zdarzenia dla zmienionych (jedna transakcja)."""
        set_id = self.feature_set_id
        view = MarketView(self.source, as_of_ms)
        events: list[OutboxEvent] = []
        with self.store.transaction():
            for pair in pairs:
                fv = features_at(view, pair)
                ids = self.store.asset_ids(pair)
                if fv.data_cutoff_ms is None or ids is None:
                    continue  # brak jakichkolwiek danych pary: nie ma czego zapisać
                if self.store.upsert_values(set_id, vector_frame(fv)):
                    events.append(
                        features_ready(
                            fv,
                            ids,
                            version=self.version,
                            correlation_id=correlation_id,
                            now_ms=self._now_ms(),
                        )
                    )
            self.store.add_outbox(events)
        return events

    def on_candle_closed(self, event: Mapping[str, Any]) -> list[OutboxEvent]:
        """Obsługa koperty `candle.closed` (kontrakt v1); zwraca dodane `features.ready`."""
        if event.get("type") != CANDLE_CLOSED:
            raise UnsupportedEventError(f"typ {event.get('type')!r}")
        if event.get("schema_version") not in CANDLE_CLOSED_VERSIONS:
            raise UnsupportedEventError(f"wersja {event.get('schema_version')!r}")
        payload: Mapping[str, Any] = event["payload"]
        if payload["timeframe"] != "1h":
            raise UnsupportedEventError(f"interwał {payload['timeframe']!r} (fs-1p: tylko 1h)")
        base, quote = str(payload["symbol"]).split("-")
        as_of = _parse_ms(str(payload["ts"])) + HOUR_MS
        return self.compute_and_store(
            self._pairs_for(Pair(base, quote)), as_of, UUID(str(event["event_id"]))
        )

    def recompute(self, until_ms: int, pairs: Sequence[Pair] | None = None) -> int:
        """Pełne przeliczenie historii do `until_ms` i zapis (bez zdarzeń); liczba zmian."""
        set_id = self.feature_set_id
        chosen = list(pairs) if pairs is not None else list(self.source.pairs())
        changed = 0
        for pair in chosen:
            frame = recompute_history(self.source, until_ms=until_ms, pairs=[pair])
            with self.store.transaction():
                changed += len(self.store.upsert_values(set_id, frame))
        return changed
