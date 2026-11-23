"""Testy skryptu kompletności wymagań (bramka G2, `requirements`)."""

import copy
from collections.abc import Callable
from typing import Any

import check_requirements as cr
import pytest
import yaml

ROADMAP = """
## E3. Infra
## E14. Bot
## E17. Utrzymanie

| ID    | Wymaganie | Mierzenie |
| NF-01 | x         | y         |
"""
TESTS = """
| G3     | E3   | kryterium |
| G14a   | E14a | kryterium |
| G14b   | E14b | kryterium |
"""
GOOD: dict[str, Any] = {
    "functional": [
        {"id": "F-01", "stage": "E3", "title": "t", "measure": "m", "target": "< 30 min",
         "gate": "G3", "source": "roadmapa"},
        {"id": "F-02", "stage": "E14", "title": "t", "measure": "m", "target": "≤ 5 s",
         "gate": "G14b", "source": "roadmapa"},
        {"id": "F-03", "stage": "E17", "title": "t", "measure": "m", "target": "1 raport",
         "gate": None, "source": "doprecyzowanie"},
    ],
    "non_functional": [
        {"id": "NF-01", "title": "t", "measure": "m", "target": "p95 ≤ 300 ms",
         "gate": "G3", "source": "roadmapa"},
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
    ],
)
def test_each_rule_catches_its_violation(change: Change, message: str) -> None:
    found = errors_after(change)
    assert any(message in e for e in found), found
