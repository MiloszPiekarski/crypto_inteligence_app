"""Router dowodów i ocen: kontrakt z E2, implementacje w E7 (agenci) i E9 (fuzja).

Do tego czasu każdy endpoint zwraca 501 w formacie RFC 9457.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, HTTPException, Query

from goatcash.http_api.errors import responses
from goatcash.http_api.market import AssetId, Cursor
from goatcash.http_api.schemas import Agent, Assessment, Evidence, Horizon, Page

router = APIRouter(tags=["analysis"])
Limit = Annotated[int, Query(ge=1, le=200, description="liczba elementów na stronie")]


def not_implemented(stage: str) -> NoReturn:
    raise HTTPException(status_code=501, detail=f"Endpoint powstaje w {stage}.")


@router.get(
    "/assets/{asset_id}/evidence",
    summary="Dowody agentów dla aktywa",
    operation_id="listEvidence",
    responses=responses(422, 501),
)
def list_evidence(
    asset_id: AssetId,
    horizon: Annotated[Horizon | None, Query(description="filtr horyzontu")] = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> Page[Evidence]:
    """Dowody agentów dla aktywa w formacie kontraktu Evidence v1 (E7)."""
    not_implemented("E7")


@router.get(
    "/assets/{asset_id}/assessment",
    summary="Bieżąca ocena aktywa",
    operation_id="getAssessment",
    responses=responses(422, 501),
)
def get_assessment(
    asset_id: AssetId, horizon: Annotated[Horizon, Query(description="horyzont oceny")]
) -> Assessment:
    """Ocena po fuzji dowodów dla horyzontu (E9)."""
    not_implemented("E9")


@router.get(
    "/agents",
    summary="Rejestr agentów",
    operation_id="listAgents",
    responses=responses(501),
)
def list_agents() -> list[Agent]:
    """Agenci analityczni z wersjami i horyzontami (E7)."""
    not_implemented("E7")
