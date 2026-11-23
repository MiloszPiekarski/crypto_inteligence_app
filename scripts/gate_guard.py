"""gate-guard: PR etapu przechodzi tylko wtedy, gdy wymagane bramki mają dowód na `main`.

Zakładka „Testy i quality gates”, sekcja 3: każdy PR ma etykietę etapu (E7 itd.), a bramki
wymagane do tego etapu muszą mieć na `main` plik docs/gates/G<nr>.passed.json. Dowód nie jest
wierzony na słowo:
- `"type": "ci"`: przebieg CI o podanym ID musi istnieć w tym repozytorium, być zdarzeniem
  `push` na `main` z workflow `ci.yml`, zakończyć się sukcesem, dotyczyć podanego commita
  (który jest w historii `main`), a job bramki musi mieć wynik `success`;
- `"type": "local"`: dozwolony tylko dla bramki, której wszystkie sprawdzenia mają
  `only: local` (np. G0: komputer i klucze właściciela); wymagany raport bez FAIL i SKIP;
- `"type": "mixed"` (ADR-0007, punkt 5): jedyny dozwolony dla bramki z blokiem `evidence`
  w gates/G<nr>.yaml (np. G3). Część `ci` jak wyżej, a do tego każdy przebieg workflow
  wymagany w `evidence.workflows` (ten plik workflow, dozwolone zdarzenie, `main`, sukces,
  to repozytorium, commit między commitem części `ci` a `main`) i każdy raport lokalny
  z `evidence.local` (plik w docs/gates/G<nr>/ na `main`, zgodna suma SHA-256, wymagana
  linia PASS). Reguły pochodzą z `main`, więc PR nie może ich złagodzić.

PR bez etykiety etapu przechodzi tylko z etykietą `dependencies` (aktualizacje Dependabota).
Użycie w CI: python scripts/gate_guard.py (zmienne GITHUB_EVENT_PATH, GITHUB_REPOSITORY,
GH_TOKEN); etykiety są czytane z API w chwili uruchomienia (`current_pr_labels`).
Lokalnie: python scripts/gate_guard.py --labels E2 [--ref origin/main].
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
STAGE_RE = re.compile(r"E\d+[a-c]?")
LOCAL_SUMMARY_RE = re.compile(r"== (G\d+[a-c]?) \(local\): (\d+) PASS, 0 FAIL, 0 SKIP ==")
WORKFLOW_PATH_RE = re.compile(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml")
EVIDENCE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
# Zdarzenia, które może wywołać tylko ktoś z prawem zapisu (nie PR z forka).
ALLOWED_EVENTS = frozenset({"push", "schedule", "workflow_dispatch"})
Getter = Callable[[str], dict[str, object]]


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


def git_show_bytes(ref: str, path: str) -> bytes | None:
    proc = subprocess.run(  # noqa: S603 - argumenty z tego skryptu
        ["git", "show", f"{ref}:{path}"],  # noqa: S607 - git z PATH, jak w Makefile
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def _evidence_rules(
    path: Path, ev: Mapping[str, object], section: str
) -> dict[str, dict[str, object]]:
    items: object = ev.get(section) or {}
    if not isinstance(items, dict):
        raise ValueError(f"{path}: 'evidence.{section}' musi być mapą id -> reguła")
    rules: dict[str, dict[str, object]] = {}
    for key, rule in cast(dict[object, object], items).items():
        if not isinstance(key, str) or not EVIDENCE_ID_RE.fullmatch(key):
            raise ValueError(f"{path}: niepoprawny identyfikator dowodu {key!r}")
        if not isinstance(rule, dict):
            raise ValueError(f"{path}: reguła {key!r} musi być mapą")
        rules[key] = cast(dict[str, object], rule)
    return rules


def _check_workflow_rule(path: Path, key: str, rule: Mapping[str, object]) -> None:
    workflow, events = rule.get("workflow"), rule.get("events")
    if not isinstance(workflow, str) or not WORKFLOW_PATH_RE.fullmatch(workflow):
        raise ValueError(f"{path}: {key}: 'workflow' musi być ścieżką .github/workflows/*.yml")
    if (
        not isinstance(events, list)
        or not events
        or not set(cast(list[object], events)) <= ALLOWED_EVENTS
    ):
        raise ValueError(f"{path}: {key}: 'events' to niepusta lista z {sorted(ALLOWED_EVENTS)}")


def _check_local_rule(path: Path, key: str, rule: Mapping[str, object]) -> None:
    pattern = rule.get("pass_line")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"{path}: {key}: 'pass_line' (wyrażenie regularne) jest wymagane")
    try:
        re.compile(pattern)
    except re.error as err:
        raise ValueError(f"{path}: {key}: niepoprawne 'pass_line': {err}") from err


def gate_evidence(gate: str) -> dict[str, dict[str, dict[str, object]]] | None:
    """Blok `evidence` z gates/G<nr>.yaml (reguły dowodu mixed) albo None, gdy go nie ma."""
    path = ROOT / "gates" / f"{gate}.yaml"
    raw = cast(dict[str, object], yaml.safe_load(path.read_text("utf-8")))
    ev = raw.get("evidence")
    if ev is None:
        return None
    if not isinstance(ev, dict):
        raise ValueError(f"{path}: 'evidence' musi być mapą")
    ev_map = cast(dict[str, object], ev)
    out = {section: _evidence_rules(path, ev_map, section) for section in ("workflows", "local")}
    for key, rule in out["workflows"].items():
        _check_workflow_rule(path, key, rule)
    for key, rule in out["local"].items():
        _check_local_rule(path, key, rule)
    if not out["workflows"] and not out["local"]:
        raise ValueError(f"{path}: 'evidence' bez reguł")
    return out


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


def current_pr_labels(repo: str) -> list[str]:
    """Etykiety PR w chwili uruchomienia (z API), nie z ładunku zdarzenia.

    Ładunek zdarzenia jest migawką: `gh pr create --label` wysyła `opened` (jeszcze bez
    etykiety) i `labeled`. Przebieg ze starszą migawką dawałby inny wynik niż ten z nowszą,
    a GitHub może uznać za wynik checka dowolny z nich. Odczyt z API sprawia, że każdy
    przebieg ocenia ten sam, bieżący stan PR. Błąd API przerywa skrypt (wynik czerwony).
    """
    event = cast(
        dict[str, object], json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    )
    number = cast(dict[str, object], event.get("pull_request") or {}).get("number")
    if not isinstance(number, int):
        raise ValueError("GITHUB_EVENT_PATH: brak numeru PR (pull_request.number)")
    pr = github_get(f"repos/{repo}/pulls/{number}")
    return [
        str(cast(dict[str, object], label).get("name"))
        for label in cast(list[object], pr.get("labels") or [])
    ]


def verify_ci(
    gate: str, proof: Mapping[str, object], repo: str, ref: str, get: Getter | None = None
) -> list[str]:
    get = get or github_get
    run_id, commit, job_name = proof.get("run_id"), proof.get("commit"), proof.get("job")
    if (
        not isinstance(run_id, int)
        or isinstance(run_id, bool)
        or not isinstance(commit, str)
        or not isinstance(job_name, str)
    ):
        return [f"{gate}: dowód ci wymaga pól run_id (liczba), commit i job"]
    if git("merge-base", "--is-ancestor", commit, ref).returncode != 0:
        return [f"{gate}: commit {commit[:12]} nie należy do historii {ref}"]
    run = get(f"repos/{repo}/actions/runs/{run_id}")
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
        get(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100").get("jobs") or [],
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


@dataclass(frozen=True)
class RunContext:
    """Wspólne dane do sprawdzania przebiegów workflow dowodu mixed."""

    gate: str
    repo: str
    ref: str
    since: str  # commit części `ci` dowodu: przebiegi nie mogą być starsze
    get: Getter


def verify_workflow_run(
    ctx: RunContext, key: str, rule: Mapping[str, object], entry: object
) -> list[str]:
    """Przebieg wymaganego workflow: ten plik, dozwolone zdarzenie, main, sukces, to repo,
    commit nie starszy niż commit części `ci` dowodu i należący do historii `ref`."""
    gate, repo, ref, since = ctx.gate, ctx.repo, ctx.ref, ctx.since
    run_id = cast(dict[str, object], entry).get("run_id") if isinstance(entry, dict) else None
    if not isinstance(run_id, int) or isinstance(run_id, bool):
        return [f"{gate}: {key}: dowód wymaga pola run_id (liczba)"]
    run = ctx.get(f"repos/{repo}/actions/runs/{run_id}")
    problems: list[str] = []
    events = cast(list[object], rule.get("events"))
    checks: list[tuple[str, object, object]] = [
        ("path", run.get("path"), rule.get("workflow")),
        ("head_branch", run.get("head_branch"), "main"),
        ("conclusion", run.get("conclusion"), "success"),
        (
            "repository",
            cast(dict[str, object], run.get("repository") or {}).get("full_name"),
            repo,
        ),
        (
            "head_repository",
            cast(dict[str, object], run.get("head_repository") or {}).get("full_name"),
            repo,
        ),
    ]
    for name, got, want in checks:
        if got != want:
            problems.append(
                f"{gate}: {key}: przebieg {run_id}: {name} = {got!r}, oczekiwano {want!r}"
            )
    if run.get("event") not in events:
        problems.append(
            f"{gate}: {key}: przebieg {run_id}: zdarzenie {run.get('event')!r} spoza {events}"
        )
    sha = run.get("head_sha")
    if not isinstance(sha, str) or git("merge-base", "--is-ancestor", sha, ref).returncode != 0:
        problems.append(f"{gate}: {key}: commit przebiegu {run_id} nie należy do historii {ref}")
    elif git("merge-base", "--is-ancestor", since, sha).returncode != 0:
        problems.append(
            f"{gate}: {key}: przebieg {run_id} dotyczy commita starszego niż dowód CI "
            f"({since[:12]}); potrzebny przebieg z tego commita albo nowszego"
        )
    return problems


def _local_entry(gate: str, key: str, entry: object) -> tuple[str, str] | str:
    """(ścieżka, sha256) z wpisu dowodu lokalnego albo opis błędu."""
    entry_map = cast(dict[str, object], entry) if isinstance(entry, dict) else {}
    path, digest = entry_map.get("path"), entry_map.get("sha256")
    prefix = f"docs/gates/{gate}/"
    if (
        not isinstance(path, str)
        or not path.startswith(prefix)
        or "/../" in f"/{path}/"
        or "/./" in f"/{path}/"
        or "\\" in path
        or path.endswith("/")
    ):
        return f"{gate}: {key}: raport musi leżeć w {prefix} (ścieżka {path!r})"
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        return f"{gate}: {key}: sha256 musi mieć 64 znaki szesnastkowe"
    return path, digest


def verify_local_report(
    gate: str, key: str, rule: Mapping[str, object], entry: object, ref: str
) -> list[str]:
    """Raport lokalny: plik w docs/gates/G<nr>/ na `ref`, zgodna suma SHA-256, linia PASS."""
    parsed = _local_entry(gate, key, entry)
    if isinstance(parsed, str):
        return [parsed]
    path, digest = parsed
    content = git_show_bytes(ref, path)
    if content is None:
        return [f"{gate}: {key}: brak pliku {path} na {ref}"]
    if hashlib.sha256(content).hexdigest() != digest:
        return [f"{gate}: {key}: suma SHA-256 pliku {path} nie zgadza się z dowodem"]
    pattern = str(rule.get("pass_line"))
    text = content.decode("utf-8", errors="replace")
    if not any(re.fullmatch(pattern, line) for line in text.splitlines()):
        return [f"{gate}: {key}: w raporcie {path} brak linii PASS ({pattern})"]
    return []


def verify_mixed(
    gate: str, proof: Mapping[str, object], repo: str, ref: str, get: Getter | None = None
) -> list[str]:
    evidence = gate_evidence(gate)
    if evidence is None:
        return [f"{gate}: dowód mixed tylko dla bramki z blokiem evidence w gates/{gate}.yaml"]
    ci = proof.get("ci")
    if not isinstance(ci, dict):
        return [f"{gate}: dowód mixed wymaga części ci (run_id, commit, job)"]
    ci_part = cast(dict[str, object], ci)
    problems = verify_ci(gate, ci_part, repo, ref, get)
    if problems:
        return problems
    ctx = RunContext(gate, repo, ref, str(ci_part["commit"]), get or github_get)
    for section in ("workflows", "local"):
        given: object = proof.get(section) or {}
        if not isinstance(given, dict):
            problems.append(f"{gate}: część {section} dowodu musi być mapą")
            continue
        given_map = cast(dict[str, object], given)
        required = evidence[section]
        for extra in sorted(set(given_map) - set(required)):
            problems.append(f"{gate}: {section}: {extra!r} nie jest wymagany w gates/{gate}.yaml")
        for key, rule in required.items():
            if key not in given_map:
                problems.append(f"{gate}: {section}: brak dowodu {key!r}")
            elif section == "workflows":
                problems += verify_workflow_run(ctx, key, rule, given_map[key])
            else:
                problems += verify_local_report(gate, key, rule, given_map[key], ref)
    return problems


def load_proof(gate: str, ref: str) -> dict[str, object] | str:
    """Plik dowodu z `ref` albo opis, dlaczego go nie ma."""
    shown = git("show", f"{ref}:docs/gates/{gate}.passed.json")
    if shown.returncode != 0:
        return f"{gate}: brak docs/gates/{gate}.passed.json na {ref} (bramka niezaliczona)"
    proof = cast(dict[str, object], json.loads(shown.stdout))
    if proof.get("gate") != gate:
        return f"{gate}: plik dowodu dotyczy innej bramki ({proof.get('gate')!r})"
    return proof


def check_gate(gate: str, repo: str, ref: str) -> list[str]:
    proof = load_proof(gate, ref)
    if isinstance(proof, str):
        return [proof]
    if gate_evidence(gate) is not None:
        # Bramka z dowodami z prawdziwej infrastruktury: sam przebieg CI nie wystarcza.
        if proof.get("type") != "mixed":
            return [f"{gate}: gates/{gate}.yaml ma blok evidence, wymagany dowód typu mixed"]
        return verify_mixed(gate, proof, repo, ref)
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
    repo = os.environ.get("GITHUB_REPOSITORY", "MiloszPiekarski/crypto_inteligence_app")
    if labels is None:
        labels = current_pr_labels(repo)
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
