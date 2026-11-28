"""Schemathesis na API v1 tylko do odczytu (E6, bramka G6p, `api-schema`, wymaganie F-09).

Zapytania generowane ze specyfikacji OpenAPI aplikacji (także niepoprawne: zły UUID,
interwał spoza listy, limit poza zakresem, uszkodzony kursor) na danych w pamięci
z `api_data` (przykład `asset_id` w specyfikacji to BTC, więc faza przykładów trafia też
w istniejące aktywo). Wszystkie sprawdzenia Schemathesis: m.in. brak błędów 5xx,
odpowiedź zgodna ze schematem, typ treści i nagłówki zgodne ze specyfikacją, niepoprawne
dane odrzucone (4xx), poprawne przyjęte.

Wynik bramki: 0 odpowiedzi niezgodnych ze schematem i 0 błędów 500. Endpointy E7 i E9
(dowody, ocena, agenci) są wyłączone, bo celowo zwracają 501 do swoich etapów
(test `test_http_api.py`); każdy z endpointów E6 jest w teście (`test_covers_all_e6_operations`).
"""

from __future__ import annotations

from typing import Any

from api_data import LATER_STAGES, conformance_schema, reader, validate
from hypothesis import HealthCheck, settings

from goatcash.http_api.app import create_app

APP = create_app(reader())
E6_OPERATIONS = {"getHealth", "listAssets", "getAsset", "listCandles", "getMarketOverview"}
schema = conformance_schema(APP)


@schema.parametrize()
@settings(
    max_examples=1000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
def test_api_conforms_to_openapi(case: Any) -> None:
    validate(case)


def test_covers_all_e6_operations() -> None:
    spec: dict[str, Any] = APP.openapi()
    declared = {op["operationId"] for ops in spec["paths"].values() for op in ops.values()}
    assert declared - LATER_STAGES == E6_OPERATIONS
    tested = {op.ok().definition.raw["operationId"] for op in schema.get_all_operations()}
    assert tested == E6_OPERATIONS
