"""Nagłówki bezpieczeństwa i CORS API v1 (E6, bramka G6p, `api-security`).

Nagłówki na każdej odpowiedzi: 200, błędy RFC 9457 (400, 404, 405, 422, 501, 503), 500
z nieobsłużonego wyjątku, odpowiedzi CORS (także odrzucone zapytanie wstępne). CORS
wyłącznie dla `https://app.goatcash.app`, tylko GET, bez ciasteczek; obce origin,
podobne nazwy domen i `null` nie dostają `Access-Control-Allow-Origin`.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from api_data import Failing, reader
from fastapi.testclient import TestClient
from httpx import Response

from goatcash.http_api.app import create_app
from goatcash.http_api.security import APP_ORIGIN, SECURITY_HEADERS
from goatcash.marketdata.api import asset_public_id

client = TestClient(create_app(reader()), raise_server_exceptions=False)
BTC = asset_public_id("BTC")
EXPECTED = {
    "strict-transport-security": "max-age=31536000; includeSubDomains",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "cross-origin-resource-policy": "same-site",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
}


def request(method: str, url: str, **kwargs: Any) -> Any:
    response = cast(Response, client.request(method, url, **kwargs))  # pyright: ignore[reportUnknownMemberType]
    return response


def assert_security_headers(response: Any) -> None:
    for name, value in EXPECTED.items():
        assert response.headers.get(name) == value, (name, response.status_code)
        assert len(response.headers.get_list(name)) == 1, name  # bez dublowania


def test_expected_headers_match_module() -> None:
    assert {k.lower(): v for k, v in SECURITY_HEADERS.items()} == EXPECTED


@pytest.mark.parametrize(
    ("method", "url", "status"),
    [
        ("GET", "/v1/health", 200),
        ("GET", "/v1/assets", 200),
        ("GET", f"/v1/assets/{BTC}/candles?timeframe=1d", 200),
        ("GET", "/v1/market/overview", 200),
        ("HEAD", "/v1/health", 405),
        ("GET", "/openapi.json", 200),
        ("GET", "/v1/assets?cursor=zzz", 400),
        ("GET", "/v1/nie-ma", 404),
        ("GET", "/docs", 404),
        ("GET", "/redoc", 404),
        ("POST", "/v1/assets", 405),
        ("DELETE", f"/v1/assets/{BTC}", 405),
        ("GET", f"/v1/assets/{BTC}/candles?timeframe=5m", 422),
        ("GET", "/v1/agents", 501),
    ],
)
def test_security_headers_on_every_response(method: str, url: str, status: int) -> None:
    response = request(method, url)
    assert response.status_code == status
    assert_security_headers(response)


def test_security_headers_on_503_and_unhandled_500() -> None:
    bare = TestClient(create_app(Failing(RuntimeError("x"))), raise_server_exceptions=False)
    response = cast(Response, bare.get("/v1/assets"))  # pyright: ignore[reportUnknownMemberType]
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert_security_headers(response)
    from psycopg import OperationalError  # noqa: PLC0415

    down = TestClient(create_app(Failing(OperationalError("x"))))
    response = cast(Response, down.get("/v1/market/overview"))  # pyright: ignore[reportUnknownMemberType]
    assert response.status_code == 503
    assert_security_headers(response)


def test_cors_allows_only_app_origin_for_reads() -> None:
    response = request("GET", "/v1/assets", headers={"Origin": APP_ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == APP_ORIGIN
    assert "access-control-allow-credentials" not in response.headers
    assert_security_headers(response)


def test_cors_preflight_allowed() -> None:
    response = request(
        "OPTIONS",
        "/v1/market/overview",
        headers={"Origin": APP_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == APP_ORIGIN
    methods = {m.strip() for m in response.headers["access-control-allow-methods"].split(",")}
    assert methods == {"GET"}
    assert response.headers["access-control-max-age"] == "600"
    assert_security_headers(response)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://app.goatcash.app",  # bez TLS
        "https://app.goatcash.app.evil.example",
        "https://evilapp.goatcash.app",
        "https://goatcash.app",
        "https://app.goatcash.app:8443",
        "null",
    ],
)
def test_cors_rejects_other_origins(origin: str) -> None:
    simple = request("GET", "/v1/assets", headers={"Origin": origin})
    assert simple.status_code == 200  # odpowiedź jest, ale przeglądarka jej nie odda stronie
    assert "access-control-allow-origin" not in simple.headers
    assert_security_headers(simple)
    preflight = request(
        "OPTIONS",
        "/v1/assets",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers
    assert_security_headers(preflight)


@pytest.mark.parametrize("method", ["HEAD", "POST", "PUT", "DELETE", "PATCH"])
def test_cors_preflight_rejects_writes(method: str) -> None:
    response = request(
        "OPTIONS",
        "/v1/assets",
        headers={"Origin": APP_ORIGIN, "Access-Control-Request-Method": method},
    )
    assert response.status_code == 400
    assert_security_headers(response)


def test_cors_preflight_rejects_custom_headers() -> None:
    response = request(
        "OPTIONS",
        "/v1/assets",
        headers={
            "Origin": APP_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 400
