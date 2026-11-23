"""Schemat początkowy: wszystkie grupy tabel z roadmapy E2, schemat `bot`, role, audyt.

Revision ID: 0001
Poprzednia: brak
Utworzono: 2026-11-23

Źródła: roadmapa E2 („Model danych (grupy tabel)”), ADR-0002 (typy, hypertable, role),
ADR-0003 (`event_outbox`), ADR-0004 (tabele Better Auth), ADR-0006 (schemat `bot`).

Role tworzone są jako grupy NOLOGIN; konta z hasłem (LOGIN) zakłada infrastruktura
(Ansible, E3) i dodaje do grup. Hasła nigdy nie trafiają do migracji.
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ROLES = (
    "goatcash_app",
    "goatcash_auth",
    "goatcash_executor",
    "goatcash_readonly",
)

# Hypertable (ADR-0002, punkt 6): tabela -> (kolumna czasu, fragment, segmentacja kompresji).
# Kompresja danych starszych niż 90 dni (Fundamenty, przepływ 6).
HYPERTABLES = {
    "candles": ("ts", "7 days", "instrument_id, timeframe"),
    "candles_ref": ("ts", "7 days", "asset_id, quote_asset_id, timeframe"),
    "trades_agg_1m": ("ts", "7 days", "instrument_id"),
    "funding_rates": ("ts", "30 days", "instrument_id"),
    "open_interest": ("ts", "30 days", "instrument_id"),
    "orderbook_top": ("ts", "1 day", "instrument_id"),
    "feature_values": ("as_of", "7 days", "feature_set_id, instrument_id, feature"),
}
COMPRESS_AFTER = "90 days"

EXTENSIONS = """
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS vector;
"""

MARKET = """
CREATE TABLE assets (
    asset_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol      text NOT NULL UNIQUE,
    name        text NOT NULL,
    coingecko_id text UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE instruments (
    instrument_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    exchange      text NOT NULL,
    symbol        text NOT NULL,
    kind          text NOT NULL CHECK (kind IN ('spot', 'perp')),
    base_asset_id  bigint NOT NULL REFERENCES assets,
    quote_asset_id bigint NOT NULL REFERENCES assets,
    active        boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (exchange, symbol, kind)
);

CREATE TABLE candles (
    instrument_id bigint NOT NULL REFERENCES instruments,
    timeframe     text NOT NULL CHECK (timeframe IN ('1m', '5m', '15m', '1h', '4h', '1d')),
    ts            timestamptz NOT NULL,
    open          numeric NOT NULL,
    high          numeric NOT NULL,
    low           numeric NOT NULL,
    close         numeric NOT NULL,
    volume        numeric NOT NULL CHECK (volume >= 0),
    source        text NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, timeframe, ts),
    CHECK (low <= open AND low <= close AND high >= open AND high >= close AND low <= high)
);

-- Cena referencyjna aktywa = mediana giełd (bez instrument_id: dotyczy aktywa i kwotowania).
CREATE TABLE candles_ref (
    asset_id       bigint NOT NULL REFERENCES assets,
    quote_asset_id bigint NOT NULL REFERENCES assets,
    timeframe      text NOT NULL CHECK (timeframe IN ('1m', '5m', '15m', '1h', '4h', '1d')),
    ts             timestamptz NOT NULL,
    open           numeric NOT NULL,
    high           numeric NOT NULL,
    low            numeric NOT NULL,
    close          numeric NOT NULL,
    volume         numeric NOT NULL CHECK (volume >= 0),
    sources        text[] NOT NULL,
    source         text NOT NULL DEFAULT 'median',
    ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (asset_id, quote_asset_id, timeframe, ts)
);

CREATE TABLE trades_agg_1m (
    instrument_id bigint NOT NULL REFERENCES instruments,
    ts            timestamptz NOT NULL,
    trades        integer NOT NULL CHECK (trades >= 0),
    buy_volume    numeric NOT NULL CHECK (buy_volume >= 0),
    sell_volume   numeric NOT NULL CHECK (sell_volume >= 0),
    vwap          numeric,
    source        text NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, ts)
);

