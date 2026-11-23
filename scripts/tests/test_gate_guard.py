"""Testy gate-guard i gate_pass: dowód bramki nie może zostać przyjęty na słowo."""

import hashlib
import json
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


def test_requirements_cover_every_stage_label() -> None:
    reqs = gate_guard.requirements()
    setup = (gate_guard.ROOT / "scripts" / "github-setup.sh").read_text(encoding="utf-8")
    labels = next(line for line in setup.splitlines() if line.startswith("for l in E0"))
    for stage in labels.split(" in ", 1)[1].split(";")[0].split():
        assert stage in reqs, stage
    for gates in reqs.values():
        for gate in gates:
            assert gate.startswith("G"), gate


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


# --- Dowód mixed (ADR-0007, punkt 5): próby obejścia muszą być odrzucone -------------------

REPO = "o/r"
WF = ".github/workflows/deploy-staging.yml"
EVIDENCE: dict[str, dict[str, dict[str, object]]] = {
    "workflows": {"deploy": {"workflow": WF, "events": ["push"]}},
    "local": {
        "rebuild": {
            "pass_line": r"== G3 rebuild \(local\): PASS, [0-9]+ s < 1800 s, 0 manual steps =="
        }
    },
}
REPORT = b"Odtworzenie od zera\n== G3 rebuild (local): PASS, 1234 s < 1800 s, 0 manual steps ==\n"
REPORT_PATH = "docs/gates/G3/rebuild-20261201T100000Z.log"
GOOD_WF_RUN: dict[str, object] = {
    "event": "push",
    "head_branch": "main",
    "conclusion": "success",
    "path": WF,
    "head_sha": "a" * 40,
    "repository": {"full_name": REPO},
    "head_repository": {"full_name": REPO},
}


def mixed_proof(**changes: object) -> dict[str, object]:
    proof: dict[str, object] = {
        "gate": "G3",
        "type": "mixed",
        "ci": {"run_id": 1, "commit": COMMIT, "job": "8 bramka G3 (ubuntu-latest)"},
        "workflows": {"deploy": {"run_id": 2}},
        "local": {"rebuild": {"path": REPORT_PATH, "sha256": hashlib.sha256(REPORT).hexdigest()}},
    }
    proof.update(changes)
    return proof


def mixed_github(wf_run: dict[str, object]) -> Callable[[str], dict[str, object]]:
    def get(path: str) -> dict[str, object]:
        if path.endswith("/jobs?per_page=100"):
            return {"jobs": [{"name": "8 bramka G3 (ubuntu-latest)", "conclusion": "success"}]}
        if path.endswith("/runs/1"):
            return {**GOOD_RUN, "head_sha": COMMIT}
        return wf_run

    return get


@pytest.fixture
def g3(monkeypatch: pytest.MonkeyPatch) -> None:
    def evidence(gate: str) -> dict[str, dict[str, dict[str, object]]] | None:
        return EVIDENCE if gate == "G3" else None

    def show(_ref: str, path: str) -> bytes | None:
        return REPORT if path == REPORT_PATH else None

    monkeypatch.setattr(gate_guard, "gate_evidence", evidence)
    monkeypatch.setattr(gate_guard, "git_show_bytes", show)


@pytest.mark.usefixtures("g3")
def test_valid_mixed_proof() -> None:
    found = gate_guard.verify_mixed(
        "G3", mixed_proof(), REPO, "origin/main", mixed_github(GOOD_WF_RUN)
    )
    assert found == []


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("event", "pull_request"),  # PR (także z forka) nie może dostarczyć dowodu
        ("event", "pull_request_target"),
        ("head_branch", "feat/x"),
        ("conclusion", "failure"),
        ("path", ".github/workflows/ci.yml"),  # inny workflow podstawiony pod wymagany
        ("repository", {"full_name": "atak/fork"}),
        ("head_repository", {"full_name": "atak/fork"}),
    ],
)
def test_mixed_workflow_run_from_wrong_source_rejected(key: str, value: object) -> None:
    run = {**GOOD_WF_RUN, key: value}
    found = gate_guard.verify_mixed("G3", mixed_proof(), REPO, "origin/main", mixed_github(run))
    assert any("deploy" in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_mixed_workflow_run_older_than_ci_commit_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class Res:
        def __init__(self, code: int) -> None:
            self.returncode = code

    def git(*args: str) -> Res:
        # commit przebiegu deploy ("a"*40) jest w historii main, ale starszy niż commit CI
        if (
            args[:2] == ("merge-base", "--is-ancestor")
            and args[2] == COMMIT
            and args[3] == "a" * 40
        ):
            return Res(1)
        return Res(0)

    monkeypatch.setattr(gate_guard, "git", git)
    found = gate_guard.verify_mixed(
        "G3", mixed_proof(), REPO, "origin/main", mixed_github(GOOD_WF_RUN)
    )
    assert any("starszego niż dowód CI" in p for p in found), found


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    "changes",
    [
        {"workflows": {}},  # brak wymaganego przebiegu
        {"local": {}},  # brak raportu lokalnego
        {"workflows": {"deploy": {"run_id": 2}, "extra": {"run_id": 3}}},  # dowód spoza reguł
        {"workflows": {"deploy": {"run_id": "2"}}},
        {"workflows": {"deploy": {"run_id": True}}},
        {"workflows": ["deploy"]},
        {"ci": None},
    ],
)
def test_mixed_proof_missing_or_malformed_parts_rejected(changes: dict[str, object]) -> None:
    found = gate_guard.verify_mixed(
        "G3", mixed_proof(**changes), REPO, "origin/main", mixed_github(GOOD_WF_RUN)
    )
    assert found, changes


