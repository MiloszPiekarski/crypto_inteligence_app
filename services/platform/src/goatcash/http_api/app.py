"""Aplikacja FastAPI: szkic kontraktu API v1 (roadmapa E2, „Kontrakty”).

Endpointy z roadmapy E6, E7 i E9 są zadeklarowane z modelami odpowiedzi, żeby powstała
specyfikacja OpenAPI 3.1 i klient TypeScript. Implementacje dochodzą w tych etapach;
do tego czasu każdy endpoint poza `/v1/health` zwraca 501 w formacie RFC 9457.
"""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse

from goatcash.common.api import package_version
from goatcash.http_api.schemas import (
    Agent,
    Assessment,
    Asset,
    Candle,
    Evidence,
    Health,
    Horizon,
    Page,
    Problem,
    Timeframe,
)

PROBLEM = "application/problem+json"
ERRORS: dict[int | str, dict[str, object]] = {
    501: {"model": Problem, "description": "Jeszcze nie zaimplementowane (szkic E2)"},
}
AssetId = Annotated[UUID, Path(description="publiczny identyfikator aktywa")]
Cursor = Annotated[str | None, Query(description="kursor następnej strony")]
Limit = Annotated[int, Query(ge=1, le=200, description="liczba elementów na stronie")]


def not_implemented(stage: str) -> NoReturn:
    raise HTTPException(status_code=501, detail=f"Endpoint powstaje w {stage}.")


v1 = APIRouter(prefix="/v1")


@v1.get("/health", tags=["system"], summary="Stan procesu api", operation_id="getHealth")
def health() -> Health:
    """Stan procesu i wersja pakietu; nie wymaga uwierzytelnienia."""
    return Health(status="ok", version=package_version())


@v1.get(
    "/assets", tags=["market"], summary="Lista aktywów", operation_id="listAssets", responses=ERRORS
)
def list_assets(cursor: Cursor = None, limit: Limit = 50) -> Page[Asset]:
    """Aktywa obsługiwane przez platformę, z paginacją kursorową (E6)."""
    not_implemented("E6")


@v1.get(
    "/assets/{asset_id}",
    tags=["market"],
    summary="Aktywo",
    operation_id="getAsset",
    responses=ERRORS,
)
def get_asset(asset_id: AssetId) -> Asset:
    """Szczegóły jednego aktywa (E6)."""
    not_implemented("E6")


@v1.get(
    "/assets/{asset_id}/candles",
    tags=["market"],
    summary="Świece referencyjne aktywa",
    operation_id="listCandles",
    responses=ERRORS,
)
def list_candles(
    asset_id: AssetId,
    timeframe: Annotated[Timeframe, Query(description="interwał świec")],
    cursor: Cursor = None,
    limit: Limit = 200,
) -> Page[Candle]:
    """Świece ceny referencyjnej (mediana giełd) dla interwału, od najnowszej (E6)."""
    not_implemented("E6")


@v1.get(
    "/assets/{asset_id}/evidence",
    tags=["analysis"],
    summary="Dowody agentów dla aktywa",
    operation_id="listEvidence",
    responses=ERRORS,
)
def list_evidence(
    asset_id: AssetId,
    horizon: Annotated[Horizon | None, Query(description="filtr horyzontu")] = None,
    cursor: Cursor = None,
    limit: Limit = 50,
) -> Page[Evidence]:
    """Dowody agentów dla aktywa w formacie kontraktu Evidence v1 (E7)."""
    not_implemented("E7")


@v1.get(
    "/assets/{asset_id}/assessment",
    tags=["analysis"],
    summary="Bieżąca ocena aktywa",
    operation_id="getAssessment",
    responses=ERRORS,
)
def get_assessment(
    asset_id: AssetId, horizon: Annotated[Horizon, Query(description="horyzont oceny")]
) -> Assessment:
    """Ocena po fuzji dowodów dla horyzontu (E9)."""
    not_implemented("E9")


@v1.get(
    "/agents",
    tags=["analysis"],
    summary="Rejestr agentów",
    operation_id="listAgents",
    responses=ERRORS,
)
def list_agents() -> list[Agent]:
    """Agenci analityczni z wersjami i horyzontami (E7)."""
    not_implemented("E7")


def problem_response(request: Request, exc: Exception) -> JSONResponse:
    status = exc.status_code if isinstance(exc, HTTPException) else 500
    title = str(exc.detail) if isinstance(exc, HTTPException) else "Błąd serwera"
    body = Problem(type="about:blank", title=title, status=status)
    return JSONResponse(body.model_dump(exclude_none=True), status, media_type=PROBLEM)


def create_app() -> FastAPI:
    app = FastAPI(
        title="GoatCash API",
        version="0.1.0",
        description=(
            "Publiczne API platformy GoatCash (szkic kontraktu z etapu E2). "
            "Endpointy oznaczone 501 powstają w etapach E6, E7 i E9."
        ),
        license_info={"name": "AGPL-3.0-only", "identifier": "AGPL-3.0-only"},
        contact={"name": "GoatCash", "url": "https://goatcash.app"},
        servers=[{"url": "https://api.goatcash.app", "description": "produkcja (od E16)"}],
        openapi_tags=[
            {"name": "system", "description": "Stan procesu"},
            {"name": "market", "description": "Dane rynkowe (E6)"},
            {"name": "analysis", "description": "Dowody agentów i oceny (E7, E9)"},
        ],
    )
    app.include_router(v1)
    app.add_exception_handler(HTTPException, problem_response)
    return app
