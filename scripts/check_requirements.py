"""Kompletność wymagań (bramka G2, sprawdzenie `requirements`): `make requirements-check`.

Sprawdza `docs/wymagania.yaml` względem dokumentacji:
- każde F-xx i NF-xx ma unikalny identyfikator, tytuł, sposób pomiaru, próg z liczbą i źródło;
- każde F-xx ma etap, który istnieje w roadmapie, a jego bramka to bramka tego etapu albo
  jednej z jego faz z tabeli bramek w testy.md (E14 -> G14a/b/c; etap bez bramki: null);
- każdy etap od E3 wzwyż ma co najmniej jedno F-xx (nic nie zostało pominięte);
- NF-xx to dokładnie identyfikatory z tabeli wymagań niefunkcjonalnych roadmapy E2.
"""

import re
import sys
from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "docs/wymagania.yaml"
ROADMAP = ROOT / "docs/dokumentacja/roadmapa.md"
TESTS = ROOT / "docs/dokumentacja/testy.md"
FIELDS_F = ("id", "stage", "title", "measure", "target", "gate", "source")
FIELDS_NF = ("id", "title", "measure", "target", "gate", "source")
SOURCES = ("roadmapa", "doprecyzowanie")


def stage_key(stage: str) -> tuple[int, str]:
    match = re.fullmatch(r"E(\d+)([a-z]?)", stage)
    return (int(match.group(1)), match.group(2)) if match else (-1, "")


def roadmap_stages(text: str) -> list[str]:
    return re.findall(r"^## (E\d+[a-z]?)\. ", text, flags=re.MULTILINE)


def gate_rows(text: str) -> list[tuple[str, str]]:
    """(bramka, etap) z tabeli bramek w testy.md (wiersze `| G<nr> | E<nr> | ...`)."""
    return re.findall(r"^\| (G\d+[a-z]?)\s+\| (E\d+[a-z]?)\s+\|", text, flags=re.MULTILINE)


def gates_for(stage: str, rows: list[tuple[str, str]]) -> set[str]:
    """Bramki etapu i jego faz (E14 -> G14a, G14b, G14c z faz E14a…c)."""
    return {g for g, s in rows if s == stage or re.fullmatch(re.escape(stage) + "[a-z]", s)}


def roadmap_nf_ids(text: str) -> set[str]:
    return set(re.findall(r"^\| (NF-\d{2})\s+\|", text, flags=re.MULTILINE))


def check(data: dict[str, Any], roadmap: str, tests: str) -> list[str]:
    errors: list[str] = []
    stages = roadmap_stages(roadmap)
    rows = gate_rows(tests)
    all_gates = {g for g, _ in rows}
    functional = cast(list[dict[str, Any]], data.get("functional") or [])
    non_functional = cast(list[dict[str, Any]], data.get("non_functional") or [])
    seen: set[str] = set()

    def common(item: dict[str, Any], fields: tuple[str, ...], pattern: str) -> str:
        rid = str(item.get("id"))
        if not re.fullmatch(pattern, rid):
            errors.append(f"{rid}: zły identyfikator (wzorzec {pattern})")
        if rid in seen:
            errors.append(f"{rid}: identyfikator powtórzony")
        seen.add(rid)
        missing = [f for f in fields if f not in item or (item[f] in ("", None) and f != "gate")]
        if missing:
            errors.append(f"{rid}: brak pól {missing}")
        if not re.search(r"\d", str(item.get("target", ""))):
            errors.append(f"{rid}: próg bez liczby (niemierzalny): {item.get('target')!r}")
        if item.get("source") not in SOURCES:
            errors.append(f"{rid}: source musi być jednym z {SOURCES}")
        extra = set(item) - set(fields)
        if extra:
            errors.append(f"{rid}: nieznane pola {sorted(extra)}")
        return rid

    for item in functional:
        rid = common(item, FIELDS_F, r"F-\d{2}")
        stage = str(item.get("stage"))
        if stage not in stages:
            errors.append(f"{rid}: etap {stage} nie istnieje w roadmapie")
        allowed = gates_for(stage, rows)
        gate = item.get("gate")
        if (gate not in allowed) if allowed else (gate is not None):
            want = sorted(allowed) or "null (etap bez bramki)"
            errors.append(f"{rid}: bramka {gate} nie należy do etapu {stage}: {want}")

    for item in non_functional:
        rid = common(item, FIELDS_NF, r"NF-\d{2}")
        if item.get("gate") not in all_gates:
            errors.append(f"{rid}: bramka {item.get('gate')} nie istnieje w testy.md")

    covered = {str(i.get("stage")) for i in functional}
    for stage in stages:
        if stage_key(stage) >= (3, "") and stage not in covered:
            errors.append(f"etap {stage} nie ma żadnego wymagania F-xx")

    nf_doc = roadmap_nf_ids(roadmap)
    nf_here = {str(i.get("id")) for i in non_functional}
    if nf_here != nf_doc:
        errors.append(
            f"NF-xx różne od roadmapy: brak {sorted(nf_doc - nf_here)}, "
            f"nadmiar {sorted(nf_here - nf_doc)}"
        )
    if not functional:
        errors.append("brak wymagań funkcjonalnych")
    return errors


def main() -> int:
    data = cast(dict[str, Any], yaml.safe_load(REQUIREMENTS.read_text("utf-8")))
    errors = check(data, ROADMAP.read_text("utf-8"), TESTS.read_text("utf-8"))
    for error in errors:
        print(f"BŁĄD {error}", file=sys.stderr)
    functional = cast(list[object], data.get("functional") or [])
    non_functional = cast(list[object], data.get("non_functional") or [])
    print(
        f"wymagania: {len(functional)} F, {len(non_functional)} NF, "
        f"{len(errors)} błędów -> {'OK' if not errors else 'NIEKOMPLETNE'}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
