"""Testy gate-guard i gate_pass: dowód bramki nie może zostać przyjęty na słowo."""

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import cast

import gate_guard
import gate_pass
import pytest
import yaml

COMMIT = "c7e95c1c2c97cb0f5ebe4d1343438f2694df66b9"
GOOD_RUN: dict[str, object] = {
    "event": "push",
    "head_branch": "main",
    "conclusion": "success",
    "path": ".github/workflows/ci.yml",
    "head_sha": COMMIT,
    "repository": {"full_name": "o/r"},
    "head_repository": {"full_name": "o/r"},
}
JOB = "8 bramka G1 (ubuntu-latest)"
PROOF: dict[str, object] = {"gate": "G1", "type": "ci", "run_id": 1, "commit": COMMIT, "job": JOB}


def fake_github(run: dict[str, object], job_ok: bool = True) -> Callable[[str], dict[str, object]]:
    def get(path: str) -> dict[str, object]:
        if path.endswith("/jobs?per_page=100"):
            return {"jobs": [{"name": JOB, "conclusion": "success" if job_ok else "failure"}]}
        return run

    return get


@pytest.fixture(autouse=True)
def commit_in_history(monkeypatch: pytest.MonkeyPatch) -> None:
    class Ok:
        returncode = 0

    def ok(*_args: str) -> Ok:
        return Ok()

    monkeypatch.setattr(gate_guard, "git", ok)


def test_valid_ci_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_guard, "github_get", fake_github(GOOD_RUN))
    assert gate_guard.verify_ci("G1", PROOF, "o/r", "origin/main") == []


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("event", "pull_request"),
        ("head_branch", "feat/x"),
        ("conclusion", "failure"),
        ("path", ".github/workflows/inne.yml"),
        ("head_sha", "0" * 40),
    ],
)
def test_ci_proof_from_wrong_run_rejected(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    run: dict[str, object] = {**GOOD_RUN, key: value}
    monkeypatch.setattr(gate_guard, "github_get", fake_github(run))
    assert any(key in p for p in gate_guard.verify_ci("G1", PROOF, "o/r", "origin/main"))


def test_ci_proof_with_red_gate_job_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate_guard, "github_get", fake_github(GOOD_RUN, job_ok=False))
    assert any("brak zielonego joba" in p for p in gate_guard.verify_ci("G1", PROOF, "o/r", "x"))


def test_ci_proof_commit_outside_main_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class No:
        returncode = 1

    def no(*_args: str) -> No:
        return No()

    monkeypatch.setattr(gate_guard, "git", no)
    assert "nie należy do historii" in gate_guard.verify_ci("G1", PROOF, "o/r", "origin/main")[0]


def test_local_proof_only_for_local_gate() -> None:
    summary = "== G1 (local): 17 PASS, 0 FAIL, 0 SKIP =="
    g1: dict[str, object] = {"commit": COMMIT, "summary": summary}
    found = gate_guard.verify_local("G1", g1, "origin/main")
    assert "tylko dla bramki" in found[0]
    ok: dict[str, object] = {
        "commit": COMMIT,
        "summary": "== G0 (local): 2 PASS, 0 FAIL, 0 SKIP ==",
    }
    assert gate_guard.verify_local("G0", ok, "origin/main") == []
    bad: dict[str, object] = {
        "commit": COMMIT,
        "summary": "== G0 (local): 1 PASS, 1 FAIL, 0 SKIP ==",
    }
    assert gate_guard.verify_local("G0", bad, "origin/main") != []


def test_labels_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    def passed(*_args: str) -> list[str]:
        return []

    monkeypatch.setattr(gate_guard, "check_gate", passed)
    assert gate_guard.main(["g", "--labels", "E2"]) == 0
    assert gate_guard.main(["g", "--labels", "dependencies"]) == 0
    assert gate_guard.main(["g", "--labels", "task"]) == 1
    assert gate_guard.main(["g", "--labels", "E99"]) == 1


