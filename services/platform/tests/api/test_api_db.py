"""API v1 na prawdziwym Postgresie z Timescale (E6, bramka G6p, `api-db`, marker `db`).

- każda odpowiedź API z czytnikiem w Postgresie = odpowiedź z czytnikiem w pamięci na tych
  samych danych (aktywa, świece 1h/4h/1d przy kilku rozmiarach strony, przegląd rynku),
  więc testy wartości referencyjnych z `test_api_market.py` dotyczą też bazy;
- `assets.public_id` z migracji 0005 = `asset_public_id` w Pythonie;
- konto logowania API (jak `goatcash_api` z `ensure-api-role.sh`: LOGIN, bez członkostw,
  SELECT tylko na 4 tabelach rynkowych, sesja tylko do odczytu) nie zapisuje, także po
  `RESET ROLE`, nie przełącza się na superużytkownika i nie czyta danych użytkowników;
- Schemathesis na aplikacji z czytnikiem w Postgresie: 0 odpowiedzi niezgodnych, 0 błędów 5xx.
Uruchomienie: `make api-db-test` (Docker). Lokalnie bez Dockera: `GOATCASH_TEST_DB_URL`
(baza po `alembic upgrade head`, konto z prawem tworzenia ról).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
import schemathesis
from alembic import command
from alembic.config import Config
from api_data import (
    DQ,
    LATER_STAGES,
    NAMES,
    QUOTE,
    conformance_schema,
    reader,
    refs,
    validate,
)
from fastapi.testclient import TestClient
from httpx import Response
from hypothesis import HealthCheck, settings
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from testcontainers.community.postgres import PostgresContainer

from goatcash.http_api.app import create_app
from goatcash.marketdata.api import PostgresReader, asset_public_id

pytestmark = pytest.mark.db

PLATFORM = Path(__file__).resolve().parents[2]
# Ten sam obraz co test migracji (G2), Compose staging (G3) i testy bazy G4p i G5p.
PG_IMAGE = (
    "timescale/timescaledb-ha:pg17"
    "@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
)
API_ROLE = "goatcash_api_test"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
API_PASSWORD = "api-test-haslo"  # noqa: S105 - konto testowe w kontenerze


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    if url := os.environ.get("GOATCASH_TEST_DB_URL"):
        yield url
        return
    with PostgresContainer(PG_IMAGE, driver=None) as pg:
        url = pg.get_connection_url()
        cfg = Config(str(PLATFORM / "alembic.ini"))
        os.environ["GOATCASH_DATABASE_URL"] = url.replace("postgresql://", "postgresql+psycopg://")
        command.upgrade(cfg, "head")
        yield url


@pytest.fixture(scope="module")
def api_url(db_url: str) -> str:
    """Dane z `api_data` w bazie i konto logowania API; zwraca adres tego konta."""
    with psycopg.connect(db_url, autocommit=True) as admin, admin.transaction():
        admin.execute(
            "TRUNCATE candles_ref, dq_status, dq_events, candles, instruments, assets "
            "RESTART IDENTITY CASCADE"
        )
        for symbol, name in sorted(NAMES.items()):
            admin.execute("INSERT INTO assets (symbol, name) VALUES (%s, %s)", (symbol, name))
        ids = {str(s): int(i) for i, s in admin.execute("SELECT asset_id, symbol FROM assets")}
        for symbol in sorted(set(NAMES) - {QUOTE}):
            for exchange in ("okx", "bybit"):
                admin.execute(
                    "INSERT INTO instruments (exchange, symbol, kind, base_asset_id, "
                    "quote_asset_id) VALUES (%s, %s, 'spot', %s, %s)",
                    (exchange, f"{symbol}-{QUOTE}", ids[symbol], ids[QUOTE]),
                )
        with admin.cursor() as cur:
            cur.executemany(
                "INSERT INTO candles_ref (asset_id, quote_asset_id, timeframe, ts, open, high, "
                "low, close, volume, sources, source) VALUES (%s, %s, '1h', %s, %s, %s, %s, %s, "
                "%s, %s, %s)",
                [
                    (
                        ids[r.base],
                        ids[r.quote],
                        EPOCH + timedelta(milliseconds=r.ts_ms),
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        r.volume,
                        list(r.sources),
                        r.source,
                    )
                    for r in refs()
                ],
            )
        for symbol, statuses in DQ.items():
            for exchange, status in zip(("okx", "bybit"), statuses, strict=True):
                admin.execute(
                    "INSERT INTO dq_status (dataset, instrument_id, status) SELECT 'candles_1h', "
                    "instrument_id, %s FROM instruments WHERE exchange = %s AND symbol = %s",
                    (status, exchange, f"{symbol}-{QUOTE}"),
                )
        admin.execute(f"DROP ROLE IF EXISTS {API_ROLE}")
        # Jak goatcash_api w infra/compose/staging/ensure-api-role.sh (ten sam zestaw atrybutów).
        admin.execute(
            f"CREATE ROLE {API_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION "
            f"NOBYPASSRLS INHERIT PASSWORD '{API_PASSWORD}'"
        )
        admin.execute(f"GRANT SELECT ON assets, instruments, candles_ref, dq_status TO {API_ROLE}")
        admin.execute(f"ALTER ROLE {API_ROLE} SET default_transaction_read_only = on")
    params = conninfo_to_dict(db_url.replace("postgresql+psycopg://", "postgresql://"))
    params.update(user=API_ROLE, password=API_PASSWORD)
    return make_conninfo(**params)  # pyright: ignore[reportArgumentType]


@pytest.fixture(scope="module")
def pg_client(api_url: str) -> Iterator[TestClient]:
    app = create_app(PostgresReader.from_url(api_url, QUOTE))
    with TestClient(app) as client:
        yield client


MEMORY = TestClient(create_app(reader()))


def get(client: TestClient, url: str, **params: Any) -> Any:
    response = cast(Response, client.get(url, params=params))  # pyright: ignore[reportUnknownMemberType]
    return response.status_code, response.headers.get("content-type"), response.json()


def walk(client: TestClient, url: str, **params: Any) -> list[Any]:
    pages: list[Any] = []
    cursor = None
    for _ in range(1000):
        query = dict(params, **({"cursor": cursor} if cursor else {}))
        page = get(client, url, **query)
        pages.append(page)
        cursor = page[2].get("next_cursor") if page[0] == 200 else None
        if cursor is None:
            return pages
    pytest.fail("paginacja się nie kończy")


def test_postgres_reader_equals_memory_reader(pg_client: TestClient) -> None:
    urls: list[tuple[str, dict[str, Any]]] = [
        ("/v1/market/overview", {}),
        ("/v1/assets", {"limit": 2}),
        ("/v1/assets", {}),
        (f"/v1/assets/{asset_public_id('NIEMA')}", {}),
        (f"/v1/assets/{asset_public_id(QUOTE)}", {}),  # kwotowanie nie jest aktywem listy
    ]
    for symbol in sorted(NAMES):
        aid = asset_public_id(symbol)
        urls.append((f"/v1/assets/{aid}", {}))
        for timeframe in ("1h", "4h", "1d"):
            for limit in (7, 200):
                urls.append((f"/v1/assets/{aid}/candles", {"timeframe": timeframe, "limit": limit}))
    for url, params in urls:
        assert walk(pg_client, url, **params) == walk(MEMORY, url, **params), (url, params)


def test_public_id_column_matches_python(db_url: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        rows = conn.execute("SELECT symbol, public_id FROM assets").fetchall()
    assert rows
    assert all(public_id == asset_public_id(symbol) for symbol, public_id in rows)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO assets (symbol, name) VALUES ('ZZZ', 'z')",
        "UPDATE candles_ref SET close = 0",
        "DELETE FROM dq_status",
        "CREATE TABLE api_probe (x int)",
        'SELECT * FROM "user"',
        "SELECT * FROM session",
        "SELECT * FROM alert_rules",
        "SELECT * FROM strategies",
        "SELECT * FROM audit_log",
        "SELECT * FROM event_outbox",
        "SELECT * FROM feature_values",
        "SET ROLE postgres",
        "SET ROLE goatcash_app",
    ],
)
def test_api_account_cannot_write_or_escalate(api_url: str, sql: str) -> None:
    with psycopg.connect(api_url, autocommit=True) as conn:
        conn.execute("RESET ROLE")
        conn.execute("SET default_transaction_read_only = off")  # nawet bez trybu tylko odczyt
        with pytest.raises(psycopg.errors.Error):
            conn.execute(sql)  # type: ignore[arg-type]


def test_api_account_attributes(api_url: str) -> None:
    with psycopg.connect(api_url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        assert row == (False, False, False, False, False)
        groups = conn.execute(
            "SELECT b.rolname FROM pg_auth_members m JOIN pg_roles b ON b.oid = m.roleid "
            "JOIN pg_roles u ON u.oid = m.member WHERE u.rolname = current_user"
        ).fetchall()
        assert groups == []  # bez członkostw: tylko SELECT na 4 tabelach rynkowych
        assert conn.execute("SHOW default_transaction_read_only").fetchone() == ("on",)


@pytest.fixture(scope="module")
def pg_schema(api_url: str) -> Any:
    return conformance_schema(create_app(PostgresReader.from_url(api_url, QUOTE)))


# Schemat leniwy nie przejmuje filtrów schematu z fixture: wykluczenie E7 i E9 jeszcze raz.
_lazy: Any = schemathesis.pytest.from_fixture("pg_schema")
lazy_schema: Any = _lazy.exclude(operation_id=sorted(LATER_STAGES))


@lazy_schema.parametrize()  # pyright: ignore[reportUntypedFunctionDecorator]
@settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
        HealthCheck.function_scoped_fixture,
    ],
)
def test_schemathesis_on_postgres(case: Any) -> None:
    validate(case)
