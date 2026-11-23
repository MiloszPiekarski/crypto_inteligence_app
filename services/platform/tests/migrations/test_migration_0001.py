"""Migracja 0001 na czystym Postgresie z TimescaleDB i pgvector (bramka G2, `migration`).

Wymaga Dockera (testcontainers). Uruchomienie: `make db-migration-test`. W zwykłym
`make test` pomijane markerem `migration` (pyproject: -m "not migration").
"""

import importlib.util
import os
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer

pytestmark = pytest.mark.migration

PLATFORM = Path(__file__).resolve().parents[2]
MIGRATION = PLATFORM / "src/goatcash/migrations/versions/v0001_schemat_poczatkowy.py"
# Obraz przypięty do digestu (ADR-0002): PostgreSQL 17 + TimescaleDB + pgvector, wieloarch.
# (arm64 u właściciela i na Oracle A1, amd64 w CI). Zmiana = PR z wynikiem tego testu.
IMAGE = (
    "timescale/timescaledb-ha:pg17"
    "@sha256:c72b4cb8aaa0a52c0870c2b0a48173c595ee9bef0f3d8f92c3f546c69fef3567"
)

PUBLIC_TABLES = {
    # Rynek
    "assets", "instruments", "candles", "candles_ref", "trades_agg_1m", "funding_rates",
    "open_interest", "orderbook_top",
    # Jakość danych, cechy
    "dq_events", "dq_status", "feature_sets", "feature_values",
    # Analiza, rozliczanie
    "agents", "evidence", "assessments", "narratives", "forecast_outcomes",
    "agent_metrics_daily", "fusion_weights",
    # Teksty
    "news_items", "news_events", "embeddings",
    # Użytkownicy (Better Auth + nasze)
    "user", "session", "account", "verification", "two_factor", "passkey", "jwks",
    "profiles", "roles", "watchlists",
    # Alerty, backtesty
    "alert_rules", "alert_events", "notification_channels", "deliveries",
    "strategies", "backtests", "backtest_results",
    # Zdarzenia (ADR-0003), audyt
    "event_outbox", "audit_log",
}  # fmt: skip
BOT_TABLES = {
    "exchange_connections", "bot_configs", "order_intents", "orders", "fills", "positions",
    "bot_events", "kill_switches",
}  # fmt: skip


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("v0001", MIGRATION)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def db_url() -> Iterator[str]:
    with PostgresContainer(IMAGE, driver=None) as pg:
        yield pg.get_connection_url()


def alembic(db_url: str, action: str) -> None:
    cfg = Config(str(PLATFORM / "alembic.ini"))
    cfg.cmd_opts = None
    os.environ["GOATCASH_DATABASE_URL"] = db_url.replace("postgresql://", "postgresql+psycopg://")
    if action == "upgrade":
        command.upgrade(cfg, "head")
    else:
        command.downgrade(cfg, "base")


def execute(db_url: str, sql: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(sql)  # type: ignore[arg-type]


def rows(db_url: str, sql: str) -> list[tuple[object, ...]]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        return conn.execute(sql).fetchall()  # type: ignore[arg-type]


def tables(db_url: str, schema: str) -> set[str]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        found = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,)
        ).fetchall()
    return {str(r[0]) for r in found}