CREATE TABLE funding_rates (
    instrument_id bigint NOT NULL REFERENCES instruments,
    ts            timestamptz NOT NULL,
    rate          numeric NOT NULL,
    source        text NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, ts)
);

CREATE TABLE open_interest (
    instrument_id bigint NOT NULL REFERENCES instruments,
    ts            timestamptz NOT NULL,
    open_interest numeric NOT NULL CHECK (open_interest >= 0),
    source        text NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, ts)
);

CREATE TABLE orderbook_top (
    instrument_id bigint NOT NULL REFERENCES instruments,
    ts            timestamptz NOT NULL,
    bid_price     numeric NOT NULL,
    bid_size      numeric NOT NULL CHECK (bid_size >= 0),
    ask_price     numeric NOT NULL,
    ask_size      numeric NOT NULL CHECK (ask_size >= 0),
    source        text NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, ts),
    CHECK (bid_price <= ask_price)
);
"""

DATA_QUALITY = """
CREATE TABLE dq_events (
    dq_event_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    instrument_id bigint REFERENCES instruments,
    dataset       text NOT NULL,
    ts            timestamptz NOT NULL,
    kind          text NOT NULL,
    decision      text NOT NULL CHECK (decision IN ('rejected', 'flagged', 'repaired')),
    details       jsonb NOT NULL DEFAULT '{}',
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX dq_events_dataset_ts ON dq_events (dataset, ts);

CREATE TABLE dq_status (
    dataset       text NOT NULL,
    instrument_id bigint NOT NULL REFERENCES instruments,
    status        text NOT NULL CHECK (status IN ('ok', 'degraded', 'stale', 'down')),
    completeness  double precision CHECK (completeness BETWEEN 0 AND 1),
    last_ts       timestamptz,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset, instrument_id)
);
"""

FEATURES = """
CREATE TABLE feature_sets (
    feature_set_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name           text NOT NULL,
    version        text NOT NULL,
    definition     jsonb NOT NULL,
    code_version   text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, version)
);

