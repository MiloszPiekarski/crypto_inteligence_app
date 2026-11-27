"""Magazyn cech (`feature_sets`, `feature_values`, `event_outbox`): protokół i wersja w pamięci.

Zapis cech i zdarzeń `features.ready` jest jedną transakcją (transactional outbox,
ADR-0003). `upsert_values` zwraca chwile (para, as_of), w których coś się zmieniło
(wartość bit w bit, status albo `data_cutoff`): ponowne przeliczenie tych samych danych
niczego nie zmienia i nie wysyła zdarzeń (konsument idempotentny).
"""

from __future__ import annotations

import copy
import struct
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from typing import Any, Protocol

import polars as pl

from goatcash.features._impl.types import Pair
from goatcash.marketdata.api import OutboxEvent

LONG_SCHEMA: dict[str, type[pl.DataType]] = {
    "base": pl.String,
    "quote": pl.String,
    "feature": pl.String,
    "as_of": pl.Int64,
    "data_cutoff": pl.Int64,
    "value": pl.Float64,
    "status": pl.String,
}
Changed = set[tuple[str, str, int]]  # (base, quote, as_of)


class FeatureSetMismatchError(RuntimeError):
    """Ta sama nazwa i wersja zbioru cech, a inna definicja (hash nie pasuje do treści)."""


class FeatureStore(Protocol):
    def transaction(self) -> Any:
        """Kontekst jednej transakcji (zapis cech i outbox razem albo nic)."""
        ...

    def ensure_feature_set(
        self, name: str, version: str, definition: dict[str, Any], code_version: str
    ) -> int:
        """Identyfikator zbioru (idempotentnie); inna definicja przy tej wersji: błąd."""
        ...

    def asset_ids(self, pair: Pair) -> tuple[int, int] | None: ...

    def upsert_values(self, feature_set_id: int, frame: pl.DataFrame) -> Changed:
        """Zapis wartości w formacie długim (`LONG_SCHEMA`); zwraca zmienione chwile."""
        ...

    def add_outbox(self, events: Sequence[OutboxEvent]) -> None: ...

    def values(self, feature_set_id: int) -> pl.DataFrame:
        """Wszystkie wartości zbioru w formacie długim, po (base, quote, feature, as_of)."""
        ...


def _bits(x: float) -> bytes:
    return struct.pack("<d", x)


class InMemoryFeatureStore:
    """`FeatureStore` w pamięci (testy logiki zadania), z wycofaniem transakcji przy błędzie."""

    def __init__(self, assets: dict[str, int] | None = None) -> None:
        self.assets: dict[str, int] = dict(assets or {})
        self.sets: dict[tuple[str, str], tuple[int, dict[str, Any], str]] = {}
        self.rows: dict[tuple[int, str, str, str, int], tuple[int, float, str]] = {}
        self.outbox: list[OutboxEvent] = []

    @contextmanager
    def transaction(self) -> Generator[None]:
        saved = (copy.copy(self.sets), copy.copy(self.rows), list(self.outbox))
        try:
            yield
        except BaseException:
            self.sets, self.rows, self.outbox = saved
            raise

    def ensure_feature_set(
        self, name: str, version: str, definition: dict[str, Any], code_version: str
    ) -> int:
        found = self.sets.get((name, version))
        if found is None:
            found = (len(self.sets) + 1, copy.deepcopy(definition), code_version)
            self.sets[(name, version)] = found
        elif found[1] != definition:
            raise FeatureSetMismatchError(f"{name} {version}: inna definicja niż zapisana")
        return found[0]

    def asset_ids(self, pair: Pair) -> tuple[int, int] | None:
        if pair.base in self.assets and pair.quote in self.assets:
            return self.assets[pair.base], self.assets[pair.quote]
        return None

    def upsert_values(self, feature_set_id: int, frame: pl.DataFrame) -> Changed:
        changed: Changed = set()
        for base, quote, feature, as_of, cutoff, value, status in frame.iter_rows():
            key = (feature_set_id, base, quote, feature, as_of)
            new = (cutoff, value, status)
            old = self.rows.get(key)
            if old is None or (old[0], _bits(old[1]), old[2]) != (cutoff, _bits(value), status):
                self.rows[key] = new
                changed.add((base, quote, as_of))
        return changed

    def add_outbox(self, events: Sequence[OutboxEvent]) -> None:
        self.outbox.extend(events)

    def values(self, feature_set_id: int) -> pl.DataFrame:
        rows = sorted(
            (base, quote, feature, as_of, v[0], v[1], v[2])
            for (sid, base, quote, feature, as_of), v in self.rows.items()
            if sid == feature_set_id
        )
        return pl.DataFrame(rows, schema=LONG_SCHEMA, orient="row")
