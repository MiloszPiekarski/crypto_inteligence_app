"""Testy gate-guard i gate_pass: dowód bramki nie może zostać przyjęty na słowo."""

import json
from collections.abc import Callable
from pathlib import Path

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
    triggers = wf[True]["pull_request"]["types"]  # PyYAML czyta klucz `on` jako True
    assert "opened" not in triggers
    assert {"synchronize", "labeled", "unlabeled", "reopened"} <= set(triggers)
    assert "concurrency" not in wf
    assert wf["permissions"].get("pull-requests") == "read"


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