CREATE TABLE feature_values (
    feature_set_id bigint NOT NULL REFERENCES feature_sets,
    instrument_id  bigint NOT NULL REFERENCES instruments,
    feature        text NOT NULL,
    as_of          timestamptz NOT NULL,
    data_cutoff    timestamptz NOT NULL,
    value          double precision,
    ingested_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_set_id, instrument_id, feature, as_of),
    CHECK (data_cutoff <= as_of)
);
"""

ANALYSIS = """
CREATE TABLE agents (
    agent_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    kind        text NOT NULL,
    description text NOT NULL DEFAULT '',
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE evidence (
    evidence_id      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id        uuid NOT NULL UNIQUE,
    agent_id         bigint NOT NULL REFERENCES agents,
    instrument_id    bigint REFERENCES instruments,
    asset_id         bigint REFERENCES assets,
    horizon          text NOT NULL,
    as_of            timestamptz NOT NULL,
    data_cutoff      timestamptz NOT NULL,
    p_up             double precision CHECK (p_up BETWEEN 0 AND 1),
    quantiles        jsonb,
    facts            jsonb NOT NULL,
    invalidation     text,
    status           text NOT NULL
        CHECK (status IN ('active', 'invalidated', 'expired', 'settled')),
    schema_version   integer NOT NULL,
    agent_version    text NOT NULL,
    model_version    text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (data_cutoff <= as_of),
    CHECK (instrument_id IS NOT NULL OR asset_id IS NOT NULL)
);
CREATE INDEX evidence_asset_as_of ON evidence (asset_id, as_of DESC);

CREATE TABLE assessments (
    assessment_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id      uuid NOT NULL UNIQUE,
    asset_id       bigint NOT NULL REFERENCES assets,
    horizon        text NOT NULL,
    as_of          timestamptz NOT NULL,
    p_up           double precision NOT NULL CHECK (p_up BETWEEN 0 AND 1),
    quantiles      jsonb,
    regime         text,
    evidence_ids   bigint[] NOT NULL,
    fusion_version text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX assessments_asset_as_of ON assessments (asset_id, horizon, as_of DESC);

CREATE TABLE narratives (
    narrative_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    assessment_id  bigint NOT NULL REFERENCES assessments,
    language       text NOT NULL CHECK (language IN ('pl', 'en')),
    body           text NOT NULL,
    model          text NOT NULL,
    prompt_version text NOT NULL,
    validated      boolean NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
"""

SETTLEMENT = """
CREATE TABLE forecast_outcomes (
    evidence_id  bigint PRIMARY KEY REFERENCES evidence,
    settled_at   timestamptz NOT NULL,
    outcome_up   boolean NOT NULL,
    realized_return double precision NOT NULL,
    brier        double precision NOT NULL CHECK (brier BETWEEN 0 AND 1),
    log_loss     double precision NOT NULL CHECK (log_loss >= 0),
    pinball      double precision
);

CREATE TABLE agent_metrics_daily (
    agent_id  bigint NOT NULL REFERENCES agents,
    day       date NOT NULL,
    regime    text NOT NULL,
    horizon   text NOT NULL,
    n         integer NOT NULL CHECK (n >= 0),
    brier     double precision,
    log_loss  double precision,
    ece       double precision,
    PRIMARY KEY (agent_id, day, regime, horizon)
);

CREATE TABLE fusion_weights (
    fusion_version text NOT NULL,
    agent_id       bigint NOT NULL REFERENCES agents,
    regime         text NOT NULL,
    horizon        text NOT NULL,
    weight         double precision NOT NULL CHECK (weight >= 0),
    valid_from     timestamptz NOT NULL,
    PRIMARY KEY (fusion_version, agent_id, regime, horizon)
);
"""

TEXTS = """
CREATE TABLE news_items (
    news_item_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source       text NOT NULL,
    url          text NOT NULL,
    title        text NOT NULL,
    body         text,
    content_hash text NOT NULL UNIQUE,
    published_at timestamptz NOT NULL,
    ingested_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE news_events (
    news_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    news_item_id  bigint NOT NULL REFERENCES news_items,
    asset_id      bigint REFERENCES assets,
    kind          text NOT NULL,
    sentiment     double precision CHECK (sentiment BETWEEN -1 AND 1),
    confidence    double precision CHECK (confidence BETWEEN 0 AND 1),
    model         text NOT NULL,
    prompt_version text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Wymiar 1024 do potwierdzenia przy wyborze modelu osadzeń (E9); zmiana = migracja.
CREATE TABLE embeddings (
    news_item_id bigint NOT NULL REFERENCES news_items,
    model        text NOT NULL,
    embedding    vector(1024) NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (news_item_id, model)
);
"""

# Tabele Better Auth (ADR-0004): nazwy kolumn jak w schemacie Better Auth 1.x (camelCase),
# nazwy tabel z roadmapy/ADR. Zgodność z przypiętą wersją sprawdzi auth-schema-drift (E6).
AUTH = """
CREATE TABLE "user" (
    id                 text PRIMARY KEY,
    name               text NOT NULL,
    email              text NOT NULL UNIQUE,
    "emailVerified"    boolean NOT NULL DEFAULT false,
    image              text,
    "twoFactorEnabled" boolean DEFAULT false,
    "createdAt"        timestamptz NOT NULL DEFAULT now(),
    "updatedAt"        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE session (
    id          text PRIMARY KEY,
    "expiresAt" timestamptz NOT NULL,
    token       text NOT NULL UNIQUE,
    "createdAt" timestamptz NOT NULL DEFAULT now(),
    "updatedAt" timestamptz NOT NULL DEFAULT now(),
    "ipAddress" text,
    "userAgent" text,
    "userId"    text NOT NULL REFERENCES "user" ON DELETE CASCADE
);
CREATE INDEX session_user_id ON session ("userId");

CREATE TABLE account (
    id                      text PRIMARY KEY,
    "accountId"             text NOT NULL,
    "providerId"            text NOT NULL,
    "userId"                text NOT NULL REFERENCES "user" ON DELETE CASCADE,
    "accessToken"           text,
    "refreshToken"          text,
    "idToken"               text,
    "accessTokenExpiresAt"  timestamptz,
    "refreshTokenExpiresAt" timestamptz,
    scope                   text,
    password                text,
    "createdAt"             timestamptz NOT NULL DEFAULT now(),
    "updatedAt"             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX account_user_id ON account ("userId");

CREATE TABLE verification (
    id          text PRIMARY KEY,
    identifier  text NOT NULL,
    value       text NOT NULL,
    "expiresAt" timestamptz NOT NULL,
    "createdAt" timestamptz NOT NULL DEFAULT now(),
    "updatedAt" timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX verification_identifier ON verification (identifier);

CREATE TABLE two_factor (
    id            text PRIMARY KEY,
    secret        text NOT NULL,
    "backupCodes" text NOT NULL,
    "userId"      text NOT NULL REFERENCES "user" ON DELETE CASCADE
);

CREATE TABLE passkey (
    id             text PRIMARY KEY,
    name           text,
    "publicKey"    text NOT NULL,
    "userId"       text NOT NULL REFERENCES "user" ON DELETE CASCADE,
    "credentialID" text NOT NULL,
    counter        integer NOT NULL,
    "deviceType"   text NOT NULL,
    "backedUp"     boolean NOT NULL,
    transports     text,
    "createdAt"    timestamptz,
    aaguid         text
);

CREATE TABLE jwks (
    id           text PRIMARY KEY,
    "publicKey"  text NOT NULL,
    "privateKey" text NOT NULL,
    "createdAt"  timestamptz NOT NULL,
    "expiresAt"  timestamptz
);
"""

USERS = """
CREATE TABLE roles (
    role        text PRIMARY KEY CHECK (role IN ('user', 'pro_tester', 'admin')),
    description text NOT NULL
);
INSERT INTO roles (role, description) VALUES
    ('user', 'użytkownik'),
    ('pro_tester', 'tester funkcji Pro'),
    ('admin', 'administrator');

CREATE TABLE profiles (
    user_id      text PRIMARY KEY REFERENCES "user" ON DELETE CASCADE,
    public_id    uuid NOT NULL UNIQUE,
    role         text NOT NULL DEFAULT 'user' REFERENCES roles,
    display_name text,
    language     text NOT NULL DEFAULT 'pl' CHECK (language IN ('pl', 'en')),
    timezone     text NOT NULL DEFAULT 'Europe/Warsaw',
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE watchlists (
    watchlist_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id    uuid NOT NULL UNIQUE,
    user_id      text NOT NULL REFERENCES "user" ON DELETE CASCADE,
    name         text NOT NULL,
    asset_ids    bigint[] NOT NULL DEFAULT '{}',
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);
"""

ALERTS = """
CREATE TABLE notification_channels (
    channel_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id   uuid NOT NULL UNIQUE,
    user_id     text NOT NULL REFERENCES "user" ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('email', 'telegram', 'web_push')),
    address     text NOT NULL,
    verified    boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, kind, address)
);

CREATE TABLE alert_rules (
    alert_rule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id     uuid NOT NULL UNIQUE,
    user_id       text NOT NULL REFERENCES "user" ON DELETE CASCADE,
    asset_id      bigint REFERENCES assets,
    condition     jsonb NOT NULL,
    cooldown      interval NOT NULL DEFAULT '1 hour',
    active        boolean NOT NULL DEFAULT true,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE alert_events (
    alert_event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_rule_id  bigint NOT NULL REFERENCES alert_rules ON DELETE CASCADE,
    triggered_at   timestamptz NOT NULL,
    dedup_key      text NOT NULL UNIQUE,
    payload        jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Idempotencja dostarczeń: jedna próba na zdarzenie i kanał (UNIQUE).
CREATE TABLE deliveries (
    delivery_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alert_event_id bigint NOT NULL REFERENCES alert_events ON DELETE CASCADE,
    channel_id     bigint NOT NULL REFERENCES notification_channels ON DELETE CASCADE,
    status         text NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    attempts       integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error     text,
    sent_at        timestamptz,
    UNIQUE (alert_event_id, channel_id)
);
"""

BACKTESTS = """
CREATE TABLE strategies (
    strategy_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id   uuid NOT NULL UNIQUE,
    user_id     text REFERENCES "user" ON DELETE CASCADE,
    name        text NOT NULL,
    definition  jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE backtests (
    backtest_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id    uuid NOT NULL UNIQUE,
    strategy_id  bigint NOT NULL REFERENCES strategies ON DELETE CASCADE,
    period_from  timestamptz NOT NULL,
    period_to    timestamptz NOT NULL,
    status       text NOT NULL CHECK (status IN ('queued', 'running', 'done', 'failed')),
    data_hash    text,
    code_version text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CHECK (period_from < period_to)
);

CREATE TABLE backtest_results (
    backtest_id bigint PRIMARY KEY REFERENCES backtests ON DELETE CASCADE,
    metrics     jsonb NOT NULL,
    equity      jsonb NOT NULL,
    data_hash   text NOT NULL,
    code_version text NOT NULL,
    finished_at timestamptz NOT NULL
);
"""

EVENTS_AND_AUDIT = """
-- ADR-0003: zdarzenie zapisywane w tej samej transakcji co zmiana danych.
CREATE TABLE event_outbox (
    outbox_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id     uuid NOT NULL UNIQUE,
    type         text NOT NULL,
    schema_version integer NOT NULL,
    payload      jsonb NOT NULL,
    occurred_at  timestamptz NOT NULL,
    published_at timestamptz
);
CREATE INDEX event_outbox_unpublished ON event_outbox (outbox_id) WHERE published_at IS NULL;

CREATE TABLE audit_log (
    audit_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at         timestamptz NOT NULL DEFAULT now(),
    actor      text NOT NULL,
    action     text NOT NULL,
    target     text,
    details    jsonb NOT NULL DEFAULT '{}'
);

-- Tylko do dopisywania: odrzuca UPDATE, DELETE i TRUNCATE także właścicielowi tabeli.
CREATE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log jest tylko do dopisywania (%)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$;
CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_append_only();
"""

BOT = """
CREATE SCHEMA bot;

-- Klucze giełd zaszyfrowane kopertowo (ADR-0006); kolumny z szyfrogramem widzi tylko executor.
CREATE TABLE bot.exchange_connections (
    connection_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id      uuid NOT NULL UNIQUE,
    user_id        text NOT NULL REFERENCES public."user" ON DELETE CASCADE,
    exchange       text NOT NULL,
    label          text NOT NULL,
    api_key_enc    bytea NOT NULL,
    api_secret_enc bytea NOT NULL,
    dek_enc        bytea NOT NULL,
    key_fingerprint text NOT NULL,
    permissions    text[] NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    revoked_at     timestamptz,
    CHECK (NOT ('withdraw' = ANY (permissions)))
);

CREATE TABLE bot.bot_configs (
    bot_config_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id     uuid NOT NULL UNIQUE,
    user_id       text NOT NULL REFERENCES public."user" ON DELETE CASCADE,
    connection_id bigint NOT NULL REFERENCES bot.exchange_connections,
    mode          text NOT NULL CHECK (mode IN ('paper', 'testnet', 'live')),
    policy        jsonb NOT NULL,
    limits        jsonb NOT NULL,
    active        boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bot.order_intents (
    intent_id     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id     uuid NOT NULL UNIQUE,
    bot_config_id bigint NOT NULL REFERENCES bot.bot_configs,
    instrument_id bigint NOT NULL REFERENCES public.instruments,
    side          text NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity      numeric NOT NULL CHECK (quantity > 0),
    order_type    text NOT NULL CHECK (order_type IN ('market', 'limit')),
    limit_price   numeric CHECK (limit_price > 0),
    stop_loss     numeric NOT NULL CHECK (stop_loss > 0),
    take_profit   numeric CHECK (take_profit > 0),
    assessment_id bigint REFERENCES public.assessments,
    status        text NOT NULL CHECK (status IN ('new', 'accepted', 'rejected', 'expired')),
    reject_reason text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CHECK (order_type <> 'limit' OR limit_price IS NOT NULL)
);
CREATE INDEX order_intents_new ON bot.order_intents (intent_id) WHERE status = 'new';

CREATE TABLE bot.orders (
    order_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    intent_id         bigint NOT NULL REFERENCES bot.order_intents,
    client_order_id   text NOT NULL UNIQUE,
    exchange_order_id text,
    status            text NOT NULL CHECK (status IN
        ('pending', 'open', 'partially_filled', 'filled', 'cancelled', 'rejected', 'error')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bot.fills (
    fill_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id         bigint NOT NULL REFERENCES bot.orders,
    exchange_fill_id text NOT NULL,
    price            numeric NOT NULL CHECK (price > 0),
    quantity         numeric NOT NULL CHECK (quantity > 0),
    fee              numeric NOT NULL,
    fee_asset        text NOT NULL,
    filled_at        timestamptz NOT NULL,
    UNIQUE (order_id, exchange_fill_id)
);

CREATE TABLE bot.positions (
    bot_config_id bigint NOT NULL REFERENCES bot.bot_configs,
    instrument_id bigint NOT NULL REFERENCES public.instruments,
    quantity      numeric NOT NULL,
    avg_price     numeric,
    realized_pnl  numeric NOT NULL DEFAULT 0,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (bot_config_id, instrument_id)
);

CREATE TABLE bot.bot_events (
    bot_event_id  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bot_config_id bigint REFERENCES bot.bot_configs,
    order_id      bigint REFERENCES bot.orders,
    kind          text NOT NULL,
    details       jsonb NOT NULL DEFAULT '{}',
    at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE bot.kill_switches (
    scope       text NOT NULL CHECK (scope IN ('global', 'user', 'bot')),
    scope_id    text NOT NULL DEFAULT '',
    engaged     boolean NOT NULL,
    reason      text NOT NULL,
    changed_by  text NOT NULL,
    changed_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, scope_id)
);
"""

# Tabele Better Auth i kolumny z szyfrogramem kluczy (używane w GRANTS i w teście migracji).
AUTH_TABLES = ("user", "session", "account", "verification", "two_factor", "passkey", "jwks")
SECRET_COLUMNS = ("api_key_enc", "api_secret_enc", "dek_enc")

# ADR-0002, punkt 9. Uprawnienia nadawane jawnie, bez ALTER DEFAULT PRIVILEGES: nowa tabela
# w kolejnej migracji dostaje uprawnienia w tej migracji, z testem.
GRANTS = """
GRANT USAGE ON SCHEMA public TO goatcash_app, goatcash_auth, goatcash_readonly;

-- goatcash_app: DML w public poza tabelami Better Auth; audit_log tylko INSERT/SELECT.
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
             AND tablename NOT IN ('user', 'session', 'account', 'verification',
                                   'two_factor', 'passkey', 'jwks',
                                   'audit_log', 'alembic_version')
    LOOP
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON public.%I TO goatcash_app', t);
        -- goatcash_readonly bez danych osobowych (ADR-0002, punkt 9).
        IF t NOT IN ('profiles', 'watchlists', 'notification_channels', 'deliveries') THEN
            EXECUTE format('GRANT SELECT ON public.%I TO goatcash_readonly', t);
        END IF;
    END LOOP;
END $$;
GRANT SELECT, INSERT ON public.audit_log TO goatcash_app;
GRANT SELECT ON public.audit_log TO goatcash_readonly;
GRANT SELECT ON public."user" TO goatcash_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO goatcash_app;

-- goatcash_auth: tylko tabele Better Auth i odczyt ról/profili.
GRANT SELECT, INSERT, UPDATE, DELETE ON
    public."user", public."session", public."account", public."verification",
    public."two_factor", public."passkey", public."jwks"
    TO goatcash_auth;
GRANT SELECT ON public.roles, public.profiles TO goatcash_auth;

-- Schemat bot: executor ma pełny DML; app zapisuje intencje i czyta stan, bez szyfrogramów.
GRANT USAGE ON SCHEMA bot TO goatcash_executor, goatcash_app;
GRANT USAGE ON SCHEMA public TO goatcash_executor;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA bot TO goatcash_executor;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA bot TO goatcash_executor, goatcash_app;
GRANT SELECT (instrument_id, base_asset_id, quote_asset_id, exchange, symbol, kind, active)
    ON public.instruments TO goatcash_executor;
GRANT SELECT, INSERT ON bot.order_intents TO goatcash_app;
GRANT SELECT, INSERT, UPDATE ON bot.bot_configs, bot.kill_switches TO goatcash_app;
GRANT SELECT ON bot.orders, bot.fills, bot.positions, bot.bot_events TO goatcash_app;
GRANT SELECT (connection_id, public_id, user_id, exchange, label, key_fingerprint,
              permissions, created_at, revoked_at)
    ON bot.exchange_connections TO goatcash_app;
"""


def upgrade() -> None:
    for role in ROLES:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') "
            f"THEN CREATE ROLE {role} NOLOGIN; END IF; END $$;"
        )
    for block in (
        EXTENSIONS,
        MARKET,
        DATA_QUALITY,
        FEATURES,
        ANALYSIS,
        SETTLEMENT,
        TEXTS,
        AUTH,
        USERS,
        ALERTS,
        BACKTESTS,
        EVENTS_AND_AUDIT,
        BOT,
    ):
        op.execute(block)
    for table, (column, chunk, segment_by) in HYPERTABLES.items():
        op.execute(
            f"SELECT create_hypertable('public.{table}', by_range('{column}', INTERVAL '{chunk}'))"
        )
        op.execute(
            f"ALTER TABLE public.{table} SET (timescaledb.compress, "
            f"timescaledb.compress_segmentby = '{segment_by}', "
            f"timescaledb.compress_orderby = '{column} DESC')"
        )
        op.execute(f"SELECT add_compression_policy('public.{table}', INTERVAL '{COMPRESS_AFTER}')")
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("DROP SCHEMA bot CASCADE")
    tables = (
        "audit_log",
        "event_outbox",
        "backtest_results",
        "backtests",
        "strategies",
        "deliveries",
        "alert_events",
        "alert_rules",
        "notification_channels",
        "watchlists",
        "profiles",
        "roles",
        "jwks",
        "passkey",
        "two_factor",
        "verification",
        "account",
        "session",
        "user",
        "embeddings",
        "news_events",
        "news_items",
        "fusion_weights",
        "agent_metrics_daily",
        "forecast_outcomes",
        "narratives",
        "assessments",
        "evidence",
        "agents",
        "feature_values",
        "feature_sets",
        "dq_status",
        "dq_events",
        "orderbook_top",
        "open_interest",
        "funding_rates",
        "trades_agg_1m",
        "candles_ref",
        "candles",
        "instruments",
        "assets",
    )
    for table in tables:
        op.execute(f'DROP TABLE public."{table}"')
    op.execute("DROP FUNCTION audit_log_append_only()")
    op.execute("DROP EXTENSION vector")
    op.execute("DROP EXTENSION timescaledb")
    for role in ROLES:
        op.execute(f"REVOKE ALL ON SCHEMA public FROM {role}")
        op.execute(f"DROP ROLE {role}")