def test_labels_read_from_api_not_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Zdarzenie `opened` z `gh pr create --label` ma jeszcze puste etykiety; liczy się stan z API.
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"pull_request": {"number": 18, "labels": []}}), "utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    asked: list[str] = []

    def api(path: str) -> dict[str, object]:
        asked.append(path)
        return {"labels": [{"name": "E2"}]}

    def passed(*_args: str) -> list[str]:
        return []

    monkeypatch.setattr(gate_guard, "github_get", api)
    monkeypatch.setattr(gate_guard, "check_gate", passed)
    assert gate_guard.main(["g"]) == 0
    assert asked == ["repos/o/r/pulls/18"]


def test_labels_removed_in_api_make_guard_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Odwrotnie: zdarzenie ma etykietę, ale w chwili uruchomienia już jej nie ma.
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"number": 7, "labels": [{"name": "E2"}]}}), "utf-8"
    )
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))

    def api(_path: str) -> dict[str, object]:
        return {"labels": []}

    monkeypatch.setattr(gate_guard, "github_get", api)
    assert gate_guard.main(["g"]) == 1


def test_workflow_has_no_opened_trigger_and_no_cancellation() -> None:
    wf = yaml.safe_load((gate_guard.ROOT / ".github/workflows/gate-guard.yml").read_text("utf-8"))
    for event in wf[True]:  # PyYAML czyta klucz `on` jako True
        triggers = wf[True][event]["types"]
        assert "opened" not in triggers
        assert {"synchronize", "labeled", "unlabeled", "reopened"} <= set(triggers)
    assert set(wf[True]) == {"pull_request_target"}, "tylko pull_request_target (PR 10b)"
    assert "concurrency" not in wf
    assert wf["permissions"].get("pull-requests") == "read"


def test_workflow_never_runs_pr_code_with_target_trigger() -> None:
    # pull_request_target jest bezpieczny tylko bez kodu z PR i bez uprawnień do zapisu.
    wf = yaml.safe_load((gate_guard.ROOT / ".github/workflows/gate-guard.yml").read_text("utf-8"))
    assert set(wf["permissions"].values()) == {"read"}
    for job in wf["jobs"].values():
        assert "permissions" not in job
        for step in job["steps"]:
            if str(step.get("uses", "")).startswith("actions/checkout@"):
                assert "ref" not in step.get("with", {}), "checkout kodu z PR"
                assert step["with"]["persist-credentials"] is False
            text = yaml.safe_dump(step)
            assert "secrets." not in text
            assert "github.event.pull_request.head" not in text


def stage_labels() -> list[str]:
    setup = (gate_guard.ROOT / "scripts" / "github-setup.sh").read_text(encoding="utf-8")
    labels = next(line for line in setup.splitlines() if line.startswith("for l in E0"))
    return labels.split(" in ", 1)[1].split(";")[0].split()


def test_requirements_cover_every_stage_label() -> None:
    reqs = gate_guard.requirements()
    # Pełna roadmapa: każda etykieta etapu ma wpis w mapie produktu.
    assert set(stage_labels()) == set(reqs.maps["produkt"])
    # Ścieżka pracy: tylko etapy z tabeli „Kolejność prac” (ADR-0008) i zaliczone E0 do E3.
    assert set(reqs.maps["praca"]) <= set(stage_labels())


WORK_STAGES = {"E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E11", "E12a", "E12b"}


def test_repo_requirements_follow_adr_0008() -> None:
    reqs = gate_guard.requirements()
    assert reqs.track == "praca"
    assert set(reqs.maps["praca"]) == WORK_STAGES
    for stage in ("E10", "E10a", "E11a", "E13", "E14a", "E14b", "E14c", "E15", "E16", "E18"):
        assert stage not in reqs.maps["praca"], stage
    # E5 w ścieżce pracy wymaga bramki pracy G4p, w produkcie pełnej G4.
    assert reqs.maps["praca"]["E5"] == ["G4p"]
    assert reqs.maps["produkt"]["E5"] == ["G4"]
    assert reqs.maps["praca"]["E12b"] == ["G6p", "G9p", "G11p"]
    for gates in reqs.maps["produkt"].values():
        assert not any(g.endswith("p") for g in gates), gates


