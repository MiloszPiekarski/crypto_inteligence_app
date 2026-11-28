"""API v1: specyfikacja OpenAPI 3.1, `/v1`, endpointy E7 i E9 jako 501 (RFC 9457), Evidence.

Endpointy rynkowe E6 sprawdzają testy w `tests/api/`.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import ValidationError

from goatcash.http_api.app import create_app
from goatcash.http_api.schemas import Evidence

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "packages/contracts/evidence/examples"
client = TestClient(create_app())


def get(url: str) -> Response:
    return client.get(url)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]


SPEC: dict[str, Any] = get("/openapi.json").json()
ASSET = "0193a4f2-7c1e-7a3b-9d2e-000000000099"


def test_spec_is_openapi_31_and_versioned() -> None:
    assert SPEC["openapi"].startswith("3.1")
    assert SPEC["paths"]
    assert all(path.startswith("/v1/") for path in SPEC["paths"])


def test_health() -> None:
    response = get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    "url",
    [
        f"/v1/assets/{ASSET}/evidence",
        f"/v1/assets/{ASSET}/assessment?horizon=1d",
        "/v1/agents",
    ],
)
def test_later_stage_endpoints_return_problem_501(url: str) -> None:
    response = get(url)
    assert response.status_code == 501
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["status"] == 501


def test_every_declared_get_is_covered_by_tests() -> None:
    declared = {path for path, ops in SPEC["paths"].items() if "get" in ops}
    assert declared == {
        "/v1/health",
        "/v1/assets",
        "/v1/assets/{asset_id}",
        "/v1/assets/{asset_id}/candles",
        "/v1/market/overview",
        "/v1/assets/{asset_id}/evidence",
        "/v1/assets/{asset_id}/assessment",
        "/v1/agents",
    }


@pytest.mark.parametrize("path", sorted((EVIDENCE / "valid").glob("*.json")), ids=str)
def test_evidence_model_accepts_contract_examples(path: Path) -> None:
    Evidence.model_validate_json(path.read_text("utf-8"))


@pytest.mark.parametrize("path", sorted((EVIDENCE / "invalid").glob("*.json")), ids=str)
def test_evidence_model_rejects_contract_counterexamples(path: Path) -> None:
    document = json.loads(path.read_text("utf-8"))
    document.pop("_why")
    with pytest.raises(ValidationError):
        Evidence.model_validate(document)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"data_cutoff": "2026-11-23T11:00:00Z"}, "zaglądanie w przyszłość"),
        (
            {"quantiles": {"q05": 0.1, "q25": 0.0, "q50": 0.0, "q75": 0.0, "q95": 0.0}},
            "kwantyle malejące",
        ),
    ],
)
def test_evidence_rules_beyond_json_schema(change: dict[str, Any], reason: str) -> None:
    document = json.loads((EVIDENCE / "valid/01-pelny.json").read_text("utf-8"))
    with pytest.raises(ValidationError, match=r"zaglądanie|kwantyle"):
        Evidence.model_validate({**document, **change})
    assert reason


def test_error_responses_documented_as_problem_json() -> None:
    for ops in SPEC["paths"].values():
        for op in ops.values():
            for status, response in op["responses"].items():
                if status[0] in "45":
                    assert list(response["content"]) == ["application/problem+json"], status
