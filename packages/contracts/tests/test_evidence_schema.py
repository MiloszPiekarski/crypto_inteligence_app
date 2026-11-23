"""Kontrakt `Evidence` v1 (roadmapa E2): poprawne przykłady przechodzą, błędne są odrzucane.

Bramka G2, sprawdzenie `evidence-v1` (`make evidence-test`).
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1] / "evidence"
SCHEMA = ROOT / "evidence.v1.schema.json"
# Pola wymagane przez roadmapę E2 (agent, wersje, aktyw, as_of, horyzont, p_up, kwantyle,
# regime_view, facts, invalidation, status) oraz identyfikator, wersja schematu i data_cutoff.
REQUIRED = {
    "evidence_id",
    "schema_version",
    "agent",
    "model_version",
    "asset",
    "horizon",
    "as_of",
    "data_cutoff",
    "p_up",
    "quantiles",
    "regime_view",
    "facts",
    "invalidation",
    "status",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def errors(document: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(load(SCHEMA), format_checker=FormatChecker())
    found = validator.iter_errors(document)  # pyright: ignore[reportUnknownMemberType]
    return [str(e.message) for e in found]


def test_schema_is_valid_and_requires_roadmap_fields() -> None:
    schema = load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    assert set(schema["required"]) == REQUIRED
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("path", sorted((ROOT / "examples/valid").glob("*.json")), ids=str)
def test_valid_examples_pass(path: Path) -> None:
    assert errors(load(path)) == []


@pytest.mark.parametrize("path", sorted((ROOT / "examples/invalid").glob("*.json")), ids=str)
def test_invalid_examples_are_rejected(path: Path) -> None:
    document = load(path)
    why = document.pop("_why")
    assert errors(document), f"przepuszczono: {why}"


def test_each_required_field_and_extra_field() -> None:
    example = load(ROOT / "examples/valid/01-pelny.json")
    for field in REQUIRED:
        broken = copy.deepcopy(example)
        del broken[field]
        assert errors(broken), f"brak {field}"
    assert errors({**example, "extra": 1})
    assert errors({**example, "agent": {**example["agent"], "extra": 1}})
    assert errors({**example, "schema_version": 2})
