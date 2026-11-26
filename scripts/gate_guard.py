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
  z `evidence.local` (plik w docs/gates/G<nr>/ na `main`, zgodna suma SHA-256, nagłówek
  z commitem nie starszym niż część `ci`, bez linii FAIL, ostatnia linia PASS z czasem
  w limicie). Reguły czytamy z `main` (`git show`), więc PR nie może ich złagodzić.
Nazwy jobów bramki i workflow pochodzą z reguł, nigdy z pliku dowodu (recenzja PR 3).

Ścieżki realizacji (ADR-0008): gates/requirements.yaml ma przełącznik `sciezka`
(`praca` albo `produkt`) i mapę zależności dla każdej ścieżki; obowiązuje mapa wskazana
przełącznikiem. W ścieżce pracy wymagane bywają bramki pracy `G<nr>p`; mapa `produkt` nie może
ich zawierać (pełna bramka nie da się zastąpić okrojoną). Etap spoza mapy aktywnej ścieżki
(np. odłożony do produktu) jest odrzucany.

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
# Bramka: G<nr> z fazą a, b albo c (G14a) i opcjonalnym sufiksem p (bramka ścieżki pracy, ADR-0008).
GATE_RE = re.compile(r"G\d+[a-c]?p?")
WORK_GATE_RE = re.compile(r"G\d+[a-c]?p")
TRACKS = ("praca", "produkt")
LOCAL_SUMMARY_RE = re.compile(r"== (G\d+[a-c]?p?) \(local\): (\d+) PASS, 0 FAIL, 0 SKIP ==")
WORKFLOW_PATH_RE = re.compile(r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml")
EVIDENCE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
REPORT_HEADER_RE = re.compile(
    r"Raport (G\d+[a-c]?p?) ([a-z0-9-]+) \| commit ([0-9a-f]{40}) \| (\d{8}T\d{6}Z) \| local"
)
FAIL_LINE_RE = re.compile(r".*\bFAIL\b.*")
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


@dataclass(frozen=True)
class Requirements:
    """gates/requirements.yaml: aktywna ścieżka i mapy etap -> wymagane bramki (ADR-0008)."""

    track: str
    maps: dict[str, dict[str, list[str]]]

    @property
    def active(self) -> dict[str, list[str]]:
        return self.maps[self.track]


def _stage_map(path: str, name: str, raw: object) -> dict[str, list[str]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{path}: '{name}' musi być niepustą mapą etap -> lista bramek")
    out: dict[str, list[str]] = {}
    for stage, gates in cast(dict[object, object], raw).items():
        if not isinstance(stage, str) or not STAGE_RE.fullmatch(stage):
            raise ValueError(f"{path}: {name}: niepoprawny etap {stage!r}")
        if not isinstance(gates, list):
            raise ValueError(f"{path}: {name}: {stage}: oczekiwano listy bramek")
        names = [str(g) for g in cast(list[object], gates)]
        for gate in names:
            if not GATE_RE.fullmatch(gate):
                raise ValueError(f"{path}: {name}: {stage}: niepoprawna bramka {gate!r}")
            if name == "produkt" and WORK_GATE_RE.fullmatch(gate):
                raise ValueError(f"{path}: produkt: {stage}: bramka pracy {gate} niedozwolona")
        out[stage] = names
    return out


def requirements() -> Requirements:
    path = "gates/requirements.yaml"
    raw = cast(object, yaml.safe_load((ROOT / path).read_text("utf-8")))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: oczekiwano mapy z kluczami sciezka, praca, produkt")
    data = cast(dict[object, object], raw)
    if set(data) != {"sciezka", *TRACKS}:
        raise ValueError(f"{path}: wymagane dokładnie klucze sciezka, praca, produkt")
    track = data["sciezka"]
    if track not in TRACKS:
        raise ValueError(f"{path}: sciezka musi być jedną z {TRACKS}, jest {track!r}")
    maps = {name: _stage_map(path, name, data[name]) for name in TRACKS}
    return Requirements(track=str(track), maps=maps)


def git_show_bytes(ref: str, path: str) -> bytes | None:
    proc = subprocess.run(  # noqa: S603 - argumenty z tego skryptu
        ["git", "show", f"{ref}:{path}"],  # noqa: S607 - git z PATH, jak w Makefile
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return proc.stdout if proc.returncode == 0 else None


def _evidence_rules(
    path: str, ev: Mapping[str, object], section: str
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


def ci_job_name(gate: str) -> str:
    """Job bramki w ci.yml, którego wynik liczy się do dowodu (nie z pliku dowodu)."""
    return f"8 bramka {gate} (ubuntu-latest)"


def _check_workflow_rule(path: str, key: str, rule: Mapping[str, object]) -> None:
    workflow, events, job = rule.get("workflow"), rule.get("events"), rule.get("job")
    if not isinstance(workflow, str) or not WORKFLOW_PATH_RE.fullmatch(workflow):
        raise ValueError(f"{path}: {key}: 'workflow' musi być ścieżką .github/workflows/*.yml")
    if not isinstance(job, str) or not job:
        raise ValueError(f"{path}: {key}: 'job' (nazwa joba, który musi być zielony) jest wymagany")
    if (
        not isinstance(events, list)
        or not events
        or not set(cast(list[object], events)) <= ALLOWED_EVENTS
    ):
        raise ValueError(f"{path}: {key}: 'events' to niepusta lista z {sorted(ALLOWED_EVENTS)}")


def _check_local_rule(path: str, key: str, rule: Mapping[str, object]) -> None:
    pattern, limit = rule.get("pass_line"), rule.get("max_seconds")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"{path}: {key}: 'pass_line' (wyrażenie regularne) jest wymagane")
    try:
        compiled = re.compile(pattern)
    except re.error as err:
        raise ValueError(f"{path}: {key}: niepoprawne 'pass_line': {err}") from err
    if "seconds" not in compiled.groupindex:
        raise ValueError(f"{path}: {key}: 'pass_line' musi mieć grupę (?P<seconds>...)")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError(f"{path}: {key}: 'max_seconds' (dodatnia liczba całkowita) jest wymagane")


def gate_evidence(
    gate: str, ref: str | None = None
) -> dict[str, dict[str, dict[str, object]]] | None:
    """Blok `evidence` z gates/G<nr>.yaml (reguły dowodu mixed) albo None, gdy go nie ma.

    Z `ref` reguły pochodzą z tego commita (`git show`), nie z drzewa roboczego.
    """
    path = f"gates/{gate}.yaml"
    if ref is None:
        text = (ROOT / path).read_text("utf-8")
    else:
        blob = git_show_bytes(ref, path)
        if blob is None:
            raise ValueError(f"{ref}:{path}: brak pliku reguł bramki")
        text = blob.decode("utf-8")
    raw = cast(dict[str, object], yaml.safe_load(text))
    if "evidence" not in raw:
        return None
    ev = raw["evidence"]
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
    workflows = [str(rule["workflow"]) for rule in out["workflows"].values()]
    if len(workflows) != len(set(workflows)):
        raise ValueError(f"{path}: każda reguła workflow musi wskazywać inny plik workflow")
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
    if job_name != ci_job_name(gate):
        # Job bramki ma continue-on-error, dopóki etap trwa: przebieg ci.yml jest zielony
        # także z czerwoną bramką, więc liczy się wyłącznie job tej bramki na ubuntu.
        return [f"{gate}: job dowodu musi być „{ci_job_name(gate)}”, jest „{job_name}”"]
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
        "repository": repo,
        "head_repository": repo,
    }
    for key, want in expected.items():
        got = run.get(key)
        if key in {"repository", "head_repository"}:
            got = cast(dict[str, object], got or {}).get("full_name")
        if got != want:
            problems.append(f"{gate}: przebieg {run_id}: {key} = {got!r}, oczekiwano {want!r}")
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
    job_name = str(rule.get("job"))
    jobs = cast(
        list[dict[str, object]],
        ctx.get(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100").get("jobs") or [],
    )
    job = next((j for j in jobs if j.get("name") == job_name), None)
    if job is None or job.get("conclusion") != "success":
        problems.append(f"{gate}: {key}: w przebiegu {run_id} brak zielonego joba „{job_name}”")
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


def _header_problem(ctx: RunContext, key: str, lines: list[str]) -> str | None:
    """Pierwsza linia: ta bramka i ten dowód, commit z `ref` nie starszy niż część ci."""
    gate = ctx.gate
    header = REPORT_HEADER_RE.fullmatch(lines[0]) if lines else None
    if header is None or header[1] != gate or header[2] != key:
        return (
            f"{gate}: {key}: pierwsza linia raportu musi mieć postać "
            f"„Raport {gate} {key} | commit <sha 40 znaków> | <RRRRMMDDTGGMMSSZ> | local”"
        )
    commit = header[3]
    if git("merge-base", "--is-ancestor", commit, ctx.ref).returncode != 0:
        return f"{gate}: {key}: commit raportu nie należy do historii {ctx.ref}"
    if git("merge-base", "--is-ancestor", ctx.since, commit).returncode != 0:
        return f"{gate}: {key}: raport dotyczy commita starszego niż dowód CI ({ctx.since[:12]})"
    return None


def _report_problems(
    ctx: RunContext, key: str, rule: Mapping[str, object], lines: list[str]
) -> list[str]:
    """Treść raportu: poprawny nagłówek, bez FAIL, ostatnia linia PASS z czasem w limicie."""
    gate = ctx.gate
    problem = _header_problem(ctx, key, lines)
    if problem is not None:
        return [problem]
    if any(FAIL_LINE_RE.fullmatch(line) for line in lines):
        return [f"{gate}: {key}: raport zawiera linię FAIL"]
    passed = re.fullmatch(str(rule.get("pass_line")), lines[-1])
    if passed is None:
        return [
            f"{gate}: {key}: ostatnia linia raportu nie jest linią PASS ({rule.get('pass_line')})"
        ]
    seconds, limit = int(passed["seconds"]), cast(int, rule.get("max_seconds"))
    if seconds > limit:
        return [f"{gate}: {key}: czas {seconds} s przekracza limit {limit} s"]
    return []


def verify_local_report(
    ctx: RunContext, key: str, rule: Mapping[str, object], entry: object
) -> list[str]:
    """Raport lokalny: plik w docs/gates/G<nr>/ na `ref`, zgodna suma SHA-256, poprawna treść."""
    gate, ref = ctx.gate, ctx.ref
    parsed = _local_entry(gate, key, entry)
    if isinstance(parsed, str):
        return [parsed]
    path, digest = parsed
    content = git_show_bytes(ref, path)
    if content is None:
        return [f"{gate}: {key}: brak pliku {path} na {ref}"]
    if hashlib.sha256(content).hexdigest() != digest:
        return [f"{gate}: {key}: suma SHA-256 pliku {path} nie zgadza się z dowodem"]
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{gate}: {key}: raport {path} nie jest w UTF-8"]
    lines = [line for line in text.splitlines() if line.strip()]
    return _report_problems(ctx, key, rule, lines)


def verify_mixed(
    gate: str, proof: Mapping[str, object], repo: str, ref: str, get: Getter | None = None
) -> list[str]:
    evidence = gate_evidence(gate, ref)
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
    run_ids = (
        [
            cast(dict[str, object], e).get("run_id")
            for e in cast(dict[str, object], proof.get("workflows") or {}).values()
            if isinstance(e, dict)
        ]
        if isinstance(proof.get("workflows"), dict)
        else []
    )
    if len(run_ids) != len({str(r) for r in run_ids}):
        problems.append(f"{gate}: workflows: ten sam przebieg (run_id) użyty więcej niż raz")
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
                problems += verify_local_report(ctx, key, rule, given_map[key])
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
    if gate_evidence(gate, ref) is not None:
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
    print(f"Ścieżka: {reqs.track} (gates/requirements.yaml)")
    problems: list[str] = []
    for stage in stages:
        if stage not in reqs.active:
            other = [t for t in TRACKS if t != reqs.track and stage in reqs.maps[t]]
            reason = f"etap należy do ścieżki {other[0]}" if other else "etap nieznany"
            problems.append(
                f"{stage}: {reason}, a aktywna jest ścieżka {reqs.track} (gates/requirements.yaml)"
            )
            continue
        for gate in reqs.active[stage]:
            found = check_gate(gate, repo, ref)
            problems += found
            verdict = "BRAK DOWODU" if found else "zaliczona (dowód sprawdzony)"
            print(f"{stage} wymaga {gate}: {verdict}")
    for problem in problems:
        print(f"BŁĄD: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
