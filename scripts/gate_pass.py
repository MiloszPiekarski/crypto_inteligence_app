"""Zapisuje dowód zaliczenia bramki: docs/gates/G<nr>.passed.json (sprawdza go gate-guard).

Bramka zaliczona w CI na `main` (typ ci), np. po zielonym przebiegu ci.yml:
    uv run python scripts/gate_pass.py 1 --run 45027155138
Bramka wyłącznie lokalna (typ local, np. G0), po `make gate G=0` na `main`:
    uv run python scripts/gate_pass.py 0 --local reports/gates/G0-20261122T140000Z.log
Bramka z blokiem `evidence` (typ mixed, np. G3; ADR-0007): przebieg ci.yml oraz przebiegi
i raporty lokalne wymagane w gates/G<nr>.yaml (raporty już w docs/gates/G<nr>/):
    uv run python scripts/gate_pass.py 3 --run 45300000000 \
        --workflow deploy=45300000001 --workflow restore-test=45300000002 \
        --local-report rebuild=docs/gates/G3/rebuild-20261201T100000Z.log

Skrypt niczego nie przyjmuje na słowo: dla typu ci pobiera przebieg z GitHuba (`gh api`)
i odmawia, jeśli nie jest to zielony `push` na `main`; dla typu local odmawia, jeśli raport
ma FAIL albo SKIP; dla typu mixed sprawdza każdy przebieg i raport tymi samymi funkcjami co
gate-guard. Wynik i tak sprawdza ponownie gate-guard w każdym PR etapu.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import gate_guard

ROOT = Path(__file__).resolve().parent.parent
HEADER_RE = re.compile(
    r"Bramka (G\d+[a-c]?p?) \(E\d+[a-c]?\) \| commit ([0-9a-f]{7,40}) \| (\S+) \| local"
)
SUMMARY_RE = re.compile(r"== (G\d+[a-c]?p?) \(local\): (\d+) PASS, 0 FAIL, 0 SKIP ==")


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


def gh_get(path: str) -> dict[str, object]:
    return cast(dict[str, object], json.loads(run("gh", "api", path)))


def _pairs(items: list[str], what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key or not value or key in out:
            raise SystemExit(f"{what}: oczekiwano unikalnych par id=wartość, jest {item!r}")
        out[key] = value
    return out


def mixed_proof(
    gate: str, ci: dict[str, object], workflows: list[str], reports: list[str]
) -> dict[str, object]:
    """Dowód mixed; odmawia, jeśli cokolwiek nie przejdzie sprawdzeń gate-guard."""
    repo = run("gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
    proof: dict[str, object] = {
        "gate": gate,
        "type": "mixed",
        "ci": {k: ci[k] for k in ("run_id", "commit", "job", "url")},
        "workflows": {
            key: {"run_id": int(value)} for key, value in _pairs(workflows, "--workflow").items()
        },
        "local": {
            key: {
                "path": value,
                "sha256": hashlib.sha256((ROOT / value).read_bytes()).hexdigest(),
            }
            for key, value in _pairs(reports, "--local-report").items()
        },
        "recorded_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Raporty lokalne muszą być już w commicie, który trafi na main (sprawdzamy na HEAD).
    problems = gate_guard.verify_mixed(gate, proof, repo, "HEAD", gh_get)
    if problems:
        raise SystemExit("Dowód mixed odrzucony:\n" + "\n".join(problems))
    return proof


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
    parser.add_argument("nr", help="numer bramki, np. 1, 10a albo 4p (bramka ścieżki pracy)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", type=int, help="ID zielonego przebiegu ci.yml na main")
    group.add_argument("--local", type=Path, help="raport z reports/gates/ (bramka tylko lokalna)")
    parser.add_argument(
        "--workflow", action="append", default=[], help="typ mixed: id=ID przebiegu workflow"
    )
    parser.add_argument(
        "--local-report", action="append", default=[], help="typ mixed: id=ścieżka raportu"
    )
    args = parser.parse_args(argv[1:])
    gate = f"G{args.nr}"
    if not gate_guard.GATE_RE.fullmatch(gate):
        raise SystemExit(f"{args.nr!r}: niepoprawny numer bramki (np. 1, 14a, 4p)")
    # Reguły z HEAD (to, co trafi na main), nie z niezacommitowanych zmian w drzewie.
    mixed = gate_guard.gate_evidence(gate, "HEAD") is not None
    if mixed and args.run is None:
        raise SystemExit(f"{gate} ma blok evidence: wymagany typ mixed (--run i dowody)")
    if not mixed and (args.workflow or args.local_report):
        raise SystemExit(f"{gate} nie ma bloku evidence: --workflow/--local-report niedozwolone")
    if mixed:
        ci = ci_proof(gate, cast(int, args.run), gate_guard.ci_job_name(gate))
        proof = mixed_proof(
            gate, ci, cast(list[str], args.workflow), cast(list[str], args.local_report)
        )
    elif args.run is not None:
        proof = ci_proof(gate, cast(int, args.run), gate_guard.ci_job_name(gate))
    else:
        proof = local_proof(gate, cast(Path, args.local))
    out = ROOT / "docs" / "gates" / f"{gate}.passed.json"
    out.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Zapisano {out.relative_to(ROOT)}:\n{out.read_text(encoding='utf-8')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
