"""Router modułu marketdata: endpointy rynkowe tylko do odczytu (roadmapa E6, ścieżka pracy).

`GET /v1/assets`, `/v1/assets/{asset_id}`, `/v1/assets/{asset_id}/candles` (decyzja D1:
ścieżka z kontraktu E2) i `/v1/market/overview`. Dane z `MarketReader` (moduł
marketdata); router tylko tłumaczy je na modele kontraktu.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request

from goatcash.http_api import cursor as cursors
from goatcash.http_api.errors import responses
from goatcash.http_api.schemas import (
    Asset,
    Candle,
    DqStatus,
    MarketOverview,
    OverviewItem,
    Page,
    Timeframe,
)
from goatcash.marketdata.api import AssetInfo, Bar, MarketReader, asset_public_id
from goatcash.marketdata.api import OverviewRow as Row

EXAMPLE_ASSET = str(asset_public_id("BTC"))
AssetId = Annotated[
    UUID, Path(description="publiczny identyfikator aktywa", examples=[EXAMPLE_ASSET])
]
Cursor = Annotated[
    str | None,
    Query(
        description=(
            "kursor następnej strony: nieprzezroczysty, tylko wartość `next_cursor` z poprzedniej "
            "strony tego samego zasobu; inny kursor daje 400"
        ),
        max_length=200,
    ),
]


def reader(request: Request) -> MarketReader:
    found: MarketReader | None = request.app.state.reader
    if found is None:
        raise HTTPException(status_code=503, detail="Dane rynkowe nie są skonfigurowane.")
    return found


Reader = Annotated[MarketReader, Depends(reader)]
router = APIRouter(tags=["market"])


EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def from_ms(ts_ms: int) -> datetime:
    return EPOCH + timedelta(milliseconds=ts_ms)


def dec(value: Decimal) -> str:
    """Liczba dziesiętna jako tekst bez notacji wykładniczej (wzór `Decimal` w kontrakcie)."""
    return format(value, "f")


def asset_model(a: AssetInfo) -> Asset:
    return Asset(id=a.public_id, symbol=a.symbol, name=a.name)


def candle_model(b: Bar) -> Candle:
    return Candle(
        ts=from_ms(b.ts_ms),
        open=dec(b.open),
        high=dec(b.high),
        low=dec(b.low),
        close=dec(b.close),
        volume=dec(b.volume),
    )


@router.get(
    "/assets",
    summary="Lista aktywów",
    operation_id="listAssets",
    responses=responses(400, 422, 503),
)
def list_assets(
    store: Reader,
    cursor: Cursor = None,
    limit: Annotated[int, Query(ge=1, le=200, description="liczba elementów na stronie")] = 50,
) -> Page[Asset]:
    """Aktywa obsługiwane przez platformę (rosnąco po symbolu), paginacja kursorowa."""
    after = None if cursor is None else cursors.decode_symbol(cursor)
    rows = store.list_assets(after, limit + 1)
    nxt = cursors.encode("assets", "", rows[limit - 1].symbol) if len(rows) > limit else None
    return Page[Asset](items=[asset_model(a) for a in rows[:limit]], next_cursor=nxt)


@router.get(
    "/assets/{asset_id}",
    summary="Aktywo",
    operation_id="getAsset",
    responses=responses(404, 422, 503),
)
def get_asset(asset_id: AssetId, store: Reader) -> Asset:
    """Szczegóły jednego aktywa."""
    found = store.get_asset(asset_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Nie ma aktywa o tym identyfikatorze.")
    return asset_model(found)


@router.get(
    "/assets/{asset_id}/candles",
    summary="Świece referencyjne aktywa",
    operation_id="listCandles",
    responses=responses(400, 404, 422, 503),
)
def list_candles(
    asset_id: AssetId,
    timeframe: Annotated[Timeframe, Query(description="interwał świec")],
    store: Reader,
    cursor: Cursor = None,
    limit: Annotated[int, Query(ge=1, le=200, description="liczba elementów na stronie")] = 200,
) -> Page[Candle]:
    """Świece ceny referencyjnej (mediana giełd) od najnowszej.

    4h i 1d to pełne okresy UTC ze świec 1h; okres z brakującą świecą 1h nie jest zwracany.
    """
    if store.get_asset(asset_id) is None:
        raise HTTPException(status_code=404, detail="Nie ma aktywa o tym identyfikatorze.")
    scope = f"{asset_id}:{timeframe}"
    before = None if cursor is None else cursors.decode_ts(scope, cursor)
    bars = store.candles(asset_id, timeframe, before, limit + 1)
    last = bars[limit - 1] if len(bars) > limit else None
    nxt = None if last is None else cursors.encode("candles", scope, str(last.ts_ms))
    return Page[Candle](items=[candle_model(b) for b in bars[:limit]], next_cursor=nxt)


def overview_item(row: Row) -> OverviewItem:
    change = None
    if row.close_24h_ago is not None and row.close_24h_ago > 0:
        change = float(row.close / row.close_24h_ago - 1)
    return OverviewItem(
        asset=asset_model(row.asset),
        ts=from_ms(row.ts_ms),
        close=dec(row.close),
        change_24h=change,
        volume_24h=None if row.volume_24h is None else dec(row.volume_24h),
        dq_status=cast(DqStatus | None, row.dq_status),
    )


@router.get(
    "/market/overview",
    summary="Przegląd rynku",
    operation_id="getMarketOverview",
    responses=responses(503),
)
def market_overview(store: Reader) -> MarketOverview:
    """Ostatnia cena, zmiana i wolumen 24 h oraz status jakości danych każdego aktywa."""
    return MarketOverview(items=[overview_item(r) for r in store.overview()])
