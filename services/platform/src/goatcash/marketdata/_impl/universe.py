"""Uniwersum ścieżki pracy: stała lista par z `marketdata/config/universe.toml`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from typing import Any, cast

from goatcash.marketdata._impl.normalize import normalize_symbol
from goatcash.marketdata._impl.types import Timeframe, datetime_to_ms

PAIR_COUNT = 20  # ścieżka pracy: 20 par (roadmapa E4, ADR-0008)


@dataclass(frozen=True, slots=True)
class Asset:
    symbol: str
    name: str
    coingecko_id: str


@dataclass(frozen=True, slots=True)
class Universe:
    start_ms: int
    timeframe: Timeframe
    exchanges: tuple[str, ...]  # (główna, druga)
    quote: Asset
    bases: tuple[Asset, ...]

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(normalize_symbol(a.symbol, self.quote.symbol) for a in self.bases)


def _asset(raw: dict[str, Any], symbol_key: str) -> Asset:
    return Asset(
        symbol=str(raw[symbol_key]).upper(),
        name=str(raw["name"]),
        coingecko_id=str(raw["coingecko_id"]),
    )


def parse_universe(text: str) -> Universe:
    raw = tomllib.loads(text)
    start = datetime.fromisoformat(str(raw["start"]))
    timeframe = str(raw["timeframe"])
    if timeframe != "1h":
        raise ValueError(f"ścieżka pracy obsługuje tylko świece 1h, jest {timeframe!r}")
    exchanges = cast(dict[str, str], raw["exchanges"])
    bases = tuple(_asset(p, "base") for p in cast(list[dict[str, Any]], raw["pairs"]))
    symbols = [b.symbol for b in bases]
    if len(set(symbols)) != len(symbols):
        raise ValueError("powtórzona para w uniwersum")
    if len({b.coingecko_id for b in bases}) != len(bases):
        raise ValueError("powtórzone coingecko_id w uniwersum")
    return Universe(
        start_ms=datetime_to_ms(start),
        timeframe="1h",
        exchanges=(exchanges["primary"], exchanges["secondary"]),
        quote=_asset(cast(dict[str, Any], raw["quote"]), "symbol"),
        bases=bases,
    )


def load_universe() -> Universe:
    """Uniwersum z pliku w pakiecie (działa także z obrazu, bez katalogu repozytorium)."""
    text = files("goatcash.marketdata").joinpath("config/universe.toml").read_text("utf-8")
    return parse_universe(text)
