"""Testy runnera bramek (scripts/gate.py): format YAML, SKIP nie liczy się jako PASS."""

from pathlib import Path

import gate
import pytest


def write_gate(root: Path, body: str) -> None:
    (root / "gates").mkdir(parents=True, exist_ok=True)
    (root / "gates" / "G9.yaml").write_text(body, encoding="utf-8")


BASE = "gate: G9\nstage: E9\ncriteria: test\n"


def run(root: Path, monkeypatch: pytest.MonkeyPatch, where: str) -> int:
    monkeypatch.setattr(gate, "ROOT", root)
    monkeypatch.setattr(gate, "WHERE", where)
    return gate.main(["gate.py", "9"])


def last_log(root: Path) -> str:
    logs = sorted((root / "reports" / "gates").glob("G9-*.log"))
    return logs[-1].read_text(encoding="utf-8")


def test_green_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_gate(tmp_path, BASE + "checks:\n  - id: ok\n    name: zawsze ok\n    run: 'true'\n")
    assert run(tmp_path, monkeypatch, "local") == 0
    assert "1 PASS, 0 FAIL, 0 SKIP" in last_log(tmp_path)


def test_failing_check_makes_gate_red(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_gate(
        tmp_path,
        BASE + "checks:\n  - id: bad\n    name: pada\n    run: 'echo powód; exit 3'\n",
    )
    assert run(tmp_path, monkeypatch, "local") == 1
    log = last_log(tmp_path)
    assert "FAIL pada" in log
    assert "powód" in log
    assert "CZERWONE" in log


def test_skip_is_not_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_gate(
        tmp_path,
        BASE + "checks:\n"
        "  - id: loc\n    name: tylko lokalnie\n    run: 'exit 1'\n"
        "    only: local\n    reason: klucz tylko u właściciela\n"
        "  - id: ok\n    name: ok\n    run: 'true'\n",
    )
    assert run(tmp_path, monkeypatch, "ci") == 0
    log = last_log(tmp_path)
    assert "SKIP tylko lokalnie [tylko local: klucz tylko u właściciela]" in log
    assert "1 PASS, 0 FAIL, 1 SKIP" in log


def test_missing_report_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_gate(
        tmp_path,
        BASE + "checks:\n  - id: ok\n    name: ok\n    run: 'true'\nreports:\n  - docs/brak.md\n",
    )
    assert run(tmp_path, monkeypatch, "local") == 1
    assert "BRAK: docs/brak.md" in last_log(tmp_path)


def test_coverage_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_gate(
        tmp_path,
        BASE + "checks:\n  - id: ok\n    name: ok\n    run: 'true'\n"
        "thresholds:\n  coverage_line_min: 80\n",
    )
    (tmp_path / "coverage.xml").write_text('<coverage line-rate="0.79"/>', encoding="utf-8")
    assert run(tmp_path, monkeypatch, "local") == 1
    (tmp_path / "coverage.xml").write_text('<coverage line-rate="0.80"/>', encoding="utf-8")
    assert run(tmp_path, monkeypatch, "local") == 0


@pytest.mark.parametrize(
    ("checks", "error"),
    [
        ("checks: []\n", "niepustą listą"),
        ("checks:\n  - id: a\n    name: a\n    run: x\n    only: ci\n", "wymaga pola 'reason'"),
        (
            "checks:\n  - id: a\n    name: a\n    run: x\n    only: gdzieś\n    reason: r\n",
            "local albo ci",
        ),
        ("checks:\n  - {id: a, name: a, run: x}\n  - {id: a, name: b, run: y}\n", "unikalne"),
    ],
)
def test_invalid_gate_file(tmp_path: Path, checks: str, error: str) -> None:
    path = tmp_path / "G9.yaml"
    path.write_text(BASE + checks, encoding="utf-8")
    with pytest.raises(ValueError, match=error):
        gate.load_gate(path)


def test_repo_gates_are_valid() -> None:
    for path in sorted((gate.ROOT / "gates").glob("G*.yaml")):
        loaded = gate.load_gate(path)
        assert loaded.gate == path.stem
