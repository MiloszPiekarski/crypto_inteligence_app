"""Reguły alertów Grafany (infra/terraform/observability): każde zapytanie Prometheus jest
typu instant (próg działa tylko na jednej wartości; bez tego Grafana zgłasza „only reduced
data can be alerted on”, sprawdzone na staging 24.11.2026), a nazwy alertów używane przez
alert-drill.yml istnieją."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "infra" / "terraform" / "observability" / "main.tf"


def rules() -> list[str]:
    text = MAIN.read_text(encoding="utf-8")
    return re.split(r"\n  rule \{", text)[1:]


def test_every_prometheus_query_is_instant() -> None:
    found = rules()
    assert len(found) == 6
    for rule in found:
        query = rule.split('ref_id         = "C"')[0]
        assert "instant = true" in query, rule.splitlines()[1]
        assert "range   = false" in query or "range = false" in query, rule.splitlines()[1]


def test_no_multi_argument_aggregations() -> None:
    """`min(a, b)` nie jest poprawnym PromQL (błąd parse na staging 24.11.2026)."""
    text = MAIN.read_text(encoding="utf-8")
    assert not re.search(r"\bmin\(\s*min\(", text)


def test_alert_drill_names_exist() -> None:
    drill = (ROOT / ".github" / "workflows" / "alert-drill.yml").read_text(encoding="utf-8")
    names = re.findall(r'"(Dysk zajety > 80%|Kontener bazy lub Valkey niedostepny)"', drill)
    text = MAIN.read_text(encoding="utf-8")
    assert len(set(names)) == 2
    for name in set(names):
        assert f'name           = "{name}"' in text or f'name      = "{name}"' in text


def test_retention_alert_matches_pgbackrest_config() -> None:
    """Próg alertu retencji wynika z pgbackrest.conf: 30 dni + tydzień między pełnymi kopiami
    + zapas. Zmiana retencji bez zmiany progu (albo odwrotnie) ma paść tutaj."""
    conf = (ROOT / "infra/compose/staging/postgres/pgbackrest.conf").read_text(encoding="utf-8")
    assert "repo1-retention-full-type=time\n" in conf
    match = re.search(r"^repo1-retention-full=(\d+)$", conf, re.M)
    assert match
    days = int(match.group(1))
    rule = next(r for r in rules() if '"Retencja kopii nie dziala"' in r)
    assert "min(goatcash_backup_oldest_timestamp_seconds)) / 86400" in rule
    assert f"params = [{days + 7 + 2}]" in rule
    assert 'no_data_state  = "Alerting"' in rule
    backup = (ROOT / "infra/compose/staging/backup.sh").read_text(encoding="utf-8")
    assert "goatcash_backup_oldest_timestamp_seconds {oldest}" in backup
