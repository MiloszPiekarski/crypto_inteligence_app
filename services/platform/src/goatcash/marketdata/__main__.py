"""`python -m goatcash.marketdata <polecenie>`: narzędzia modułu marketdata.

- `record --exchange okx --out <katalog>`: nagranie kaset testowych z prawdziwej giełdy
  (bez kluczy API; tylko publiczne dane rynkowe);
- `probe [--record bybit]`: sonda dostępu do giełd uniwersum z miejsca uruchomienia
  (serwer staging: `marketdata-probe.yml`), opcjonalnie z nagraniem kaset jednej giełdy;
- `ingest`: proces pobierania świec (usługa Compose staging), zmienne środowiska
  `GOATCASH_DATABASE_URL` i `GOATCASH_VALKEY_URL`;
- `report`: raport danych G4p z bazy (rola tylko do odczytu), kod 1 przy niespełnionym
  kryterium (`data-report.yml`).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from goatcash.marketdata._impl.probe import run_probe
from goatcash.marketdata._impl.record import record
from goatcash.marketdata._impl.sources import SOURCES
from goatcash.marketdata._impl.universe import load_universe


def ingest_main() -> int:
    from goatcash.common.api import package_version  # noqa: PLC0415
    from goatcash.marketdata._impl.ingest import Ingest  # noqa: PLC0415
    from goatcash.marketdata._impl.pgstore import PostgresStore  # noqa: PLC0415
    from goatcash.marketdata._impl.runtime import connect, env, outbox_publisher, serve  # noqa: PLC0415

    producer = f"ingest@{package_version()}"
    store = PostgresStore(connect(env("GOATCASH_DATABASE_URL"), "goatcash_app"))
    universe = load_universe()
    sources = {name: cls() for name, cls in SOURCES.items() if name in universe.exchanges}
    ing = Ingest(store=store, sources=sources, universe=universe, producer=producer)
    print(f"ingest: start {producer}, {len(universe.symbols)} par, giełdy {universe.exchanges}")
    paused = os.environ.get("GOATCASH_INGEST_PAUSED", "0") == "1"
    serve(ing, store, outbox_publisher(store, env("GOATCASH_VALKEY_URL"), producer), paused=paused)
    return 0


def report_main() -> int:
    import time  # noqa: PLC0415

    from goatcash.marketdata._impl.pgstore import PostgresStore  # noqa: PLC0415
    from goatcash.marketdata._impl.runtime import connect, env, print_report, report_rows  # noqa: PLC0415

    universe = load_universe()
    store = PostgresStore(connect(env("GOATCASH_DATABASE_URL"), "goatcash_readonly"))
    rows = report_rows(store, universe, int(time.time() * 1000))
    return print_report(rows, universe)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m goatcash.marketdata")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="nagranie kaset testowych z giełdy")
    rec.add_argument("--exchange", choices=sorted(SOURCES), required=True)
    rec.add_argument("--out", type=Path, required=True)
    prb = sub.add_parser("probe", help="sonda dostępu do giełd (opcjonalnie z nagraniem kaset)")
    prb.add_argument("--record", choices=sorted(SOURCES), default=None)
    sub.add_parser("ingest", help="proces pobierania świec (pętla co godzinę)")
    sub.add_parser("report", help="raport danych G4p (kod 1 przy niespełnionym kryterium)")
    args = parser.parse_args(argv)
    if args.command == "probe":
        return run_probe(load_universe(), record_exchange=args.record)
    if args.command == "ingest":
        return ingest_main()
    if args.command == "report":
        return report_main()
    files = record(str(args.exchange), load_universe(), Path(args.out))
    print(f"zapisano {len(files)} kaset w {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
