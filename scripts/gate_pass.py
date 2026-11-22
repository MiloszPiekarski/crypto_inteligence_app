"""Zapisuje dowód zaliczenia bramki: docs/gates/G<nr>.passed.json (sprawdza go gate-guard).

Bramka zaliczona w CI na `main` (typ ci), np. po zielonym przebiegu ci.yml:
    uv run python scripts/gate_pass.py 1 --run 45027155138
Bramka wyłącznie lokalna (typ local, np. G0), po `make gate G=0` na `main`:
    uv run python scripts/gate_pass.py 0 --local reports/gates/G0-20261122T140000Z.log

Skrypt niczego nie przyjmuje na słowo: dla typu ci pobiera przebieg z GitHuba (`gh api`)
i odmawia, jeśli nie jest to zielony `push` na `main`; dla typu local odmawia, jeśli raport
ma FAIL albo SKIP. Wynik i tak sprawdza ponownie gate-guard w każdym PR etapu.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
HEADER_RE = re.compile(
    r"Bramka (G\d+[a-c]?) \(E\d+[a-c]?\) \| commit ([0-9a-f]{7,40}) \| (\S+) \| local"
)
SUMMARY_RE = re.compile(r"== (G\d+[a-c]?) \(local\): (\d+) PASS, 0 FAIL, 0 SKIP ==")


def run(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603


def ci_proof(gate: str, run_id: int, job: str) -> dict[str, object]:
    data = cast(
        dict[str, object],
        json.loads(run("gh", "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}")),
    )
    wanted = {
        "event": "push",
        "head_branch": "main",
        "conclusion": "success",
        "path": ".github/workflows/ci.yml",
    }
    bad = {k: data.get(k) for k, v in wanted.items() if data.get(k) != v}
    if bad:
        raise SystemExit(f"Przebieg {run_id} nie jest zielonym pushem ci.yml na main: {bad}")
    return {
        "gate": gate,
        "type": "ci",
        "run_id": run_id,
        "commit": data["head_sha"],
        "job": job,
        "url": data["html_url"],
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def local_proof(gate: str, report: Path) -> dict[str, object]:
    text = report.read_text(encoding="utf-8")
    header = HEADER_RE.search(text)
    summary = SUMMARY_RE.search(text)
    if header is None or header[1] != gate:
        raise SystemExit(f"{report}: to nie jest lokalny raport bramki {gate}")
    if summary is None or summary[1] != gate:
        raise SystemExit(f"{report}: raport ma FAIL albo SKIP (albo brak podsumowania)")
    return {
        "gate": gate,
        "type": "local",
        "commit": run("git", "rev-parse", header[2]),
        "report_time": header[3],
        "summary": summary[0],
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nr", help="numer bramki, np. 1 albo 10a")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", type=int, help="ID zielonego przebiegu ci.yml na main")
    group.add_argument("--local", type=Path, help="raport z reports/gates/ (bramka tylko lokalna)")
    parser.add_argument(
        "--job", help="nazwa joba bramki (domyślnie: 8 bramka G<nr> (ubuntu-latest))"
    )
    args = parser.parse_args(argv[1:])
    gate = f"G{args.nr}"
    if args.run is not None:
        proof = ci_proof(
            gate, cast(int, args.run), cast(str, args.job or f"8 bramka {gate} (ubuntu-latest)")
        )
    else:
        proof = local_proof(gate, cast(Path, args.local))
    out = ROOT / "docs" / "gates" / f"{gate}.passed.json"
    out.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Zapisano {out.relative_to(ROOT)}:\n{out.read_text(encoding='utf-8')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
