# pyright: reportMissingTypeStubs=false
"""Nagranie kaset testowych z prawdziwej giełdy (`python -m goatcash.marketdata record`).

Te same adaptery co w produkcji, więc nagrane URL-e są dokładnie tymi, o które pytają testy.
Plan nagrania jest stały (okna niżej), żeby kasety obu giełd pokrywały te same świece:

- `instruments.json`: lista instrumentów spot przycięta do par uniwersum;
- `candles_<PARA>.json`: pierwsze 100 h od początku uniwersum (2023-01-01) i 100 h
  od 2026-11-20 dla każdej z 20 par (test normalizacji);
- `series_<PARA>.json`: 2000 h od 2024-07-01 dla 5 par (fałszywe alarmy DQ na prawdziwych
  danych; okres obejmuje gwałtowny spadek 5.08.2024).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import ccxt

from goatcash.marketdata._impl.cassette import Cassette, RecordingSession, now_iso
from goatcash.marketdata._impl.sources import SOURCES
from goatcash.marketdata._impl.types import HOUR_MS, TimeRange, datetime_to_ms
from goatcash.marketdata._impl.universe import Universe

RECENT_START_MS = datetime_to_ms(datetime(2026, 11, 20, tzinfo=UTC))
SERIES_START_MS = datetime_to_ms(datetime(2024, 7, 1, tzinfo=UTC))
NORMALIZATION_HOURS = 100
SERIES_HOURS = 2000
SERIES_PAIRS = ("BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT", "APT-USDT")


@dataclass(frozen=True, slots=True)
class Window:
    name: str
    time_range: TimeRange


def normalization_windows(universe: Universe) -> list[Window]:
    hours = NORMALIZATION_HOURS * HOUR_MS
    return [
        Window("start", TimeRange(universe.start_ms, universe.start_ms + hours)),
        Window("recent", TimeRange(RECENT_START_MS, RECENT_START_MS + hours)),
    ]


def series_window() -> TimeRange:
    return TimeRange(SERIES_START_MS, SERIES_START_MS + SERIES_HOURS * HOUR_MS)


def _trim_instruments(exchange: str, body: str, ids: set[str]) -> str:
    data = cast(dict[str, Any], json.loads(body))
    if exchange == "okx":
        data["data"] = [i for i in cast(list[dict[str, Any]], data["data"]) if i["instId"] in ids]
    else:
        result = cast(dict[str, Any], data["result"])
        result["list"] = [
            i for i in cast(list[dict[str, Any]], result["list"]) if i["symbol"] in ids
        ]
    return json.dumps(data, separators=(",", ":"))


def record(
    exchange: str,
    universe: Universe,
    out_dir: Path,
    *,
    client_factory: Callable[[], ccxt.Exchange] | None = None,
    log: Callable[[str], None] = print,
) -> list[Path]:
    """Nagrywa kasety jednej giełdy do `out_dir/<giełda>/`; zwraca zapisane pliki."""
    source_cls = SOURCES[exchange]
    target = out_dir / exchange
    written: list[Path] = []

    def session_for(name: str, note: str = "") -> tuple[Cassette, Any]:
        cassette = Cassette(exchange=exchange, recorded_at=now_iso(), note=note)
        source = source_cls(client_factory() if client_factory else None)
        client = cast(Any, source)._client
        client.session = RecordingSession(cassette)
        log(f"{exchange}: nagrywam {name}")
        return cassette, source

    cassette, source = session_for(
        "instruments", "odpowiedź listy instrumentów przycięta do par uniwersum (pełna > 1 MB)"
    )
    infos = source.instruments(universe.symbols)
    ids = {i.exchange_symbol for i in infos}
    for interaction in cassette.interactions:
        interaction.body = _trim_instruments(exchange, interaction.body, ids)
    path = target / "instruments.json"
    cassette.save(path)
    written.append(path)
    log(f"{exchange}: {len(infos)}/{len(universe.symbols)} par dostępnych")

    for symbol in universe.symbols:
        if symbol not in {i.symbol for i in infos}:
            continue
        cassette, src = session_for(f"candles {symbol}")
        # Lista instrumentów w tej kasecie także (ccxt ładuje rynki przed świecami).
        for window in normalization_windows(universe):
            candles = src.candles(symbol, universe.timeframe, window.time_range)
            log(f"{exchange}: {symbol} {window.name}: {len(candles)} świec")
        cassette.interactions = [i for i in cassette.interactions if "instruments" not in i.url]
        path = target / f"candles_{symbol}.json"
        cassette.save(path)
        written.append(path)

    for symbol in SERIES_PAIRS:
        cassette, src = session_for(f"series {symbol}")
        candles = src.candles(symbol, universe.timeframe, series_window())
        log(f"{exchange}: {symbol} seria: {len(candles)} świec")
        cassette.interactions = [i for i in cassette.interactions if "instruments" not in i.url]
        path = target / f"series_{symbol}.json"
        cassette.save(path)
        written.append(path)
    return written
