"""`python -m goatcash.marketdata <polecenie>`: narzędzia modułu marketdata.

- `record --exchange okx --out <katalog>`: nagranie kaset testowych z prawdziwej giełdy
  (bez kluczy API; tylko publiczne dane rynkowe).

Proces `ingest` i raport danych dochodzą w PR 2 E4 (staging).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from goatcash.marketdata._impl.record import record
from goatcash.marketdata._impl.sources import SOURCES
from goatcash.marketdata._impl.universe import load_universe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m goatcash.marketdata")
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="nagranie kaset testowych z giełdy")
    rec.add_argument("--exchange", choices=sorted(SOURCES), required=True)
    rec.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "record":
        files = record(str(args.exchange), load_universe(), Path(args.out))
        print(f"zapisano {len(files)} kaset w {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
