"""gate-guard: PR etapu przechodzi tylko wtedy, gdy wymagane bramki mają dowód na `main`.

Zakładka „Testy i quality gates”, sekcja 3: każdy PR ma etykietę etapu (E7 itd.), a bramki
wymagane do tego etapu muszą mieć na `main` plik docs/gates/G<nr>.passed.json. Dowód nie jest
wierzony na słowo:
- `"type": "ci"`: przebieg CI o podanym ID musi istnieć w tym repozytorium, być zdarzeniem
  `push` na `main` z workflow `ci.yml`, zakończyć się sukcesem, dotyczyć podanego commita
  (który jest w historii `main`), a job bramki musi mieć wynik `success`;
- `"type": "local"`: dozwolony tylko dla bramki, której wszystkie sprawdzenia mają
  `only: local` (np. G0: komputer i klucze właściciela); wymagany raport bez FAIL i SKIP.

PR bez etykiety etapu przechodzi tylko z etykietą `dependencies` (aktualizacje Dependabota).
Użycie w CI: python scripts/gate_guard.py (zmienne GITHUB_EVENT_PATH, GITHUB_REPOSITORY,
GH_TOKEN). Lokalnie: python scripts/gate_guard.py --labels E2 [--ref origin/main].
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
STAGE_RE = re.compile(r"E\d+[a-c]?")
LOCAL_SUMMARY_RE = re.compile(r"== (G\d+[a-c]?) \(local\): (\d+) PASS, 0 FAIL, 0 SKIP ==")


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argumenty z tego skryptu, nie od użytkownika
        ["git", *args],  # noqa: S607 - git z PATH, jak w Makefile
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def requirements() -> dict[str, list[str]]:
    raw = cast(object, yaml.safe_load((ROOT / "gates" / "requirements.yaml").read_text("utf-8")))
    if not isinstance(raw, dict):
        raise ValueError("gates/requirements.yaml: oczekiwano mapy etap -> lista bramek")
    data = cast(dict[object, object], raw)
    return {str(k): [str(g) for g in cast(list[object], v or [])] for k, v in data.items()}


def gate_is_local_only(gate: str) -> bool:
    raw = cast(object, yaml.safe_load((ROOT / "gates" / f"{gate}.yaml").read_text("utf-8")))
    checks = cast(list[dict[str, object]], cast(dict[str, object], raw).get("checks") or [])
    return bool(checks) and all(c.get("only") == "local" for c in checks)


def github_get(path: str) -> dict[str, object]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    req = urllib.request.Request(
        f"https://api.github.com/{path}",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - stały host https
        return cast(dict[str, object], json.load(resp))


def verify_ci(gate: str, proof: Mapping[str, object], repo: str, ref: str) -> list[str]:
    run_id, commit, job_name = proof.get("run_id"), proof.get("commit"), proof.get("job")
    if not isinstance(run_id, int) or not isinstance(commit, str) or not isinstance(job_name, str):
        return [f"{gate}: dowód ci wymaga pól run_id (liczba), commit i job"]
    if git("merge-base", "--is-ancestor", commit, ref).returncode != 0:
        return [f"{gate}: commit {commit[:12]} nie należy do historii {ref}"]
    run = github_get(f"repos/{repo}/actions/runs/{run_id}")
    problems: list[str] = []
    expected = {
        "event": "push",
        "head_branch": "main",
        "conclusion": "success",
        "path": ".github/workflows/ci.yml",
        "head_sha": commit,
    }
    for key, want in expected.items():
        if run.get(key) != want:
            problems.append(
                f"{gate}: przebieg {run_id}: {key} = {run.get(key)!r}, oczekiwano {want!r}"
            )
    jobs = cast(
        list[dict[str, object]],
        github_get(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100").get("jobs") or [],
    )
    job = next((j for j in jobs if j.get("name") == job_name), None)
    if job is None or job.get("conclusion") != "success":
        problems.append(f"{gate}: w przebiegu {run_id} brak zielonego joba „{job_name}”")
    return problems


def verify_local(gate: str, proof: Mapping[str, object], ref: str) -> list[str]:
    if not gate_is_local_only(gate):
        return [
            f"{gate}: dowód lokalny dozwolony tylko dla bramki z samymi sprawdzeniami only: local"
        ]
    commit, summary = proof.get("commit"), proof.get("summary")
    if (
        not isinstance(commit, str)
        or git("merge-base", "--is-ancestor", commit, ref).returncode != 0
    ):
        return [f"{gate}: commit dowodu lokalnego nie należy do historii {ref}"]
    match = LOCAL_SUMMARY_RE.fullmatch(str(summary))
    if match is None or match[1] != gate:
        return [
            f"{gate}: podsumowanie lokalne musi mieć postać "
            f"„== {gate} (local): N PASS, 0 FAIL, 0 SKIP ==”"
        ]
    return []


def check_gate(gate: str, repo: str, ref: str) -> list[str]:
    shown = git("show", f"{ref}:docs/gates/{gate}.passed.json")
    if shown.returncode != 0:
        return [f"{gate}: brak docs/gates/{gate}.passed.json na {ref} (bramka niezaliczona)"]
    proof = cast(dict[str, object], json.loads(shown.stdout))
    if proof.get("gate") != gate:
        return [f"{gate}: plik dowodu dotyczy innej bramki ({proof.get('gate')!r})"]
    if proof.get("type") == "ci":
        return verify_ci(gate, proof, repo, ref)
    if proof.get("type") == "local":
        return verify_local(gate, proof, ref)
    return [f"{gate}: nieznany typ dowodu {proof.get('type')!r}"]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", nargs="*", help="etykiety PR (domyślnie z GITHUB_EVENT_PATH)")
    parser.add_argument(
        "--ref", default="origin/main", help="gałąź z dowodami (domyślnie origin/main)"
    )
    args = parser.parse_args(argv[1:])
    labels = cast(list[str] | None, args.labels)
    if labels is None:
        event = cast(
            dict[str, object], json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text("utf-8"))
        )
        pr = cast(dict[str, object], event.get("pull_request") or {})
        labels = [
            str(cast(dict[str, object], label).get("name"))
            for label in cast(list[object], pr.get("labels") or [])
        ]
    repo = os.environ.get("GITHUB_REPOSITORY", "MiloszPiekarski/crypto_inteligence_app")
    ref = cast(str, args.ref)
    stages = [label for label in labels if STAGE_RE.fullmatch(label)]
    if not stages:
        if "dependencies" in labels:
            print(
                "PR bez etykiety etapu, z etykietą dependencies: "
                "aktualizacja zależności, przepuszczony."
            )
            return 0
        print("BŁĄD: PR musi mieć etykietę etapu (E0…E18), np. E2.")
        return 1
    reqs = requirements()
    problems: list[str] = []
    for stage in stages:
        if stage not in reqs:
            problems.append(f"{stage}: etap nieznany w gates/requirements.yaml")
            continue
        for gate in reqs[stage]:
            found = check_gate(gate, repo, ref)
            problems += found
            verdict = "BRAK DOWODU" if found else "zaliczona (dowód sprawdzony)"
            print(f"{stage} wymaga {gate}: {verdict}")
    for problem in problems:
        print(f"BŁĄD: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
