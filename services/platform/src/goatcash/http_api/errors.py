"""Błędy w formacie RFC 9457 (Problem Details, `application/problem+json`) dla każdej odpowiedzi
4xx i 5xx: wyjątki HTTP (także 404 i 405 z routingu), błędy walidacji zapytania (422),
niedostępność bazy (503) i nieobsłużone wyjątki (500, bez szczegółów na zewnątrz).
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from goatcash.http_api.schemas import Problem

PROBLEM = "application/problem+json"
log = logging.getLogger("goatcash.api")

TITLES = {
    400: "Niepoprawne zapytanie",
    404: "Nie znaleziono",
    405: "Metoda niedozwolona",
    422: "Niepoprawne parametry zapytania",
    500: "Błąd serwera",
    501: "Jeszcze nie zaimplementowane",
    503: "Usługa chwilowo niedostępna",
}


def problem(
    status: int, detail: str | None = None, headers: dict[str, str] | None = None
) -> JSONResponse:
    title = TITLES.get(status, "Błąd")
    body = Problem(type="about:blank", title=title, status=status, detail=detail)
    return JSONResponse(
        body.model_dump(exclude_none=True), status, headers=headers, media_type=PROBLEM
    )


def responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Deklaracja odpowiedzi błędów w OpenAPI (typ treści poprawia `problem_openapi`)."""
    return {s: {"model": Problem, "description": TITLES[s]} for s in statuses}


async def _http(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover - rejestracja niżej
        raise exc
    detail: str | None = exc.detail
    if detail == HTTPStatus(exc.status_code).phrase:  # domyślny tekst Starlette („Not Found”)
        detail = None
    return problem(exc.status_code, detail, dict(exc.headers or {}))


async def _validation(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover - rejestracja niżej
        raise exc
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(x) for x in err.get("loc", ()) if x not in ("query", "path"))
        parts.append(f"{loc}: {err.get('msg', 'niepoprawna wartość')}")
    return problem(422, "; ".join(parts) or None)


async def _database(_: Request, exc: Exception) -> JSONResponse:
    log.warning("baza niedostępna: %s", type(exc).__name__)
    return problem(503, "Dane rynkowe są chwilowo niedostępne.", {"Retry-After": "30"})


def install(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(psycopg.OperationalError, _database)


def problem_openapi(spec: dict[str, Any]) -> dict[str, Any]:
    """Odpowiedzi 4xx i 5xx w specyfikacji mają typ `application/problem+json`."""
    for ops in spec.get("paths", {}).values():
        for op in ops.values():
            for status, response in op.get("responses", {}).items():
                content = response.get("content")
                if status[:1] in "45" and content and "application/json" in content:
                    response["content"] = {PROBLEM: content.pop("application/json")}
    return spec
