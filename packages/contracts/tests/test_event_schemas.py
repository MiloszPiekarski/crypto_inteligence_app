"""Schematy zdarzeń (ADR-0003): poprawne przykłady przechodzą, błędne są odrzucane.

Bramka G2, sprawdzenie `event-schemas` (`make event-schemas-test`). Oprócz przykładów
z plików test sam psuje każdy poprawny przykład (brak pola, pole nadmiarowe, zły typ,
zła wersja), żeby schemat nie mógł po cichu przepuszczać niekompletnych zdarzeń.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

EVENTS = Path(__file__).resolve().parents[1] / "events"
EXAMPLES = EVENTS / "examples"
# Typy zdarzeń z roadmapy E2 („Kontrakty”) i ADR-0003.
TYPES = (
    "candle.closed",
    "features.ready",
    "evidence.published",
    "assessment.updated",
    "narrative.ready",
    "alert.triggered",
    "order_intent.created",
    "order.updated",
)
ENVELOPE_FIELDS = (
    "event_id",
    "type",
    "schema_version",
    "occurred_at",
    "producer",
    "correlation_id",
    "payload",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text("utf-8"))


def registry() -> Registry[Any]:
    resources = [
        (str(s["$id"]), Resource.from_contents(s))
        for s in (load(p) for p in EVENTS.glob("*.schema.json"))
    ]
    return Registry[Any]().with_resources(resources)


def validator(event_type: str) -> Draft202012Validator:
    schema = load(EVENTS / f"{event_type}.v1.schema.json")
    return Draft202012Validator(schema, registry=registry(), format_checker=FormatChecker())


def valid_example(event_type: str) -> dict[str, Any]:
    return load(EXAMPLES / event_type / "valid" / "01.json")


def errors(event_type: str, document: dict[str, Any]) -> list[str]:
    found = validator(event_type).iter_errors(document)  # pyright: ignore[reportUnknownMemberType]
    return [str(e.message) for e in found]


def test_every_event_type_has_schema_and_examples() -> None:
    schemas = {p.name.removesuffix(".v1.schema.json") for p in EVENTS.glob("*.v1.schema.json")}
    assert schemas == set(TYPES)
    for event_type in TYPES:
        assert list((EXAMPLES / event_type / "valid").glob("*.json")), event_type
        assert list((EXAMPLES / event_type / "invalid").glob("*.json")), event_type


@pytest.mark.parametrize("path", sorted(EVENTS.glob("*.schema.json")), ids=lambda p: p.name)
def test_schemas_are_valid_draft_2020_12(path: Path) -> None:
    Draft202012Validator.check_schema(load(path))


@pytest.mark.parametrize("event_type", TYPES)
def test_valid_examples_pass(event_type: str) -> None:
    for path in sorted((EXAMPLES / event_type / "valid").glob("*.json")):
        assert errors(event_type, load(path)) == [], path


@pytest.mark.parametrize(
    "path",
    sorted(EXAMPLES.glob("*/invalid/*.json")),
    ids=lambda p: f"{p.parts[-3]}/{p.stem}",
)
def test_invalid_examples_are_rejected(path: Path) -> None:
    document = load(path)
    why = document.pop("_why")  # opis przypadku, nie część zdarzenia
    assert errors(path.parts[-3], document), f"{path}: przepuszczono ({why})"


@pytest.mark.parametrize("event_type", TYPES)
def test_missing_required_fields_rejected(event_type: str) -> None:
    example = valid_example(event_type)
    for field in ENVELOPE_FIELDS:
        broken = copy.deepcopy(example)
        del broken[field]
        assert errors(event_type, broken), f"brak {field}"
    schema = load(EVENTS / f"{event_type}.v1.schema.json")
    for field in schema["properties"]["payload"]["required"]:
        broken = copy.deepcopy(example)
        del broken["payload"][field]
        assert errors(event_type, broken), f"brak payload.{field}"


@pytest.mark.parametrize("event_type", TYPES)
def test_unknown_fields_and_wrong_versions_rejected(event_type: str) -> None:
    example = valid_example(event_type)
    for broken in (
        {**example, "extra": 1},
        {**example, "payload": {**example["payload"], "extra": 1}},
        {**example, "schema_version": 2},
        {**example, "type": "other.event"},
        {**example, "event_id": "nie-uuid"},
        {**example, "occurred_at": "wczoraj"},
        {**example, "producer": "Worker"},
    ):
        assert errors(event_type, broken), broken


def test_format_checks_are_enforced() -> None:
    # Bez bibliotek formatów jsonschema po cichu ignoruje `format`; ten test to wykrywa.
    checker = FormatChecker()
    assert not checker.conforms("2026-11-23T10:00:00", "date-time")
    assert not checker.conforms("nie-uuid", "uuid")
    assert checker.conforms("2026-11-23T10:00:00Z", "date-time")
