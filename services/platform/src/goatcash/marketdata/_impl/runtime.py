"""Proces `ingest` i raport danych (roadmapa E4, punkty 4, 8 i 9 ścieżki pracy).

`ingest` (usługa w Compose staging): co godzinę, 2 min po pełnej godzinie, dla każdej pary
uniwersum uzupełnianie od punktu kontrolnego do ostatniej zamkniętej świecy (pierwsze
uruchomienie: cała historia od 2023-01-01), wykrywanie i klasyfikacja luk obu giełd,
`dq_status`, potem publikacja `candle.closed` z outbox do Valkey. Błąd jednej pary (np.
giełda chwilowo niedostępna) nie zatrzymuje pozostałych; para wraca w następnym cyklu.
Plik heartbeat (healthcheck Compose) jest odświeżany co minutę i po każdej parze.

Proces łączy się adresem z `api.env` i od razu przełącza na rolę `goatcash_app`
(`SET ROLE`), więc działa z uprawnieniami aplikacji, nie właściciela bazy. Raport używa
roli `goatcash_readonly`.

`report`: kryteria G4p dla każdej pary i giełdy (kod wyjścia 1, gdy któreś nie spełnione):
pierwsza świeca = początek uniwersum (2023-01-01), 0 brakujących świec bez opisu,
kompletność ≥ 99,9% względem świec udostępnianych przez giełdę, dane aktualne (nie
`stale`), cena referencyjna dla 100% chwil z poprawną świecą (F-06).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import psycopg

from goatcash.marketdata._impl.events import OutboxStore, relay_outbox
from goatcash.marketdata._impl.ingest import Ingest, InstrumentReport, instrument_report
from goatcash.marketdata._impl.store import InstrumentStatus, MarketStore
from goatcash.marketdata._impl.types import HOUR_MS, ms_to_datetime
from goatcash.marketdata._impl.universe import Universe

MIN_COMPLETENESS = 0.999
CYCLE_OFFSET_MS = 2 * 60_000  # 2 min po pełnej godzinie: giełdy zamykają świecę z opóźnieniem
HEARTBEAT = Path(os.environ.get("GOATCASH_HEARTBEAT", "/tmp/goatcash-ingest.heartbeat"))  # noqa: S108


def connect(url: str, role: str) -> psycopg.Connection[Any]:
    """Połączenie z adresu SQLAlchemy (`postgresql+psycopg://`) i przełączenie roli."""
    if role not in {"goatcash_app", "goatcash_readonly"}:
        raise ValueError(f"niedozwolona rola {role!r}")
    conn = psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"), autocommit=True)
    conn.execute(
        "SET ROLE goatcash_app" if role == "goatcash_app" else "SET ROLE goatcash_readonly"
    )
    return conn


def beat(path: Path = HEARTBEAT) -> None:
    path.write_text(str(int(time.time())), encoding="ascii")


def status_of(report: InstrumentReport) -> InstrumentStatus:
    if report.first_ts_ms is None:
        status = "down"
    elif report.stale:
        status = "stale"
    elif report.unexplained or report.completeness < MIN_COMPLETENESS:
        status = "degraded"
    else:
        status = "ok"
    return InstrumentStatus(
        exchange=report.exchange,
        symbol=report.symbol,
        status=status,
        completeness=report.completeness if report.first_ts_ms is not None else None,
        last_ts_ms=report.last_ts_ms,
    )


@dataclass(slots=True)
class CycleResult:
    written: int = 0
    repaired_parts: int = 0
    published: int = 0
    failed_pairs: dict[str, str] = field(default_factory=dict[str, str])


def run_cycle(
    ing: Ingest,
    store: MarketStore,
    publish: Callable[[], int],
    *,
    log: Callable[[str], None] = print,
    on_progress: Callable[[], None] = lambda: None,
) -> CycleResult:
    """Jeden cykl dla wszystkich par; błąd pary jest zapisywany w wyniku i w logu."""
    result = CycleResult()
    try:
        ing.setup_instruments()
    except Exception as exc:  # giełda niedostępna: cały cykl wraca za godzinę
        result.failed_pairs["*"] = f"{type(exc).__name__}: {exc}"
        log(f"ingest: instrumenty BŁĄD {type(exc).__name__}: {str(exc)[:300]}")
        return result
    for symbol in ing.universe.symbols:
        try:
            written = ing.backfill_pair(symbol)
            parts = [p for ex in ing.exchanges for p in ing.repair_gaps(symbol, ex)]
        except Exception as exc:  # para wraca w następnym cyklu, pozostałe działają dalej
            result.failed_pairs[symbol] = f"{type(exc).__name__}: {exc}"
            log(f"ingest: {symbol} BŁĄD {type(exc).__name__}: {str(exc)[:300]}")
            on_progress()
            continue
        result.written += written
        result.repaired_parts += len(parts)
        now = ing.now_ms()
        for ex in ing.exchanges:
            store.upsert_status(status_of(instrument_report(store, ex, symbol, now)))
        log(f"ingest: {symbol} zapisane {written}, fragmenty luk {len(parts)}")
        on_progress()
    result.published = publish()
    log(f"ingest: cykl zakończony: {json.dumps(asdict(result), ensure_ascii=False)}")
    return result


def next_cycle_ms(now_ms: int) -> int:
    return (now_ms // HOUR_MS + 1) * HOUR_MS + CYCLE_OFFSET_MS


def serve(  # noqa: PLR0913 (zależności wstrzykiwane w testach)
    ing: Ingest,
    store: MarketStore,
    publish: Callable[[], int],
    *,
    sleep: Callable[[float], None] = time.sleep,
    cycles: int | None = None,
    log: Callable[[str], None] = print,
    paused: bool = False,
) -> None:
    """Pętla procesu ingest (`cycles` tylko w testach).

    `paused` (zmienna `GOATCASH_INGEST_PAUSED=1`): proces żyje i odświeża heartbeat, ale nie
    pyta giełd (test Compose w CI; awaryjne wstrzymanie pobierania bez zatrzymania usługi).
    """
    done = 0
    beat()
    if paused:
        log("ingest: wstrzymany (GOATCASH_INGEST_PAUSED=1), bez zapytań do giełd")
    while cycles is None or done < cycles:
        if not paused:
            run_cycle(ing, store, publish, log=log, on_progress=beat)
        done += 1
        if cycles is not None and done >= cycles:
            return
        wake = next_cycle_ms(ing.now_ms())
        while (left := wake - ing.now_ms()) > 0:
            beat()
            sleep(min(60.0, left / 1000))


def outbox_publisher(store: OutboxStore, valkey_url: str, producer: str) -> Callable[[], int]:
    import redis  # noqa: PLC0415 (klient potrzebny tylko w procesie ingest)

    client = redis.Redis.from_url(valkey_url, decode_responses=True)  # pyright: ignore[reportUnknownMemberType]
    return lambda: relay_outbox(store, client, producer=producer)  # pyright: ignore[reportArgumentType]


# --- raport danych (G4p, staging) ---


@dataclass(frozen=True, slots=True)
class ReportRow:
    exchange: str
    symbol: str
    first: str
    end: str
    expected: int
    stored: int
    exchange_missing: int
    rejected: int
    unexplained: int
    completeness: float
    stale: bool
    missing_refs: int
    problems: tuple[str, ...]


def report_rows(store: MarketStore, universe: Universe, now_ms: int) -> list[ReportRow]:
    rows: list[ReportRow] = []
    for symbol in universe.symbols:
        missing_refs = store.missing_refs(symbol)
        for ex in universe.exchanges:
            r = instrument_report(store, ex, symbol, now_ms)
            problems: list[str] = []
            if r.first_ts_ms != universe.start_ms:
                problems.append("pierwsza świeca ≠ początek uniwersum")
            if r.unexplained:
                problems.append(f"{len(r.unexplained)} brakujących bez opisu")
            if r.completeness < MIN_COMPLETENESS:
                problems.append(f"kompletność {r.completeness:.4%} < 99,9%")
            if r.stale:
                problems.append("dane nieaktualne (> 2 h)")
            if missing_refs:
                problems.append(f"{missing_refs} chwil bez ceny referencyjnej")
            rows.append(
                ReportRow(
                    exchange=ex,
                    symbol=symbol,
                    first=""
                    if r.first_ts_ms is None
                    else ms_to_datetime(r.first_ts_ms).isoformat(),
                    end=ms_to_datetime(r.end_ms).isoformat() if r.end_ms else "",
                    expected=r.expected,
                    stored=r.stored,
                    exchange_missing=r.exchange_missing,
                    rejected=r.rejected,
                    unexplained=len(r.unexplained),
                    completeness=r.completeness,
                    stale=r.stale,
                    missing_refs=missing_refs,
                    problems=tuple(problems),
                )
            )
    return rows


def print_report(
    rows: list[ReportRow], universe: Universe, out: Callable[[str], None] = print
) -> int:
    """Tabela Markdown + podsumowanie; kod 0 tylko gdy wszystkie kryteria spełnione."""
    expected_rows = len(universe.symbols) * len(universe.exchanges)
    out(
        "| giełda | para | od | do | oczekiwane | zapisane | luki giełdy | odrzucone "
        "| bez opisu | kompletność | bez ceny ref. | uwagi |"
    )
    out("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for r in rows:
        out(
            f"| {r.exchange} | {r.symbol} | {r.first[:16]} | {r.end[:16]} | {r.expected} | "
            f"{r.stored} | {r.exchange_missing} | {r.rejected} | {r.unexplained} | "
            f"{r.completeness:.4%} | {r.missing_refs} | {'; '.join(r.problems) or 'OK'} |"
        )
    total = {
        "wiersze": f"{len(rows)}/{expected_rows}",
        "oczekiwane": sum(r.expected for r in rows),
        "zapisane": sum(r.stored for r in rows),
        "luki_po_stronie_giełdy": sum(r.exchange_missing for r in rows),
        "odrzucone_przez_dq": sum(r.rejected for r in rows),
        "brakujące_bez_opisu": sum(r.unexplained for r in rows),
        "min_kompletność": min((r.completeness for r in rows), default=0.0),
    }
    ok = len(rows) == expected_rows and all(not r.problems for r in rows)
    out("RAPORT " + json.dumps(total, ensure_ascii=False))
    out(f"RAPORT WYNIK: {'OK' if ok else 'NIE SPEŁNIA KRYTERIÓW G4p'}")
    return 0 if ok else 1


def env(name: str, environ: Mapping[str, str] = os.environ) -> str:
    value = environ.get(name, "")
    if not value:
        raise SystemExit(f"brak zmiennej środowiska {name}")
    return value
