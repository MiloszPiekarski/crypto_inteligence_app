"""Workflow dowodu G3 (gates/G3.yaml, `evidence.workflows`): istnieją, job o nazwie z reguły
nie może przejść „na niby” (bez continue-on-error, bez wejść osłabiających sprawdzenie), sekrety
są tylko w środowiskach z właściwymi ograniczeniami. Plus sonda serwera i odczyt alertów."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import cast

import pg_checksums
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


def load_wf(name: str) -> dict[str, object]:
    data = yaml.safe_load((WF / name).read_text(encoding="utf-8"))
    # PyYAML czyta klucz `on` jako True.
    if True in data:
        data["on"] = data.pop(True)
    return cast(dict[str, object], data)


def evidence_rules() -> dict[str, dict[str, object]]:
    """Reguły `evidence.workflows` ze wszystkich bramek (G3, G4p, ...), klucz `G<nr>:<id>`."""
    rules: dict[str, dict[str, object]] = {}
    for path in sorted((ROOT / "gates").glob("G*.yaml")):
        gate = yaml.safe_load(path.read_text(encoding="utf-8"))
        evidence = cast(dict[str, object], gate.get("evidence") or {})
        workflows = cast(dict[str, dict[str, object]], evidence.get("workflows") or {})
        for key, rule in workflows.items():
            rules[f"{path.stem}:{key}"] = rule
    return rules


def test_evidence_rules_cover_g3_and_g4p() -> None:
    assert {"G3:deploy", "G3:restore-test", "G4p:data-report"} <= set(evidence_rules())


def job_by_name(wf: dict[str, object], name: str) -> dict[str, object]:
    jobs = cast(dict[str, dict[str, object]], wf["jobs"])
    found = [j for j in jobs.values() if j.get("name") == name]
    assert len(found) == 1, f"dokładnie jeden job o nazwie {name}"
    return found[0]


@pytest.mark.parametrize("key", sorted(evidence_rules()))
def test_evidence_workflow_cannot_pass_by_accident(key: str) -> None:
    rule = evidence_rules()[key]
    wf = load_wf(Path(str(rule["workflow"])).name)
    job = job_by_name(wf, str(rule["job"]))
    assert "continue-on-error" not in job
    steps = cast(list[dict[str, object]], job["steps"])
    assert all("continue-on-error" not in s for s in steps)
    # Każdy krok z `if` to tylko sprzątanie (always), nie pomijanie sprawdzeń.
    assert all(s.get("if") in (None, "always()") for s in steps)
    triggers = cast(dict[str, object], wf["on"])
    assert set(triggers) <= set(cast(list[str], rule["events"]))
    dispatch = triggers.get("workflow_dispatch")
    inputs = cast(dict[str, object], dispatch).get("inputs") if isinstance(dispatch, dict) else None
    assert not inputs, "bez wejść ręcznych"
    assert wf["permissions"] == {}, "uprawnienia tylko na poziomie joba"


def test_deploy_waits_for_ci_and_verifies_signature() -> None:
    wf = load_wf("deploy-staging.yml")
    job = job_by_name(wf, "deploy")
    assert job["environment"] == "staging"
    assert cast(dict[str, object], wf["concurrency"])["cancel-in-progress"] is False
    runs = "\n".join(str(s.get("run", "")) for s in cast(list[dict[str, object]], job["steps"]))
    assert "wait-for-ci.sh" in runs
    assert "cosign verify" in runs
    assert ".github/workflows/ci.yml@refs/heads/main" in runs
    assert "--certificate-oidc-issuer https://token.actions.githubusercontent.com" in runs
    assert "printf 'sha-%s\\n' \"$GITHUB_SHA\"" in runs
    assert 'deploy.sh "$tag"' in runs


def test_ci_signs_images_by_digest_on_main_only() -> None:
    job = cast(dict[str, dict[str, object]], load_wf("ci.yml")["jobs"])["images"]
    assert cast(dict[str, str], job["permissions"])["id-token"] == "write"
    steps = cast(list[dict[str, object]], job["steps"])
    sign = [s for s in steps if "cosign sign" in str(s.get("run", ""))]
    assert len(sign) == 1
    assert sign[0]["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert "@${DIGEST}" in str(sign[0]["run"])


@pytest.mark.parametrize("name", ["restore-test.yml", "external-scan.yml"])
def test_scheduled_workflows_use_only_probe_key(name: str) -> None:
    """Harmonogram = środowisko bez recenzenta, więc bez klucza wdrożeń i bez klucza age."""
    text = (WF / name).read_text(encoding="utf-8")
    job = next(iter(cast(dict[str, dict[str, object]], load_wf(name)["jobs"]).values()))
    assert job["environment"] == "staging-readonly"
    assert "STAGING_SSH_KEY" not in text
    assert "SOPS_AGE_KEY" not in text
    assert "STAGING_PROBE_SSH_KEY" in text


def test_secrets_only_in_job_with_environment() -> None:
    for path in WF.glob("*.yml"):
        wf = load_wf(path.name)
        for job_id, job in cast(dict[str, dict[str, object]], wf["jobs"]).items():
            uses_secret = "secrets." in yaml.safe_dump(job).replace("secrets.GITHUB_TOKEN", "")
            if uses_secret and path.name != "ci.yml":
                assert "environment" in job, f"{path.name}:{job_id} sekrety bez środowiska"


def load_script(path: Path) -> ModuleType:
    loader = importlib.machinery.SourceFileLoader(path.name.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


PROBE = ROOT / "infra" / "ansible" / "roles" / "base" / "files" / "goatcash-probe"


def test_probe_uses_same_sql_as_pg_checksums() -> None:
    probe = load_script(PROBE)
    assert probe.TABLES == pg_checksums.TABLES
    assert probe.ROW_SUM == pg_checksums.ROW_SUM


@pytest.mark.parametrize("cmd", ["", "bash", "restore-point; id", "lynis && id", "LYNIS"])
def test_probe_rejects_other_commands(
    cmd: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    probe = load_script(PROBE)
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", cmd)

    def no_run(*_a: object, **_k: object) -> None:
        pytest.fail("uruchomiono")

    monkeypatch.setattr(probe.subprocess, "run", no_run)
    assert probe.main() == 2
    assert "niedozwolone" in capsys.readouterr().err


def test_alert_reader_counts_only_active() -> None:
    wfa = load_script(ROOT / "scripts" / "ci" / "wait-for-alerts.py")
    body = json.dumps(
        [
            {"labels": {"alertname": "A"}, "status": {"state": "active"}},
            {"labels": {"alertname": "B"}, "status": {"state": "suppressed"}},
        ]
    )
    assert wfa.active_names(body) == {"A"}


def test_otel_reads_container_logs_from_docker_data_root() -> None:
    """Kolektor OTel musi czytać logi z katalogu, w którym Docker je zapisuje (data-root
    z Ansible); inaczej logi nie trafiają do Grafany (rozliczenie E3)."""
    daemon = (ROOT / "infra/ansible/roles/docker/templates/daemon.json.j2").read_text("utf-8")
    data_root = json.loads(daemon)["data-root"]
    compose = (ROOT / "infra/compose/staging/compose.yaml").read_text(encoding="utf-8")
    assert f":-{data_root}/containers}}:/var/lib/docker/containers:ro" in compose


def test_marketdata_probe_is_manual_fixed_and_leaves_nothing() -> None:
    """Sonda E4: tylko ręcznie, bez wejść, środowisko staging (main), stałe polecenie zdalne
    z jednorazowym kontenerem (`--rm`), bez klucza age i bez dostępu do bazy."""
    text = (WF / "marketdata-probe.yml").read_text(encoding="utf-8")
    wf = load_wf("marketdata-probe.yml")
    assert wf["on"] == {"workflow_dispatch": None}
    assert wf["permissions"] == {}
    job = job_by_name(wf, "probe")
    assert job["environment"] == "staging"
    assert job["permissions"] == {"id-token": "write"}
    runs = "\n".join(str(s.get("run", "")) for s in cast(list[dict[str, object]], job["steps"]))
    assert "docker run --rm" in runs
    assert "goatcash.marketdata probe --record bybit" in runs
    assert "${{" not in runs  # żadnych wyrażeń w poleceniach (wstrzyknięcie)
    for forbidden in ("SOPS_AGE_KEY", "psql", "compose exec", "deploy.sh", "rsync"):
        assert forbidden not in text


def test_data_report_is_manual_readonly_and_fails_on_criteria() -> None:
    """Dowód G4p: tylko ręcznie, bez wejść, raport w kontenerze ingest (rola tylko do
    odczytu w kodzie), kod raportu przechodzi przez pipefail, bez zmian na serwerze."""
    text = (WF / "data-report.yml").read_text(encoding="utf-8")
    wf = load_wf("data-report.yml")
    assert wf["on"] == {"workflow_dispatch": None}
    job = job_by_name(wf, "data-report")
    assert job["environment"] == "staging"
    assert job["permissions"] == {"id-token": "write"}
    steps = cast(list[dict[str, object]], job["steps"])
    report = next(str(s["run"]) for s in steps if "marketdata report" in str(s.get("run", "")))
    assert "set -o pipefail" in report
    assert "docker compose exec -T ingest python -m goatcash.marketdata report" in report
    assert "${{" not in report
    for forbidden in ("SOPS_AGE_KEY", "psql", "deploy.sh", "rsync", "docker compose up", "restart"):
        assert forbidden not in text