GOOD_REQS = """
sciezka: praca
praca:
  E4: [G3]
  E5: [G4p]
produkt:
  E4: [G3]
  E5: [G4]
  E10: [G4]
"""


def write_reqs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    (tmp_path / "gates").mkdir(exist_ok=True)
    (tmp_path / "gates" / "requirements.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setattr(gate_guard, "ROOT", tmp_path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (GOOD_REQS.replace("sciezka: praca", "sciezka: obie"), "sciezka musi"),
        (GOOD_REQS.replace("sciezka: praca\n", ""), "dokładnie klucze"),
        (GOOD_REQS + "inna: {E1: []}\n", "dokładnie klucze"),
        (GOOD_REQS.replace("  E5: [G4]", "  E5: [G4p]"), "bramka pracy G4p niedozwolona"),
        (GOOD_REQS.replace("  E5: [G4p]", "  E5: [G4x]"), "niepoprawna bramka"),
        (GOOD_REQS.replace("  E5: [G4p]", "  E5: [../G4]"), "niepoprawna bramka"),
        (GOOD_REQS.replace("  E5: [G4p]", "  X5: [G4p]"), "niepoprawny etap"),
        (GOOD_REQS.replace("  E5: [G4p]", "  E5: G4p"), "oczekiwano listy"),
        ("sciezka: praca\npraca: {}\nprodukt: {E1: []}\n", "niepustą mapą"),
        ("- E1\n", "oczekiwano mapy"),
    ],
)
def test_bad_requirements_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, message: str
) -> None:
    write_reqs(tmp_path, monkeypatch, text)
    with pytest.raises(ValueError, match=message):
        gate_guard.requirements()