def as_role(db_url: str, role: str, sql: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(f"SET ROLE {role}")  # type: ignore[arg-type]
        conn.execute(sql)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def migrated(db_url: str) -> str:
    alembic(db_url, "upgrade")
    return db_url


def test_postgres_17(migrated: str) -> None:
    assert int(str(rows(migrated, "SHOW server_version_num")[0][0])) // 10000 == 17


def test_upgrade_creates_all_table_groups(migrated: str) -> None:
    assert tables(migrated, "public") - {"alembic_version"} == PUBLIC_TABLES
    assert tables(migrated, "bot") == BOT_TABLES
    extensions = {str(r[0]) for r in rows(migrated, "SELECT extname FROM pg_extension")}
    assert {"timescaledb", "vector"} <= extensions


def test_evidence_matches_contract_v1(migrated: str) -> None:
    # Kolumny tabeli `evidence` dla pól kontraktu Evidence v1 (migracja 0002).
    columns = {
        str(r[0])
        for r in rows(
            migrated,
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'evidence'",
        )
    }
    contract = {"p_up", "quantiles", "regime_view", "facts", "invalidation", "status"}
    assert contract | {"as_of", "data_cutoff", "agent_version", "model_version"} <= columns
    insert = (
        "WITH a AS (INSERT INTO agents (name, kind) VALUES ('rv_{0}', 'rule') RETURNING agent_id),"
        " s AS (INSERT INTO assets (symbol, name) VALUES ('RV{0}', 'x') RETURNING asset_id)"
        " INSERT INTO evidence (public_id, agent_id, asset_id, horizon, as_of, data_cutoff, facts,"
        " status, schema_version, agent_version, regime_view) SELECT gen_random_uuid(),"
        " a.agent_id, s.asset_id, '1d', now(), now(), '{{}}', 'active', 1, '1.0.0', '{1}' FROM a, s"
    )
    execute(migrated, insert.format("OK", "trend_up"))
    with pytest.raises(psycopg.errors.CheckViolation):
        execute(migrated, insert.format("BAD", "moon"))


def test_hypertables_with_compression_policy(migrated: str) -> None:
    hypertables = {
        str(r[0]): bool(r[1])
        for r in rows(
            migrated,
            "SELECT hypertable_name, compression_enabled FROM timescaledb_information.hypertables",
        )
    }
    expected = set(load_migration().HYPERTABLES)
    assert set(hypertables) == expected
    assert all(hypertables.values())
    policies = {
        str(r[0])
        for r in rows(
            migrated,
            "SELECT hypertable_name FROM timescaledb_information.jobs "
            "WHERE proc_name = 'policy_compression'",
        )
    }
    assert policies == expected


def test_audit_log_is_append_only_even_for_owner(migrated: str) -> None:
    execute(migrated, "INSERT INTO audit_log (actor, action) VALUES ('test', 'insert')")
    for sql in ("UPDATE audit_log SET actor = 'x'", "DELETE FROM audit_log", "TRUNCATE audit_log"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            execute(migrated, sql)


@pytest.mark.parametrize(
    ("role", "sql"),
    [
        ("goatcash_app", "UPDATE audit_log SET actor = 'x'"),
        ("goatcash_app", "SELECT api_key_enc FROM bot.exchange_connections"),
        ("goatcash_app", "SELECT dek_enc FROM bot.exchange_connections"),
        ("goatcash_app", "UPDATE bot.orders SET status = 'error'"),
        ("goatcash_app", 'SELECT * FROM "account"'),
        ("goatcash_executor", "SELECT * FROM assessments"),
        ("goatcash_executor", 'SELECT * FROM "user"'),
        ("goatcash_auth", "SELECT * FROM bot.exchange_connections"),
        ("goatcash_auth", "SELECT * FROM evidence"),
        ("goatcash_readonly", "SELECT * FROM bot.exchange_connections"),
        ("goatcash_readonly", 'SELECT * FROM "account"'),
        ("goatcash_readonly", 'SELECT * FROM "user"'),
        ("goatcash_readonly", "SELECT address FROM notification_channels"),
        ("goatcash_readonly", "SELECT display_name FROM profiles"),
        ("goatcash_readonly", "INSERT INTO agents (name, kind) VALUES ('x', 'y')"),
    ],
)
def test_roles_have_least_privilege(migrated: str, role: str, sql: str) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(migrated, role, sql)


@pytest.mark.parametrize(
    ("role", "sql"),
    [
        ("goatcash_app", "SELECT public_id, key_fingerprint FROM bot.exchange_connections"),
        ("goatcash_app", "INSERT INTO audit_log (actor, action) VALUES ('app', 'ok')"),
        ("goatcash_app", "SELECT * FROM candles"),
        ("goatcash_executor", "SELECT api_key_enc, dek_enc FROM bot.exchange_connections"),
        ("goatcash_executor", "SELECT instrument_id, symbol FROM instruments"),
        ("goatcash_auth", 'SELECT * FROM "session"'),
        ("goatcash_readonly", "SELECT * FROM evidence"),
    ],
)
def test_roles_can_do_their_job(migrated: str, role: str, sql: str) -> None:
    as_role(migrated, role, sql)


def test_withdraw_permission_key_rejected(migrated: str) -> None:
    execute(migrated, """INSERT INTO "user" (id, name, email) VALUES ('u1', 'U', 'u@ex.com')""")
    with pytest.raises(psycopg.errors.CheckViolation):
        execute(
            migrated,
            "INSERT INTO bot.exchange_connections (public_id, user_id, exchange, label, "
            "api_key_enc, api_secret_enc, dek_enc, key_fingerprint, permissions) VALUES "
            "(gen_random_uuid(), 'u1', 'binance', 'x', '\\x00', '\\x00', '\\x00', 'f', "
            "ARRAY['spot', 'withdraw'])",
        )


def test_downgrade_base_leaves_clean_database_and_upgrade_again(migrated: str) -> None:
    alembic(migrated, "downgrade")
    assert tables(migrated, "public") == {"alembic_version"}
    assert not rows(migrated, "SELECT 1 FROM pg_namespace WHERE nspname = 'bot'")
    roles = {str(r[0]) for r in rows(migrated, "SELECT rolname FROM pg_roles")}
    assert not roles & set(load_migration().ROLES)
    alembic(migrated, "upgrade")
    assert tables(migrated, "public") - {"alembic_version"} == PUBLIC_TABLES