@pytest.mark.usefixtures("g3")
@pytest.mark.parametrize(
    "entry",
    [
        {"path": "docs/gates/G3/inny.log", "sha256": "0" * 64},  # brak pliku na main
        {"path": REPORT_PATH, "sha256": "0" * 64},  # suma nie pasuje (plik zmieniony)
        {"path": "docs/gates/G3/../G2.md", "sha256": "0" * 64},  # wyjście z katalogu
        {"path": "docs/gates/G3/./x.log", "sha256": "0" * 64},
        {"path": "README.md", "sha256": "0" * 64},
        {"path": "docs/gates/G30/x.log", "sha256": "0" * 64},  # inny katalog z tym prefiksem
        {"path": REPORT_PATH, "sha256": "ABC"},
        {"path": REPORT_PATH},
    ],
)
def test_mixed_local_report_tampering_rejected(entry: dict[str, object]) -> None:
    proof = mixed_proof(local={"rebuild": entry})
    found = gate_guard.verify_mixed("G3", proof, REPO, "origin/main", mixed_github(GOOD_WF_RUN))
    assert any("rebuild" in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_mixed_local_report_without_pass_line_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    red = b"== G3 rebuild (local): FAIL, 2400 s, 2 manual steps ==\n"

    def show(_ref: str, _path: str) -> bytes:
        return red

    monkeypatch.setattr(gate_guard, "git_show_bytes", show)
    proof = mixed_proof(
        local={"rebuild": {"path": REPORT_PATH, "sha256": hashlib.sha256(red).hexdigest()}}
    )
    found = gate_guard.verify_mixed("G3", proof, REPO, "origin/main", mixed_github(GOOD_WF_RUN))
    assert any("brak linii PASS" in p for p in found), found


@pytest.mark.usefixtures("g3")
def test_gate_with_evidence_rejects_plain_ci_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    # Obejście: zaliczyć G3 samym zielonym przebiegiem CI, bez dowodów z infrastruktury.
    ci_only: dict[str, object] = {
        "gate": "G3",
        "type": "ci",
        "run_id": 1,
        "commit": COMMIT,
        "job": "x",
    }

    def load_ci(_gate: str, _ref: str) -> dict[str, object]:
        return ci_only

    monkeypatch.setattr(gate_guard, "load_proof", load_ci)
    found = gate_guard.check_gate("G3", REPO, "origin/main")
    assert any("wymagany dowód typu mixed" in p for p in found), found
    local_only: dict[str, object] = {**ci_only, "type": "local"}

    def load_local(_gate: str, _ref: str) -> dict[str, object]:
        return local_only

    monkeypatch.setattr(gate_guard, "load_proof", load_local)
    assert gate_guard.check_gate("G3", REPO, "origin/main") != []


def test_mixed_proof_rejected_for_gate_without_evidence() -> None:
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


@pytest.mark.parametrize(
    "bad",
    [
        {"workflows": {"x": {"workflow": WF, "events": ["pull_request"]}}},
        {"workflows": {"x": {"workflow": "../evil.yml", "events": ["push"]}}},
        {"workflows": {"x": {"workflow": WF, "events": []}}},
        {"workflows": {"X Y": {"workflow": WF, "events": ["push"]}}},
        {"local": {"r": {}}},
        {"local": {"r": {"pass_line": "("}}},
        {},
        [],
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
    def evidence(gate: str) -> dict[str, dict[str, dict[str, object]]] | None:
        return EVIDENCE if gate == "G3" else None

    monkeypatch.setattr(gate_guard, "gate_evidence", evidence)
    with pytest.raises(SystemExit, match="wymagany typ mixed"):
        gate_pass.main(["p", "3", "--local", "x.log"])
    with pytest.raises(SystemExit, match="niedozwolone"):
        gate_pass.main(["p", "2", "--run", "1", "--workflow", "deploy=2"])


def test_gate_pass_mixed_rejects_bad_pairs() -> None:
    with pytest.raises(SystemExit):
        gate_pass._pairs(["deploy"], "--workflow")  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(SystemExit):
        gate_pass._pairs(["a=1", "a=2"], "--workflow")  # pyright: ignore[reportPrivateUsage]
    assert gate_pass._pairs(["a=1", "b=2"], "--w") == {"a": "1", "b": "2"}  # pyright: ignore[reportPrivateUsage]
