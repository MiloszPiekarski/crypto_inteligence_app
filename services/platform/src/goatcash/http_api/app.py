"""Aplikacja FastAPI: API v1 tylko do odczytu (roadmapa E6, ścieżka pracy, ADR-0008).

Routery per moduł: system (`/v1/health`), rynek (marketdata, E6) i analiza (kontrakt E2,
implementacje w E7 i E9; do tego czasu 501). Każdy błąd w formacie RFC 9457, nagłówki
bezpieczeństwa na każdej odpowiedzi, CORS tylko dla `https://app.goatcash.app`.

Dane rynkowe: `create_app(reader=...)` w testach; w procesie api `MarketReader`
w Postgresie z `GOATCASH_DATABASE_URL` (konto `goatcash_api`, tylko odczyt). Bez adresu
bazy endpointy rynkowe zwracają 503, a `/v1/health` działa.

Cache odpowiedzi (`cache.py`): Valkey z `GOATCASH_VALKEY_URL` (albo `valkey=` w testach)
i słuchacz `candle.closed` uruchamiany razem z aplikacją; bez Valkey odpowiedzi idą prosto
z bazy.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

import redis
from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi

from goatcash.common.api import package_version
from goatcash.http_api import analysis, cache, errors, market, security
from goatcash.http_api.schemas import Health
from goatcash.http_api.telemetry import setup_tracing
from goatcash.marketdata.api import MarketReader, PostgresReader, load_universe

system = APIRouter(tags=["system"])


@system.get("/health", summary="Stan procesu api", operation_id="getHealth")
def health() -> Health:
    """Stan procesu i wersja pakietu; nie wymaga uwierzytelnienia ani bazy."""
    return Health(status="ok", version=package_version())


def reader_from_env() -> MarketReader | None:
    url = os.environ.get("GOATCASH_DATABASE_URL")
    if not url:
        return None
    return PostgresReader.from_url(url, load_universe().quote.symbol)


def valkey_from_env(*, listener: bool = False) -> cache.Valkey | None:
    """Klient Valkey z `GOATCASH_VALKEY_URL`. Cache: krótkie limity (wolny albo niedostępny
    Valkey nie spowalnia odpowiedzi z bazy); słuchacz: limit dłuższy niż XREAD BLOCK."""
    url = os.environ.get("GOATCASH_VALKEY_URL")
    if not url:
        return None
    timeout = cache.BLOCK_MS / 1000 + 5 if listener else 0.25
    client = redis.Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        url, socket_timeout=timeout, socket_connect_timeout=2 if listener else 0.25
    )
    return cast(cache.Valkey, client)


def create_app(
    reader: MarketReader | None = None,
    *,
    valkey: cache.Valkey | None = None,
    invalidator: cache.Invalidator | None = None,
) -> FastAPI:
    """`valkey` i `invalidator` podają testy; bez nich konfiguracja z `GOATCASH_VALKEY_URL`
    (słuchacz w osobnym wątku startuje i kończy się razem z aplikacją)."""
    started: list[cache.Invalidator] = []
    if valkey is None and invalidator is None:
        valkey = valkey_from_env()
        listener = valkey_from_env(listener=True)
        if valkey is not None and listener is not None:
            invalidator = cache.Invalidator(listener)
            started.append(invalidator)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        for inv in started:
            inv.start()
        yield
        for inv in started:
            inv.stop()
        close = getattr(app.state.reader, "close", None)
        if callable(close):
            close()

    app = FastAPI(
        title="GoatCash API",
        version="0.2.0",
        description=(
            "Publiczne API platformy GoatCash, tylko do odczytu (ścieżka pracy, E6). "
            "Endpointy oznaczone 501 powstają w etapach E7 i E9."
        ),
        license_info={"name": "AGPL-3.0-only", "identifier": "AGPL-3.0-only"},
        contact={"name": "GoatCash", "url": "https://goatcash.app"},
        servers=[{"url": "https://api.goatcash.app", "description": "staging (produkcja od E16)"}],
        openapi_tags=[
            {"name": "system", "description": "Stan procesu"},
            {"name": "market", "description": "Dane rynkowe (E6)"},
            {"name": "analysis", "description": "Dowody agentów i oceny (E7, E9)"},
        ],
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.reader = reader if reader is not None else reader_from_env()
    v1 = APIRouter(prefix="/v1")
    v1.include_router(system)
    v1.include_router(market.router)
    v1.include_router(analysis.router)
    app.include_router(v1)
    errors.install(app)
    # Cache wewnątrz CORS i nagłówków bezpieczeństwa: odpowiedź z cache dostaje je tak samo.
    app.add_middleware(cache.ResponseCache, client=valkey, invalidator=invalidator)
    security.install(app)

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            spec = get_openapi(
                title=app.title,
                version=app.version,
                openapi_version=app.openapi_version,
                description=app.description,
                routes=app.routes,
                tags=app.openapi_tags,
                servers=app.servers,
                contact=app.contact,
                license_info=app.license_info,
            )
            app.openapi_schema = errors.problem_openapi(spec)
        return app.openapi_schema

    app.openapi = openapi
    setup_tracing(app)
    return app
