"""Kompletność wymagań (bramka G2, sprawdzenie `requirements`): `make requirements-check`.

Sprawdza `docs/wymagania.yaml` względem dokumentacji:
- każde F-xx i NF-xx ma unikalny identyfikator, tytuł, sposób pomiaru, próg z liczbą i źródło;
- próg `source: doprecyzowanie` (inny niż w roadmapie) ma akceptację właściciela
  (`accepted`, data RRRR-MM-DD) i wyjaśnienie różnicy (`note`);
- każde F-xx ma etap, który istnieje w roadmapie, a jego bramka to bramka tego etapu albo
  jednej z jego faz z tabeli bramek w testy.md (E14 -> G14a/b/c; etap bez bramki: null);
- każdy etap od E3 wzwyż ma co najmniej jedno F-xx (nic nie zostało pominięte);
- NF-xx to dokładnie identyfikatory z tabeli wymagań niefunkcjonalnych roadmapy E2;
- każde F-xx i NF-xx ma ścieżkę (`track: praca|produkt`, ADR-0008); wymaganie ścieżki pracy
  z etapu E4+ (NF: z pełną bramką od G4) ma `work_gate` (bramka pracy G<nr>p z sekcji 3a
  testy.md, należąca do etapu) i `work_target` z liczbą; wymaganie produktu ich nie ma;
- każda bramka pracy z testy.md ma co najmniej jedno wymaganie z tym `work_gate`.
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
FIELDS_F = ("id", "stage", "title", "measure", "target", "gate", "track", "source")
FIELDS_NF = ("id", "title", "measure", "target", "gate", "track", "source")
SOURCES = ("roadmapa", "doprecyzowanie")
TRACKS = ("praca", "produkt")
OPTIONAL = ("accepted", "note", "work_gate", "work_target")
WORK_GATE_RE = r"G\d+[a-c]?p"
FIRST_WORK_STAGE = 4  # E0 do E3 zaliczone w pełnym zakresie; bramki pracy od E4 (ADR-0008)


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


def source_errors(rid: str, item: dict[str, Any]) -> list[str]:
    """Próg spoza roadmapy wymaga akceptacji właściciela i wyjaśnienia różnicy."""
    if item.get("source") != "doprecyzowanie":
        return (
            [f"{rid}: accepted dotyczy tylko source: doprecyzowanie"] if "accepted" in item else []
        )
    errors: list[str] = []
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(item.get("accepted", ""))):
        errors.append(f"{rid}: doprecyzowanie bez akceptacji właściciela (accepted: RRRR-MM-DD)")
    if not str(item.get("note", "")).strip():
        errors.append(f"{rid}: doprecyzowanie bez wyjaśnienia różnicy od roadmapy (note)")
    return errors


def gate_number(gate: object) -> int:
    match = re.fullmatch(r"G(\d+)[a-z]?", str(gate))
    return int(match.group(1)) if match else -1


def track_errors(
    rid: str, item: dict[str, Any], needs_work_gate: bool, allowed_work: set[str]
) -> list[str]:
    """Ścieżka pracy albo produktu (ADR-0008): bramka i próg pracy tylko tam, gdzie trzeba."""
    track = item.get("track")
    if track not in TRACKS:
        return [f"{rid}: track musi być jednym z {TRACKS}"]
    has_work = "work_gate" in item or "work_target" in item
    if track == "produkt" or not needs_work_gate:
        return [f"{rid}: work_gate i work_target tylko dla ścieżki pracy od E4"] if has_work else []
    errors: list[str] = []
    gate = item.get("work_gate")
    if not re.fullmatch(WORK_GATE_RE, str(gate)) or gate not in allowed_work:
        want = sorted(allowed_work) or "brak bramki pracy w testy.md"
        errors.append(f"{rid}: work_gate {gate} to nie bramka pracy tego wymagania: {want}")
    if not re.search(r"\d", str(item.get("work_target", ""))):
        errors.append(f"{rid}: work_target bez liczby: {item.get('work_target')!r}")
    return errors


def stage_gate_errors(
    rid: str, item: dict[str, Any], allowed: set[str], work_gates: set[str]
) -> list[str]:
    """Pełna bramka F-xx należy do etapu; bramka pracy jak w `track_errors`."""
    stage = str(item.get("stage"))
    gate = item.get("gate")
    full = allowed - work_gates
    errors: list[str] = []
    if (gate not in full) if full else (gate is not None):
        want = sorted(full) or "null (etap bez bramki)"
        errors.append(f"{rid}: bramka {gate} nie należy do etapu {stage}: {want}")
    work = stage_key(stage) >= (FIRST_WORK_STAGE, "")
    return errors + track_errors(rid, item, work, allowed & work_gates)


def unused_work_gates(work_gates: set[str], items: list[dict[str, Any]]) -> list[str]:
    used = {str(i.get("work_gate")) for i in items}
    return [
        f"bramka pracy {g} nie ma żadnego wymagania (work_gate)" for g in sorted(work_gates - used)
    ]


def check(data: dict[str, Any], roadmap: str, tests: str) -> list[str]:
    errors: list[str] = []
    stages = roadmap_stages(roadmap)
    rows = gate_rows(tests)
    all_gates = {g for g, _ in rows}
    work_gates = {g for g in all_gates if re.fullmatch(WORK_GATE_RE, g)}
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
        errors.extend(source_errors(rid, item))
        extra = set(item) - set(fields) - set(OPTIONAL)
        if extra:
            errors.append(f"{rid}: nieznane pola {sorted(extra)}")
        return rid

    for item in functional:
        rid = common(item, FIELDS_F, r"F-\d{2}")
        stage = str(item.get("stage"))
        if stage not in stages:
            errors.append(f"{rid}: etap {stage} nie istnieje w roadmapie")
        errors.extend(stage_gate_errors(rid, item, gates_for(stage, rows), work_gates))

    for item in non_functional:
        rid = common(item, FIELDS_NF, r"NF-\d{2}")
        if item.get("gate") not in all_gates - work_gates:
            errors.append(f"{rid}: bramka {item.get('gate')} nie istnieje w testy.md")
        work = gate_number(item.get("gate")) >= FIRST_WORK_STAGE
        errors.extend(track_errors(rid, item, work, work_gates))

    covered = {str(i.get("stage")) for i in functional}
    for stage in stages:
        if stage_key(stage) >= (3, "") and stage not in covered:
            errors.append(f"etap {stage} nie ma żadnego wymagania F-xx")

    errors.extend(unused_work_gates(work_gates, [*functional, *non_functional]))
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
