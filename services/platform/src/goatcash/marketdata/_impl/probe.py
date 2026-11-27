"""Sonda dostępu do giełd z miejsca uruchomienia (`python -m goatcash.marketdata probe`).

Roadmapa E4, punkt 1 ścieżki pracy: na początku etapu sprawdzamy dostęp do giełd z serwera
staging (Amsterdam). Dla każdej giełdy uniwersum: czy lista instrumentów odpowiada, ile
z 20 par jest dostępnych i od kiedy giełda udostępnia świece 1 h (pierwsza świeca w oknie
100 h od początku uniwersum). Tylko publiczne dane rynkowe, bez kluczy i bez zapisu do bazy.

Opcjonalnie (`--record <giełda>`) nagrywa kasety testowe tej giełdy i wypisuje je na
standardowe wyjście jako archiwum tar.gz w base64 między znacznikami, z sumą SHA-256
(wynik trafia do logu workflow; artefakty nie są potrzebne).
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

from goatcash.marketdata._impl.record import record
from goatcash.marketdata._impl.sources import SOURCES, MarketDataSource, RetryPolicy
from goatcash.marketdata._impl.types import HOUR_MS, TimeRange, ms_to_datetime
from goatcash.marketdata._impl.universe import Universe

PROBE_HOURS = 100
ARCHIVE_BEGIN = "=== KASETY BEGIN"
ARCHIVE_END = "=== KASETY END ==="


@dataclass(slots=True)
class ExchangeProbe:
    exchange: str
    reachable: bool = False
    error: str = ""
    pairs_available: int = 0
    missing_pairs: list[str] = field(default_factory=list[str])
    # Para → pierwsza świeca 1 h w oknie 100 h od początku uniwersum (ISO) albo "" (brak).
    first_candle: dict[str, str] = field(default_factory=dict[str, str])
    candle_errors: dict[str, str] = field(default_factory=dict[str, str])

    @property
    def ok(self) -> bool:
        return self.reachable and not self.missing_pairs and not self.candle_errors


def _error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:300]}"


def probe_exchange(source: MarketDataSource, universe: Universe) -> ExchangeProbe:
    result = ExchangeProbe(exchange=source.exchange)
    try:
        infos = source.instruments(universe.symbols)
    except Exception as exc:  # sonda raportuje każdy błąd, nie przerywa się
        result.error = _error(exc)
        return result
    result.reachable = True
    have = {i.symbol for i in infos}
    result.pairs_available = len(have)
    result.missing_pairs = [s for s in universe.symbols if s not in have]
    window = TimeRange(universe.start_ms, universe.start_ms + PROBE_HOURS * HOUR_MS)
    for symbol in universe.symbols:
        if symbol not in have:
            continue
        try:
            candles = source.candles(symbol, universe.timeframe, window)
        except Exception as exc:
            result.candle_errors[symbol] = _error(exc)
            continue
        first = min((c.ts_ms for c in candles), default=None)
        result.first_candle[symbol] = "" if first is None else ms_to_datetime(first).isoformat()
    return result


def default_sources() -> dict[str, MarketDataSource]:
    # Sonda ma szybko pokazać blokadę: 3 próby zamiast 8.
    retry = RetryPolicy(max_attempts=3)
    return {name: cls(retry=retry) for name, cls in SOURCES.items()}


def archive(directory: Path) -> tuple[str, str]:
    """Katalog → (tar.gz w base64 z podziałem wierszy, SHA-256 archiwum)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path in sorted(directory.rglob("*.json")):
            tar.add(path, arcname=str(path.relative_to(directory)))
    data = buf.getvalue()
    return base64.encodebytes(data).decode("ascii"), hashlib.sha256(data).hexdigest()


def run_probe(
    universe: Universe,
    *,
    record_exchange: str | None = None,
    sources: Mapping[str, MarketDataSource] | None = None,
    recorder: Callable[[str, Universe, Path], object] | None = None,
    out: Callable[[str], None] = print,
) -> int:
    """Sonda giełd uniwersum; kod 0 tylko gdy obie giełdy mają wszystkie pary bez błędów."""
    found = sources if sources is not None else default_sources()
    results = [probe_exchange(found[ex], universe) for ex in universe.exchanges]
    for r in results:
        out("SONDA " + json.dumps({**asdict(r), "ok": r.ok}, ensure_ascii=False, sort_keys=True))
    ok = all(r.ok for r in results)
    out(f"SONDA WYNIK: {'OK' if ok else 'BLOKADA albo BŁĄD'}")
    if not ok or record_exchange is None:
        return 0 if ok else 1
    with tempfile.TemporaryDirectory() as tmp:
        if recorder is not None:
            recorder(record_exchange, universe, Path(tmp))
        else:
            record(record_exchange, universe, Path(tmp), log=out)
        encoded, digest = archive(Path(tmp))
        out(f"{ARCHIVE_BEGIN} sha256={digest} ===")
        out(encoded.rstrip("\n"))
        out(ARCHIVE_END)
    return 0
