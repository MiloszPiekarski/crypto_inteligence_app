"""Uruchamia bramkę jakości zdefiniowaną w gates/G<nr>.yaml (make gate G=<nr>).

Plik bramki zawiera komendy testów, progi i wymagane raporty (zakładka „Testy
i quality gates”). Pełny wynik trafia do reports/gates/G<nr>-<czas UTC>.log,
a w CI katalog reports/gates/ jest publikowany jako artefakt.

Sprawdzenie z `only: local` albo `only: ci` jest w innym miejscu pomijane
i widoczne w raporcie jako SKIP z powodem. Pominięcie nigdy nie liczy się
jako PASS.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO, cast

import yaml

ROOT = Path(__file__).resolve().parent.parent
WHERE = "ci" if os.environ.get("CI") == "true" else "local"


@dataclass(frozen=True)
class Check:
    id: str
    name: str
    run: str
    only: str | None
    reason: str | None


@dataclass(frozen=True)
class Gate:
    gate: str
    stage: str
    criteria: str
    checks: list[Check]
    coverage_line_min: float | None
    required_reports: list[str]


def _str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"pole '{key}' musi być niepustym tekstem")
    return value


def load_gate(path: Path) -> Gate:
    raw = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: oczekiwano mapy YAML")
    data = cast(dict[str, object], raw)
    checks: list[Check] = []
    raw_checks = data.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise ValueError(f"{path}: 'checks' musi być niepustą listą")
    for item in cast(list[object], raw_checks):
        if not isinstance(item, dict):
            raise ValueError(f"{path}: każdy element 'checks' musi być mapą")
        c = cast(dict[str, object], item)
        only = c.get("only")
        if only not in (None, "local", "ci"):
            raise ValueError(f"{path}: 'only' może mieć wartość local albo ci")
        reason = c.get("reason")
        if only is not None and not isinstance(reason, str):
            raise ValueError(f"{path}: sprawdzenie z 'only' wymaga pola 'reason'")
        checks.append(
            Check(
                id=_str(c, "id"),
                name=_str(c, "name"),
                run=_str(c, "run"),
                only=cast(str | None, only),
                reason=cast(str | None, reason),
            )
        )
    ids = [c.id for c in checks]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: identyfikatory sprawdzeń muszą być unikalne")
    thresholds = cast(object, data.get("thresholds") or {})
    if not isinstance(thresholds, dict):
        raise ValueError(f"{path}: 'thresholds' musi być mapą")
    cov = cast(dict[str, object], thresholds).get("coverage_line_min")
    if cov is not None and not isinstance(cov, int | float):
        raise ValueError(f"{path}: 'coverage_line_min' musi być liczbą")
    reports = cast(object, data.get("reports") or [])
    if not isinstance(reports, list) or not all(
        isinstance(r, str) for r in cast(list[object], reports)
    ):
        raise ValueError(f"{path}: 'reports' musi być listą ścieżek")
    return Gate(
        gate=_str(data, "gate"),
        stage=_str(data, "stage"),
        criteria=_str(data, "criteria"),
        checks=checks,
        coverage_line_min=float(cov) if cov is not None else None,
        required_reports=cast(list[str], reports),
    )


def coverage_line_rate(path: Path) -> float:
    root = ET.parse(path).getroot()  # noqa: S314 - plik generuje nasz pytest-cov
    return float(root.get("line-rate", "0")) * 100


USAGE_ARGC = 2


class Report:
    """Wypisuje wynik na ekran i jednocześnie do pliku raportu."""

    def __init__(self, log: TextIO) -> None:
        self.log = log
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.executed = 0  # uruchomione sprawdzenia z `checks` (bez progów i raportów)

    def out(self, line: str = "") -> None:
        print(line, flush=True)
        self.log.write(line + "\n")

    def result(self, ok: bool, text: str) -> None:
        self.out(f"  {'PASS' if ok else 'FAIL'} {text}")
        if ok:
            self.passed += 1
        else:
            self.failed += 1


def git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 - git z PATH, jak w Makefile
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() or "brak"


def check_env() -> dict[str, str]:
    """Środowisko sprawdzeń: narzędzia z `make tools` (.tools/bin) mają pierwszeństwo,
    żeby lokalnie działały te same przypięte wersje co w CI."""
    env = dict(os.environ)
    tools = ROOT / ".tools" / "bin"
    if tools.is_dir():
        env["PATH"] = f"{tools}{os.pathsep}{env.get('PATH', '')}"
    return env


def run_check(report: Report, check: Check) -> None:
    if check.only is not None and check.only != WHERE:
        report.out(f"  SKIP {check.name} [tylko {check.only}: {check.reason}]")
        report.skipped += 1
        return
    start = time.monotonic()
    # Komendy pochodzą z gates/G<nr>.yaml w repozytorium (przegląd w PR), jak cele Makefile.
    proc = subprocess.run(  # noqa: S603
        ["bash", "-o", "pipefail", "-c", check.run],  # noqa: S607
        cwd=ROOT,
        env=check_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    took = time.monotonic() - start
    report.executed += 1
    if proc.returncode == 0:
        report.result(True, f"{check.name} ({took:.0f} s)")
        return
    report.result(False, f"{check.name} ({took:.0f} s, kod {proc.returncode})")
    for line in (proc.stdout + proc.stderr).strip().splitlines()[-25:]:
        report.out(f"       {line}")


def check_coverage(report: Report, minimum: float) -> None:
    cov_file = ROOT / "coverage.xml"
    if not cov_file.is_file():
        report.result(False, "próg pokrycia: brak coverage.xml (czy testy się uruchomiły?)")
        return
    rate = coverage_line_rate(cov_file)
    sign = ">=" if rate >= minimum else "<"
    report.result(rate >= minimum, f"próg pokrycia linii {rate:.1f}% {sign} {minimum:.0f}%")


def open_new_report(log_dir: Path, base: str) -> tuple[Path, TextIO]:
    """Tworzy NOWY plik raportu; nigdy nie nadpisuje raportu innego przebiegu.

    Dwa przebiegi w tej samej sekundzie dostają osobne pliki (sufiks -2, -3, ...).
    Tryb "x" zakłada plik atomowo, więc równoległe przebiegi nie mogą trafić w ten sam.
    """
    for n in range(1, 1000):
        path = log_dir / (f"{base}.log" if n == 1 else f"{base}-{n}.log")
        try:
            return path, path.open("x", encoding="utf-8")
        except FileExistsError:
            continue
    raise RuntimeError(f"nie udało się utworzyć unikalnego raportu {base}")


def main(argv: list[str]) -> int:
    if len(argv) != USAGE_ARGC:
        print("Użycie: scripts/gate.py <nr>, np. scripts/gate.py 1")
        return 2
    gate_file = ROOT / "gates" / f"G{argv[1]}.yaml"
    if not gate_file.is_file():
        print(f"Brak definicji bramki: {gate_file.relative_to(ROOT)}")
        return 2
    gate = load_gate(gate_file)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_dir = ROOT / "reports" / "gates"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path, log = open_new_report(log_dir, f"{gate.gate}-{stamp}")

    with log:
        report = Report(log)
        report.out(f"Bramka {gate.gate} ({gate.stage}) | commit {git_commit()} | {stamp} | {WHERE}")
        report.out(f"Kryteria: {gate.criteria}")
        report.out("-" * 60)
        for check in gate.checks:
            run_check(report, check)
        if report.executed == 0:
            # Bramka, w której wszystko pominięto, niczego nie sprawdziła: to nie jest zielone.
            report.result(False, f"żadne sprawdzenie nie zostało uruchomione ({WHERE})")
        if gate.coverage_line_min is not None:
            check_coverage(report, gate.coverage_line_min)
        for path in gate.required_reports:
            exists = (ROOT / path).is_file()
            report.result(exists, f"wymagany raport {'istnieje' if exists else 'BRAK'}: {path}")
        report.out()
        report.out(
            f"== {gate.gate} ({WHERE}): {report.passed} PASS, "
            f"{report.failed} FAIL, {report.skipped} SKIP =="
        )
        verdict = "ZIELONE" if report.failed == 0 else "CZERWONE"
        report.out(f"WYNIK: {gate.gate} testy automatyczne {verdict}")
    print(f"Raport: {log_path.relative_to(ROOT)}")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