def checked_gates(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def record(gate: str, *_args: str) -> list[str]:
        seen.append(gate)
        return []

    monkeypatch.setattr(gate_guard, "check_gate", record)
    return seen


def test_active_track_selects_required_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = checked_gates(monkeypatch)
    write_reqs(tmp_path, monkeypatch, GOOD_REQS)
    assert gate_guard.main(["g", "--labels", "E5"]) == 0
    assert seen == ["G4p"]
    seen.clear()
    write_reqs(tmp_path, monkeypatch, GOOD_REQS.replace("sciezka: praca", "sciezka: produkt"))
    assert gate_guard.main(["g", "--labels", "E5"]) == 0
    assert seen == ["G4"], "w produkcie bramka pracy nie zastępuje pełnej"


def test_deferred_stage_rejected_in_work_track(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen = checked_gates(monkeypatch)
    write_reqs(tmp_path, monkeypatch, GOOD_REQS)
    assert gate_guard.main(["g", "--labels", "E10"]) == 1
    assert "należy do ścieżki produkt" in capsys.readouterr().out
    # Dwie etykiety: etap odłożony nie przejdzie obok dozwolonego.
    assert gate_guard.main(["g", "--labels", "E4", "E10"]) == 1
    assert seen == ["G3"]
    write_reqs(tmp_path, monkeypatch, GOOD_REQS.replace("sciezka: praca", "sciezka: produkt"))
    assert gate_guard.main(["g", "--labels", "E10"]) == 0


def test_work_gate_proof_must_name_that_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dowód pełnej G4 nie zalicza G4p i odwrotnie (pole `gate` w pliku dowodu)."""

    class Shown:
        returncode = 0
        stdout = json.dumps({**PROOF, "gate": "G4"})

    def show(*_args: str) -> Shown:
        return Shown()

    monkeypatch.setattr(gate_guard, "git", show)
    assert "innej bramki" in str(gate_guard.load_proof("G4p", "origin/main"))


def test_work_gate_names_in_reports() -> None:
    assert gate_guard.GATE_RE.fullmatch("G4p")
    assert gate_guard.GATE_RE.fullmatch("G14a")
    assert not gate_guard.GATE_RE.fullmatch("G4pp")
    assert not gate_guard.GATE_RE.fullmatch("G4q")
    assert gate_guard.LOCAL_SUMMARY_RE.fullmatch("== G4p (local): 3 PASS, 0 FAIL, 0 SKIP ==")
    assert gate_pass.SUMMARY_RE.fullmatch("== G4p (local): 3 PASS, 0 FAIL, 0 SKIP ==")
    assert gate_pass.HEADER_RE.fullmatch(
        "Bramka G4p (E4) | commit abc1234 | 20261201T000000Z | local"
    )


@pytest.mark.parametrize("nr", ["../x", "4q", "4 ", "x"])
def test_gate_pass_rejects_bad_gate_number(nr: str) -> None:
    with pytest.raises(SystemExit, match="niepoprawny numer bramki"):
        gate_pass.main(["p", nr, "--run", "1"])


def test_gate_pass_local_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: str) -> str:
        return COMMIT

    monkeypatch.setattr(gate_pass, "run", fake_run)
    report = tmp_path / "G0.log"
    report.write_text(
        "Bramka G0 (E0) | commit c7e95c1 | 20261122T140000Z | local\n"
        "== G0 (local): 2 PASS, 0 FAIL, 0 SKIP ==\n",
        encoding="utf-8",
    )
    proof = gate_pass.local_proof("G0", report)
    assert proof["commit"] == COMMIT
    assert proof["summary"] == "== G0 (local): 2 PASS, 0 FAIL, 0 SKIP =="
    red = tmp_path / "red.log"
    red.write_text(
        "Bramka G0 (E0) | commit c7e95c1 | 20261122T140000Z | local\n"
        "== G0 (local): 1 PASS, 1 FAIL, 0 SKIP ==\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        gate_pass.local_proof("G0", red)


def test_repo_g1_proof_is_well_formed() -> None:
    proof = json.loads((gate_guard.ROOT / "docs" / "gates" / "G1.passed.json").read_text("utf-8"))
    assert proof["type"] == "ci"
    assert proof["job"] == JOB
    assert (
        yaml.safe_load((gate_guard.ROOT / "gates" / "G0.yaml").read_text("utf-8"))["gate"] == "G0"
    )


@pytest.mark.parametrize("job", ["1 lint", "8 bramka G1 (macos-15)", "8 bramka G2 (ubuntu-latest)"])
def test_ci_proof_with_other_job_rejected(monkeypatch: pytest.MonkeyPatch, job: str) -> None:
    # Recenzja PR 3: job bramki ma continue-on-error, przebieg jest zielony także z czerwoną
    # bramką, więc dowód nie może wskazać dowolnego zielonego joba (np. lint albo macOS).
    monkeypatch.setattr(gate_guard, "github_get", fake_github(GOOD_RUN))
    found = gate_guard.verify_ci("G1", {**PROOF, "job": job}, "o/r", "origin/main")
    assert any("job dowodu musi być „8 bramka G1 (ubuntu-latest)”" in p for p in found), found


@pytest.mark.parametrize("key", ["repository", "head_repository"])
def test_ci_proof_from_other_repository_rejected(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    run: dict[str, object] = {**GOOD_RUN, key: {"full_name": "atak/fork"}}
    monkeypatch.setattr(gate_guard, "github_get", fake_github(run))
    assert any(key in p for p in gate_guard.verify_ci("G1", PROOF, "o/r", "origin/main"))


# --- Dowód mixed (ADR-0007, punkt 5): próby obejścia muszą być odrzucone -------------------

REPO = "o/r"
WF = ".github/workflows/deploy-staging.yml"
WF2 = ".github/workflows/external-scan.yml"
G3_JOB = "8 bramka G3 (ubuntu-latest)"
REPORT_COMMIT = "b" * 40
REBUILD_LINE = r"== G3 rebuild \(local\): PASS, (?P<seconds>[0-9]+) s, 0 manual steps =="
EVIDENCE: dict[str, dict[str, dict[str, object]]] = {
    "workflows": {
        "deploy": {"workflow": WF, "job": "deploy", "events": ["push"]},
        "external-scan": {"workflow": WF2, "job": "external-scan", "events": ["schedule"]},
    },
    "local": {"rebuild": {"pass_line": REBUILD_LINE, "max_seconds": 1800}},
}
HEADER = f"Raport G3 rebuild | commit {REPORT_COMMIT} | 20261201T100000Z | local"
REPORT = (
    f"{HEADER}\nkrok: infrastruktura gotowa\n"
    "== G3 rebuild (local): PASS, 1234 s, 0 manual steps ==\n"
)
REPORT_PATH = "docs/gates/G3/rebuild-20261201T100000Z.log"


def wf_run(workflow: str, event: str, **changes: object) -> dict[str, object]:
    run: dict[str, object] = {
        "event": event,
        "head_branch": "main",
        "conclusion": "success",
        "path": workflow,
        "head_sha": "a" * 40,
        "repository": {"full_name": REPO},
        "head_repository": {"full_name": REPO},
    }
    run.update(changes)
    return run


def mixed_proof(report: str = REPORT, /, **changes: object) -> dict[str, object]:
    proof: dict[str, object] = {
        "gate": "G3",
        "type": "mixed",
        "ci": {"run_id": 1, "commit": COMMIT, "job": G3_JOB},
        "workflows": {"deploy": {"run_id": 2}, "external-scan": {"run_id": 3}},
        "local": {
            "rebuild": {
                "path": REPORT_PATH,
                "sha256": hashlib.sha256(report.encode()).hexdigest(),
            }
        },
    }
    proof.update(changes)
    return proof


def mixed_github(
    deploy: dict[str, object] | None = None,
    ci_job_ok: bool = True,
    wf_job_ok: bool = True,
) -> Callable[[str], dict[str, object]]:
    runs: dict[str, dict[str, object]] = {
        "1": {**GOOD_RUN, "head_sha": COMMIT},
        "2": deploy if deploy is not None else wf_run(WF, "push"),
        "3": wf_run(WF2, "schedule"),
    }
    jobs = {
        "1": [
            {"name": "1 lint", "conclusion": "success"},
            {"name": G3_JOB, "conclusion": "success" if ci_job_ok else "failure"},
        ],
        "2": [{"name": "deploy", "conclusion": "success" if wf_job_ok else "skipped"}],
        "3": [{"name": "external-scan", "conclusion": "success"}],
    }

    def get(path: str) -> dict[str, object]:
        run_id = path.split("/runs/")[1].split("/", maxsplit=1)[0]
        if path.endswith("/jobs?per_page=100"):
            return {"jobs": jobs[run_id]}
        return runs[run_id]

    return get


def use_report(monkeypatch: pytest.MonkeyPatch, report: str | bytes) -> None:
    blob = report.encode() if isinstance(report, str) else report

    def show(_ref: str, path: str) -> bytes | None:
        return blob if path == REPORT_PATH else None

    monkeypatch.setattr(gate_guard, "git_show_bytes", show)


@pytest.fixture
def g3(monkeypatch: pytest.MonkeyPatch) -> None:
    def evidence(
        gate: str, _ref: str | None = None
    ) -> dict[str, dict[str, dict[str, object]]] | None:
        return EVIDENCE if gate == "G3" else None

    monkeypatch.setattr(gate_guard, "gate_evidence", evidence)
    use_report(monkeypatch, REPORT)


def verify(
    proof: dict[str, object], get: Callable[[str], dict[str, object]] | None = None
) -> list[str]:
    return gate_guard.verify_mixed("G3", proof, REPO, "origin/main", get or mixed_github())


def git_rejecting(monkeypatch: pytest.MonkeyPatch, *pairs: tuple[str, str]) -> None:
    """git merge-base --is-ancestor odpowiada „nie” dla podanych par (przodek, potomek)."""

    class Res:
        def __init__(self, code: int) -> None:
            self.returncode = code

    def git(*args: str) -> Res:
        if args[:2] == ("merge-base", "--is-ancestor") and (args[2], args[3]) in pairs:
            return Res(1)
        return Res(0)

    monkeypatch.setattr(gate_guard, "git", git)


@pytest.mark.usefixtures("g3")
def test_valid_mixed_proof() -> None:
    assert verify(mixed_proof()) == []


@pytest.mark.usefixtures("g3")
def test_mixed_ci_part_with_red_gate_job_rejected() -> None:
    found = verify(mixed_proof(), mixed_github(ci_job_ok=False))
    assert any(f"brak zielonego joba „{G3_JOB}”" in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_mixed_ci_part_with_lint_job_rejected() -> None:
    proof = mixed_proof(ci={"run_id": 1, "commit": COMMIT, "job": "1 lint"})
    assert any("job dowodu musi być" in p for p in verify(proof))


@pytest.mark.usefixtures("g3")
def test_mixed_ci_part_from_other_commit_rejected() -> None:
    proof = mixed_proof(ci={"run_id": 1, "commit": "c" * 40, "job": G3_JOB})
    assert any("head_sha" in p for p in verify(proof))


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("event", "pull_request", "zdarzenie 'pull_request'"),
        ("event", "pull_request_target", "zdarzenie 'pull_request_target'"),
        ("event", "workflow_dispatch", "zdarzenie 'workflow_dispatch'"),
        ("head_branch", "feat/x", "head_branch"),
        ("conclusion", "failure", "conclusion"),
        ("path", ".github/workflows/ci.yml", "path"),
        ("path", "x/.github/workflows/deploy-staging.yml", "path"),
        ("repository", {"full_name": "atak/fork"}, "repository"),
        ("head_repository", {"full_name": "atak/fork"}, "head_repository"),
    ],
)
def test_mixed_workflow_run_from_wrong_source_rejected(
    key: str, value: object, message: str
) -> None:
    found = verify(mixed_proof(), mixed_github(deploy={**wf_run(WF, "push"), key: value}))
    assert any(p.startswith("G3: deploy:") and message in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_mixed_workflow_with_skipped_job_rejected() -> None:
    # Recenzja PR 3: przebieg zielony, ale job sprawdzający pominięty (if:) albo z
    # continue-on-error; liczy się wynik joba z reguły, nie całego przebiegu.
    found = verify(mixed_proof(), mixed_github(wf_job_ok=False))
    assert any("brak zielonego joba „deploy”" in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_mixed_workflow_run_older_than_ci_commit_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_rejecting(monkeypatch, (COMMIT, "a" * 40))
    assert any("starszego niż dowód CI" in p for p in verify(mixed_proof()))


@pytest.mark.usefixtures("g3")
def test_mixed_workflow_run_outside_main_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    git_rejecting(monkeypatch, ("a" * 40, "origin/main"))
    assert any("commit przebiegu 2 nie należy do historii" in p for p in verify(mixed_proof()))


@pytest.mark.usefixtures("g3")
def test_mixed_same_run_for_two_rules_rejected() -> None:
    proof = mixed_proof(workflows={"deploy": {"run_id": 2}, "external-scan": {"run_id": 2}})
    assert any("ten sam przebieg" in p for p in verify(proof))


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"workflows": {"deploy": {"run_id": 2}}}, "brak dowodu 'external-scan'"),
        ({"local": {}}, "brak dowodu 'rebuild'"),
        (
            {
                "workflows": {
                    "deploy": {"run_id": 2},
                    "external-scan": {"run_id": 3},
                    "x": {"run_id": 4},
                }
            },
            "'x' nie jest wymagany",
        ),
        (
            {"workflows": {"deploy": {"run_id": "2"}, "external-scan": {"run_id": 3}}},
            "run_id (liczba)",
        ),
        (
            {"workflows": {"deploy": {"run_id": True}, "external-scan": {"run_id": 3}}},
            "run_id (liczba)",
        ),
        ({"workflows": ["deploy"]}, "musi być mapą"),
        ({"ci": None}, "wymaga części ci"),
    ],
)
def test_mixed_proof_missing_or_malformed_parts_rejected(
    changes: dict[str, object], message: str
) -> None:
    found = verify(mixed_proof(**changes))
    assert any(message in p for p in found), found


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    "path",
    [
        "docs/gates/G3/../G2.md",
        "docs/gates/G3/./x.log",
        "docs/gates/G3/x\\y.log",
        "docs/gates/G3/sub/",
        "README.md",
        "docs/gates/G30/x.log",
    ],
)
def test_mixed_local_report_path_outside_dir_rejected(path: str) -> None:
    proof = mixed_proof(local={"rebuild": {"path": path, "sha256": "0" * 64}})
    assert any("raport musi leżeć w docs/gates/G3/" in p for p in verify(proof)), path


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ({"path": "docs/gates/G3/inny.log", "sha256": "0" * 64}, "brak pliku"),
        ({"path": REPORT_PATH, "sha256": "0" * 64}, "suma SHA-256"),
        ({"path": REPORT_PATH, "sha256": "ABC"}, "64 znaki"),
        ({"path": REPORT_PATH}, "64 znaki"),
    ],
)
def test_mixed_local_report_tampering_rejected(entry: dict[str, object], message: str) -> None:
    found = verify(mixed_proof(local={"rebuild": entry}))
    assert any(message in p for p in found), found


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    ("report", "message"),
    [
        (REPORT.replace("1234 s", "99999 s"), "przekracza limit 1800 s"),
        (REPORT + "== G3 rebuild (local): FAIL, 99 s ==\n", "linię FAIL"),
        (REPORT.replace("krok: infrastruktura gotowa", "krok: FAIL"), "linię FAIL"),
        (REPORT + "coś po linii PASS\n", "ostatnia linia raportu nie jest linią PASS"),
        (REPORT.replace(HEADER + "\n", ""), "pierwsza linia raportu"),
        (REPORT.replace("Raport G3 rebuild", "Raport G2 rebuild"), "pierwsza linia raportu"),
        (REPORT.replace("Raport G3 rebuild", "Raport G3 inny"), "pierwsza linia raportu"),
        (REPORT.replace(REPORT_COMMIT, "b" * 7), "pierwsza linia raportu"),
    ],
)
def test_mixed_local_report_content_rejected(
    monkeypatch: pytest.MonkeyPatch, report: str, message: str
) -> None:
    use_report(monkeypatch, report)
    found = verify(mixed_proof(report))
    assert any(message in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_mixed_local_report_older_than_ci_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    git_rejecting(monkeypatch, (COMMIT, REPORT_COMMIT))
    assert any("raport dotyczy commita starszego" in p for p in verify(mixed_proof()))


@pytest.mark.usefixtures("g3")
def test_mixed_local_report_commit_outside_main_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git_rejecting(monkeypatch, (REPORT_COMMIT, "origin/main"))
    assert any("commit raportu nie należy do historii" in p for p in verify(mixed_proof()))


@pytest.mark.usefixtures("g3")
def test_mixed_local_report_not_utf8_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    blob = REPORT.encode("utf-16")
    use_report(monkeypatch, blob)
    proof = mixed_proof(
        local={"rebuild": {"path": REPORT_PATH, "sha256": hashlib.sha256(blob).hexdigest()}}
    )
    assert any("nie jest w UTF-8" in p for p in verify(proof))


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize("kind", ["ci", "local"])
def test_gate_with_evidence_rejects_plain_ci_or_local_proof(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    # Obejście: zaliczyć G3 samym zielonym przebiegiem CI, bez dowodów z infrastruktury.
    proof: dict[str, object] = {
        "gate": "G3",
        "type": kind,
        "run_id": 1,
        "commit": COMMIT,
        "job": G3_JOB,
    }

    def load(_gate: str, _ref: str) -> dict[str, object]:
        return proof

    monkeypatch.setattr(gate_guard, "load_proof", load)
    found = gate_guard.check_gate("G3", REPO, "origin/main")
    assert any("wymagany dowód typu mixed" in p for p in found), found


def test_mixed_proof_rejected_for_gate_without_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_evidence(_gate: str, _ref: str | None = None) -> None:
        return None

    monkeypatch.setattr(gate_guard, "gate_evidence", no_evidence)
    found = gate_guard.verify_mixed("G2", mixed_proof(gate="G2"), REPO, "origin/main")
    assert any("tylko dla bramki z blokiem evidence" in p for p in found), found


def test_repo_g3_evidence_rules_are_valid() -> None:
    ev = gate_guard.gate_evidence("G3")
    assert ev is not None
    assert set(ev["workflows"]) == {"deploy", "restore-test", "external-scan", "alert-drill"}
    assert set(ev["local"]) == {"rebuild"}
    for rule in ev["workflows"].values():
        assert "pull_request" not in cast(list[str], rule["events"])
    assert gate_guard.gate_evidence("G2") is None
    assert gate_guard.gate_evidence("G0") is None
    line = "== G3 rebuild (local): PASS, 1799 s, 0 manual steps =="
    assert re.fullmatch(str(ev["local"]["rebuild"]["pass_line"]), line)


def test_gate_evidence_reads_rules_from_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    # Recenzja PR 3: reguły z `ref` (main), nie z drzewa roboczego.
    asked: list[tuple[str, str]] = []

    def show(ref: str, path: str) -> bytes:
        asked.append((ref, path))
        return b"gate: G3\n"

    monkeypatch.setattr(gate_guard, "git_show_bytes", show)
    assert gate_guard.gate_evidence("G3", "origin/main") is None
    assert asked == [("origin/main", "gates/G3.yaml")]


GOOD_WF_RULE: dict[str, object] = {"workflow": WF, "job": "deploy", "events": ["push"]}


@pytest.mark.parametrize(
    "bad",
    [
        None,  # `evidence:` bez wartości nie może wyłączyć wymogu dowodu mixed
        [],
        {},
        {"workflows": {"x": {**GOOD_WF_RULE, "events": ["pull_request"]}}},
        {"workflows": {"x": {**GOOD_WF_RULE, "workflow": "../evil.yml"}}},
        {"workflows": {"x": {**GOOD_WF_RULE, "events": []}}},
        {"workflows": {"x": {"workflow": WF, "events": ["push"]}}},  # brak job
        {"workflows": {"X Y": GOOD_WF_RULE}},
        {"workflows": {"a": GOOD_WF_RULE, "b": GOOD_WF_RULE}},  # ten sam plik workflow
        {"local": {"r": {}}},
        {"local": {"r": {"pass_line": "(", "max_seconds": 1}}},
        {"local": {"r": {"pass_line": "PASS", "max_seconds": 1}}},  # brak grupy seconds
        {"local": {"r": {"pass_line": "(?P<seconds>[0-9]+)"}}},  # brak max_seconds
        {"local": {"r": {"pass_line": "(?P<seconds>[0-9]+)", "max_seconds": True}}},
    ],
)
def test_bad_evidence_rules_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    (tmp_path / "gates").mkdir()
    (tmp_path / "gates" / "G9.yaml").write_text(yaml.safe_dump({"evidence": bad}), "utf-8")
    monkeypatch.setattr(gate_guard, "ROOT", tmp_path)
    with pytest.raises(ValueError, match=r"G9\.yaml"):
        gate_guard.gate_evidence("G9")


def test_gate_pass_rejects_wrong_mode_for_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    def evidence(
        gate: str, _ref: str | None = None
    ) -> dict[str, dict[str, dict[str, object]]] | None:
        return EVIDENCE if gate == "G3" else None

    monkeypatch.setattr(gate_guard, "gate_evidence", evidence)
    with pytest.raises(SystemExit, match="wymagany typ mixed"):
        gate_pass.main(["p", "3", "--local", "x.log"])
    with pytest.raises(SystemExit, match="niedozwolone"):
        gate_pass.main(["p", "2", "--run", "1", "--workflow", "deploy=2"])
    with pytest.raises(SystemExit):
        gate_pass.main(["p", "2", "--run", "1", "--job", "1 lint"])  # --job już nie istnieje


def test_gate_pass_mixed_rejects_bad_pairs() -> None:
    with pytest.raises(SystemExit):
        gate_pass._pairs(["deploy"], "--workflow")  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(SystemExit):
        gate_pass._pairs(["a=1", "a=2"], "--workflow")  # pyright: ignore[reportPrivateUsage]
    assert gate_pass._pairs(["a=1", "b=2"], "--w") == {"a": "1", "b": "2"}  # pyright: ignore[reportPrivateUsage]
