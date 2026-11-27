"""Schematy zdarzeń (ADR-0003): poprawne przykłady przechodzą, błędne są odrzucane.

Bramka G2, sprawdzenie `event-schemas` (`make event-schemas-test`). Oprócz przykładów
z plików test sam psuje każdy poprawny przykład (brak pola, pole nadmiarowe, zły typ,
zła wersja), żeby schemat nie mógł po cichu przepuszczać niekompletnych zdarzeń.

Wersje (ADR-0003, punkt 2): zmiana niezgodna wstecz = nowy plik `<typ>.v<N>.schema.json`,
przykłady wersji N > 1 w `examples/<typ>/v<N>/`; poprzednia wersja zostaje (konsument
obsługuje bieżącą i poprzednią). features.ready v2: decyzja właściciela 27.11.2026 (E5).
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
# (typ, wersja) każdego schematu; wersje > 1 dopisujemy jawnie.
SCHEMAS = (*((t, 1) for t in TYPES), ("features.ready", 2))
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


def schema_path(event_type: str, version: int = 1) -> Path:
    return EVENTS / f"{event_type}.v{version}.schema.json"


def examples(event_type: str, version: int = 1) -> Path:
    return EXAMPLES / event_type if version == 1 else EXAMPLES / event_type / f"v{version}"


def validator(event_type: str, version: int = 1) -> Draft202012Validator:
    schema = load(schema_path(event_type, version))
    return Draft202012Validator(schema, registry=registry(), format_checker=FormatChecker())


def valid_example(event_type: str, version: int = 1) -> dict[str, Any]:
    return load(examples(event_type, version) / "valid" / "01.json")


def errors(event_type: str, document: dict[str, Any], version: int = 1) -> list[str]:
    found = validator(event_type, version).iter_errors(document)  # pyright: ignore[reportUnknownMemberType]
    return [str(e.message) for e in found]


def test_every_event_type_has_schema_and_examples() -> None:
    found = {
        (p.name.split(".v")[0], int(p.name.split(".v")[1].split(".")[0]))
        for p in EVENTS.glob("*.v*.schema.json")
    }
    assert found == set(SCHEMAS)
    for event_type, version in SCHEMAS:
        assert list((examples(event_type, version) / "valid").glob("*.json")), event_type
        assert list((examples(event_type, version) / "invalid").glob("*.json")), event_type


@pytest.mark.parametrize("path", sorted(EVENTS.glob("*.schema.json")), ids=lambda p: p.name)
def test_schemas_are_valid_draft_2020_12(path: Path) -> None:
    Draft202012Validator.check_schema(load(path))


def _ids(item: tuple[str, int]) -> str:
    return f"{item[0]}.v{item[1]}"


@pytest.mark.parametrize("schema", SCHEMAS, ids=_ids)
def test_valid_examples_pass(schema: tuple[str, int]) -> None:
    event_type, version = schema
    for path in sorted((examples(event_type, version) / "valid").glob("*.json")):
        assert errors(event_type, load(path), version) == [], path


def _invalid() -> list[tuple[str, int, Path]]:
    return [
        (t, v, p) for t, v in SCHEMAS for p in sorted((examples(t, v) / "invalid").glob("*.json"))
    ]


@pytest.mark.parametrize(
    ("event_type", "version", "path"),
    _invalid(),
    ids=[f"{t}.v{v}/{p.stem}" for t, v, p in _invalid()],
)
def test_invalid_examples_are_rejected(event_type: str, version: int, path: Path) -> None:
    document = load(path)
    why = document.pop("_why")  # opis przypadku, nie część zdarzenia
    assert errors(event_type, document, version), f"{path}: przepuszczono ({why})"


@pytest.mark.parametrize("schema", SCHEMAS, ids=_ids)
def test_missing_required_fields_rejected(schema: tuple[str, int]) -> None:
    event_type, version = schema
    example = valid_example(event_type, version)
    for field in ENVELOPE_FIELDS:
        broken = copy.deepcopy(example)
        del broken[field]
        assert errors(event_type, broken, version), f"brak {field}"
    for field in load(schema_path(event_type, version))["properties"]["payload"]["required"]:
        broken = copy.deepcopy(example)
        del broken["payload"][field]
        assert errors(event_type, broken, version), f"brak payload.{field}"


@pytest.mark.parametrize("schema", SCHEMAS, ids=_ids)
def test_unknown_fields_and_wrong_versions_rejected(schema: tuple[str, int]) -> None:
    event_type, version = schema
    example = valid_example(event_type, version)
    for broken in (
        {**example, "extra": 1},
        {**example, "payload": {**example["payload"], "extra": 1}},
        {**example, "schema_version": version + 1},
        {**example, "type": "other.event"},
        {**example, "event_id": "nie-uuid"},
        {**example, "occurred_at": "wczoraj"},
        {**example, "producer": "Worker"},
    ):
        assert errors(event_type, broken, version), broken


def test_format_checks_are_enforced() -> None:
    # Bez bibliotek formatów jsonschema po cichu ignoruje `format`; ten test to wykrywa.
    checker = FormatChecker()
    assert not checker.conforms("2026-11-23T10:00:00", "date-time")
    assert not checker.conforms("nie-uuid", "uuid")
    assert checker.conforms("2026-11-23T10:00:00Z", "date-time")
