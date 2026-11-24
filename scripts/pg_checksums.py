"""Sumy kontrolne wszystkich tabel bazy (F-02: „100% tabel ze zgodną liczbą wierszy i sumą").

Dla każdej tabeli użytkownika (bez schematów systemowych i wewnętrznych TimescaleDB; hypertable
liczona przez tabelę nadrzędną, czyli razem z chunkami): liczba wierszy i MD5 wierszy
posortowanych tekstowo. Wynik: JSON {"schemat.tabela": [liczba, md5]} na stdout.
Użycie: python scripts/pg_checksums.py DSN  (np. postgresql://postgres:x@127.0.0.1:5432/postgres)
Porównanie: python scripts/pg_checksums.py --compare A.json B.json (kod 1 przy różnicy).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import psycopg
from psycopg import sql

TABLES = """
SELECT table_schema, table_name FROM information_schema.tables
WHERE table_type = 'BASE TABLE'
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
  AND table_schema NOT LIKE '\\_timescaledb%' AND table_schema NOT LIKE 'timescaledb\\_%'
  AND table_schema NOT LIKE 'pg\\_%'
ORDER BY 1, 2
"""
# Ta sama treść w sondzie serwera (infra/ansible/roles/base/files/goatcash-probe).
ROW_SUM = (
    "SELECT count(*), coalesce(md5(string_agg(t::text, E'\\n' ORDER BY t::text)), '') FROM {} AS t"
)


def checksums(dsn: str) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        for schema, table in conn.execute(TABLES).fetchall():
            ident = sql.Identifier(str(schema), str(table))
            query = sql.SQL(ROW_SUM).format(ident)
            row = conn.execute(query).fetchone()
            if row is None:
                raise RuntimeError(f"brak wyniku sumy dla {schema}.{table}")
            out[f"{schema}.{table}"] = [int(cast(int, row[0])), str(row[1])]
    return out


def compare(a: dict[str, list[object]], b: dict[str, list[object]]) -> list[str]:
    problems = [f"tabela tylko w pierwszym: {t}" for t in sorted(set(a) - set(b))]
    problems += [f"tabela tylko w drugim: {t}" for t in sorted(set(b) - set(a))]
    problems += [
        f"różnica w {t}: {a[t]} != {b[t]}" for t in sorted(set(a) & set(b)) if a[t] != b[t]
    ]
    return problems


def main(argv: list[str]) -> int:
    if len(argv) == 4 and argv[1] == "--compare":  # noqa: PLR2004
        a = cast(dict[str, list[object]], json.loads(Path(argv[2]).read_text("utf-8")))
        b = cast(dict[str, list[object]], json.loads(Path(argv[3]).read_text("utf-8")))
        problems = compare(a, b)
        for problem in problems:
            print(f"  RÓŻNICA {problem}")
        rows = sum(int(cast(int, v[0])) for v in a.values())
        verdict = "zgodne" if not problems else f"{len(problems)} różnic"
        print(f"sumy kontrolne: {len(a)} tabel, {rows} wierszy: {verdict}")
        return 1 if problems else 0
    if len(argv) != 2:  # noqa: PLR2004
        print(__doc__)
        return 2
    print(json.dumps(checksums(argv[1]), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
