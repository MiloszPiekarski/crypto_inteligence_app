"""Szybsze CI w ścieżce pracy (ADR-0008, punkt 7): `scripts/ci/zmiany.sh` i ci-ok.

Obrazy i bramki na macOS mogą zostać pominięte tylko w PR i tylko przy zmianach, które ich
nie dotyczą; na main i przy ręcznym uruchomieniu działa wszystko, a ci-ok nie przepuszcza
pominięcia żadnego innego joba.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ci" / "zmiany.sh"
BOTH = ["ubuntu-latest", "macos-15"]
GIT = shutil.which("git") or "git"
BASH = shutil.which("bash") or "bash"


def sh(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    """Stałe polecenia testu (git, bash ze skryptem z repo), bez danych z zewnątrz."""
    return subprocess.run(args, capture_output=True, text=True, **kwargs)  # noqa: S603, PLW1510  # pyright: ignore[reportCallIssue, reportArgumentType, reportUnknownVariableType]


def git(repo: Path, *args: str) -> str:
    return sh([GIT, "-C", str(repo), *args], check=True).stdout.strip()


def run(repo: Path, event: str, base: str) -> dict[str, str]:
    out = repo / "out.txt"
    out.write_text("")
    env = {**os.environ, "EVENT": event, "BASE": base, "GITHUB_OUTPUT": str(out)}
    sh([BASH, str(SCRIPT)], cwd=repo, env=env, check=True)
    return dict(line.split("=", 1) for line in out.read_text().splitlines())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "test")
    git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "README.md").write_text("a\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "baza")
    return tmp_path


def change(repo: Path, path: str) -> str:
    base = git(repo, "rev-parse", "HEAD")
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("zmiana\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "zmiana")
    return base


@pytest.mark.parametrize(
    ("path", "images", "systems"),
    [
        ("docs/stan-pracy.md", "false", ["ubuntu-latest"]),
        ("services/platform/src/goatcash/x.py", "false", ["ubuntu-latest"]),
        ("uv.lock", "true", ["ubuntu-latest"]),
        ("services/platform/pyproject.toml", "true", ["ubuntu-latest"]),
        ("services/executor/Dockerfile", "true", ["ubuntu-latest"]),
        ("scripts/gate.py", "false", BOTH),
        ("infra/compose/staging/backup.sh", "false", BOTH),
        ("gates/G4p.yaml", "false", BOTH),
        ("Makefile", "false", BOTH),
        (".github/workflows/ci.yml", "true", BOTH),
    ],
)
def test_pull_request_selects_jobs_by_changed_files(
    repo: Path, path: str, images: str, systems: list[str]
) -> None:
    base = change(repo, path)
    out = run(repo, "pull_request", base)
    assert out["obrazy"] == images
    assert json.loads(out["systemy"]) == systems


@pytest.mark.parametrize("event", ["push", "workflow_dispatch"])
def test_main_and_manual_run_everything(repo: Path, event: str) -> None:
    base = change(repo, "docs/x.md")
    out = run(repo, event, base)
    assert out["obrazy"] == "true"
    assert json.loads(out["systemy"]) == BOTH


def test_pull_request_without_base_fails(repo: Path) -> None:
    env = {**os.environ, "EVENT": "pull_request", "BASE": "", "GITHUB_OUTPUT": "/dev/null"}
    result = sh([BASH, str(SCRIPT)], cwd=repo, env=env, check=False)
    assert result.returncode != 0


def ci_jobs() -> dict[str, dict[str, object]]:
    data = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    return cast(dict[str, dict[str, object]], data["jobs"])


def test_ci_wires_change_detection() -> None:
    jobs = ci_jobs()
    assert jobs["images"]["if"] == "needs.zmiany.outputs.obrazy == 'true'"
    assert "zmiany" in cast(list[str], jobs["images"]["needs"])
    strategy = cast(dict[str, dict[str, object]], jobs["gate"]["strategy"])
    assert strategy["matrix"]["os"] == "${{ fromJSON(needs.zmiany.outputs.systemy) }}"
    assert jobs["coverage"]["needs"] == "test"
    needs = cast(list[str], jobs["ci-ok"]["needs"])
    # Wyjątek: `gate-next` (bramka etapu w toku) jest z założenia poza ci-ok, z
    # continue-on-error, dopóki bramka nie jest zaliczona (testy.md, sekcja 3, „Wdrożenie”).
    assert set(needs) == set(jobs) - {"ci-ok", "gate-next"}, "ci-ok musi czekać na wszystkie joby"
    if "gate-next" in jobs:
        assert jobs["gate-next"]["continue-on-error"] is True
        assert "zmiany" in cast(list[str], jobs["gate-next"]["needs"])
        next_strategy = cast(dict[str, dict[str, object]], jobs["gate-next"]["strategy"])
        assert next_strategy["matrix"]["os"] == "${{ fromJSON(needs.zmiany.outputs.systemy) }}"


def ci_ok_verdict(results: dict[str, str], obrazy: str) -> int:
    steps = cast(list[dict[str, object]], ci_jobs()["ci-ok"]["steps"])
    script = str(steps[0]["run"])
    needs = {k: {"result": v} for k, v in results.items()}
    env = {**os.environ, "NEEDS": json.dumps(needs), "OBRAZY": obrazy}
    return sh([BASH, "-c", script], env=env, check=False).returncode


JOBS = ["zmiany", "lint", "types", "test", "gitleaks", "images", "coverage", "gate"]
ALL_OK = dict.fromkeys(JOBS, "success")


def test_ci_ok_accepts_only_justified_skip_of_images() -> None:
    assert ci_ok_verdict(ALL_OK, "true") == 0
    assert ci_ok_verdict({**ALL_OK, "images": "skipped"}, "false") == 0
    # Obrazy pominięte, choć zmiany ich wymagały (np. czerwony gitleaks): czerwone.
    assert ci_ok_verdict({**ALL_OK, "images": "skipped"}, "true") != 0
    # Job `zmiany` nie zielony: pominięcie obrazów nie jest uzasadnione.
    failed = {**ALL_OK, "zmiany": "failure", "images": "skipped"}
    assert ci_ok_verdict(failed, "") != 0
    for job in ["lint", "types", "test", "gitleaks", "coverage", "gate"]:
        assert ci_ok_verdict({**ALL_OK, job: "skipped"}, "false") != 0, job
        assert ci_ok_verdict({**ALL_OK, job: "failure"}, "false") != 0, job
