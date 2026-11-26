"""Testy skryptu kompletności wymagań (bramka G2, `requirements`)."""

import copy
from collections.abc import Callable
from typing import Any

import check_requirements as cr
import pytest
import yaml

ROADMAP = """
## E3. Infra
## E4. Dane
## E14. Bot
## E17. Utrzymanie

| ID    | Wymaganie | Mierzenie |
| NF-01 | x         | y         |
"""
TESTS = """
| G3     | E3   | kryterium |
| G4     | E4   | kryterium |
| G4p    | E4   | kryterium pracy |
| G14a   | E14a | kryterium |
| G14b   | E14b | kryterium |
"""
GOOD: dict[str, Any] = {
    "functional": [
        {"id": "F-01", "stage": "E3", "title": "t", "measure": "m", "target": "< 30 min",
         "gate": "G3", "track": "praca", "source": "roadmapa"},
        {"id": "F-02", "stage": "E14", "title": "t", "measure": "m", "target": "≤ 5 s",
         "gate": "G14b", "track": "produkt", "source": "roadmapa"},
        {"id": "F-03", "stage": "E17", "title": "t", "measure": "m", "target": "1 raport",
         "gate": None, "track": "produkt", "source": "doprecyzowanie",
         "accepted": "2026-11-23", "note": "próg doprecyzowany"},
        {"id": "F-04", "stage": "E4", "title": "t", "measure": "m", "target": "≥ 99,9%",
         "gate": "G4", "track": "praca", "work_gate": "G4p", "work_target": "20 par",
         "source": "roadmapa"},
    ],
    "non_functional": [
        {"id": "NF-01", "title": "t", "measure": "m", "target": "p95 ≤ 300 ms",
         "gate": "G3", "track": "produkt", "source": "roadmapa"},
    ],
}  # fmt: skip


Data = dict[str, Any]
Change = Callable[[Data], None]


def setf(index: int, key: str, value: object, group: str = "functional") -> Change:
    def change(data: Data) -> None:
        data[group][index][key] = value

    return change


def popf(index: int, key: str) -> Change:
    def change(data: Data) -> None:
        del data["functional"][index][key]

    return change


def drop_stage_e14(data: Data) -> None:
    del data["functional"][1]


def drop_work_requirement(data: Data) -> None:
    del data["functional"][3]


def drop_nf(data: Data) -> None:
    data["non_functional"] = []


def drop_functional(data: Data) -> None:
    data["functional"] = []


def errors_after(change: Change) -> list[str]:
    data = copy.deepcopy(GOOD)
    change(data)
    return cr.check(data, ROADMAP, TESTS)


def test_good_data_passes() -> None:
    assert cr.check(GOOD, ROADMAP, TESTS) == []


def test_note_allowed_for_roadmap_source() -> None:
    data = copy.deepcopy(GOOD)
    data["functional"][0]["note"] = "wyjaśnienie"
    assert cr.check(data, ROADMAP, TESTS) == []


def test_repository_requirements_pass() -> None:
    data = yaml.safe_load(cr.REQUIREMENTS.read_text("utf-8"))
    roadmap = cr.ROADMAP.read_text("utf-8")
    assert cr.check(data, roadmap, cr.TESTS.read_text("utf-8")) == []
    assert cr.main() == 0


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (setf(1, "id", "F-01"), "powtórzony"),
        (setf(0, "id", "F1"), "zły identyfikator"),
        (setf(0, "target", "szybko"), "bez liczby"),
        (setf(0, "stage", "E99"), "nie istnieje"),
        (setf(0, "gate", "G14a"), "nie należy do etapu"),
        (setf(0, "gate", None), "nie należy do etapu"),
        (setf(2, "gate", "G3"), "nie należy do etapu"),
        (popf(0, "measure"), "brak pól"),
        (setf(0, "title", ""), "brak pól"),
        (setf(0, "extra", 1), "nieznane pola"),
        (setf(0, "source", "wymyślone"), "source"),
        (drop_stage_e14, "etap E14 nie ma"),
        (drop_nf, "NF-xx różne"),
        (setf(0, "gate", "G99", group="non_functional"), "nie istnieje w testy.md"),
        (drop_functional, "brak wymagań funkcjonalnych"),
        (popf(2, "accepted"), "bez akceptacji"),
        (setf(2, "accepted", "jutro"), "bez akceptacji"),
        (popf(2, "note"), "bez wyjaśnienia"),
        (setf(2, "note", " "), "bez wyjaśnienia"),
        (setf(0, "accepted", "2026-11-23"), "accepted dotyczy tylko"),
        # Ścieżki realizacji (ADR-0008).
        (popf(0, "track"), "brak pól"),
        (setf(0, "track", "obie"), "track musi"),
        (popf(3, "work_gate"), "to nie bramka pracy"),
        (setf(3, "work_gate", "G4"), "to nie bramka pracy"),
        (setf(3, "work_gate", "G5p"), "to nie bramka pracy"),
        (setf(3, "work_target", "dużo"), "work_target bez liczby"),
        (popf(3, "work_target"), "work_target bez liczby"),
        (setf(3, "gate", "G4p"), "nie należy do etapu"),
        (setf(3, "track", "produkt"), "tylko dla ścieżki pracy"),
        (drop_work_requirement, "bramka pracy G4p nie ma"),
        (setf(0, "work_gate", "G4p"), "tylko dla ścieżki pracy"),
        (setf(1, "work_target", "1 raz"), "tylko dla ścieżki pracy"),
        (setf(0, "gate", "G4p", group="non_functional"), "nie istnieje w testy.md"),
    ],
)
def test_each_rule_catches_its_violation(change: Change, message: str) -> None:
    found = errors_after(change)
    assert any(message in e for e in found), found
