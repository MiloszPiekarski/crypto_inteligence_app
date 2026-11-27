"""Cechy z kluczem pary aktywów i statusem; korelacja zdarzeń w outbox (roadmapa E5).

Revision ID: 0004
Poprzednia: 0003
Utworzono: 2026-11-27

Decyzja właściciela 27.11.2026 (karta E5, „Ścieżka pracy inżynierskiej”, decyzja 1): cechy
liczymy z ceny referencyjnej (`candles_ref`), która nie należy do żadnej giełdy, więc
`feature_values` ma klucz `(feature_set_id, asset_id, quote_asset_id, feature, as_of)`
zamiast `instrument_id`, a status wartości (braki danych = NaN + status, zakres 5) ma
kolumnę `status`.

Tabela jest tworzona od nowa (hypertable z kompresją jak w 0001). Do E5 nic nie zapisywało
cech, więc migracja wymaga pustej tabeli i przerywa się, gdy są w niej wiersze (zamiast po
cichu je zgubić); tak samo `downgrade`.

`event_outbox.correlation_id` (opcjonalne): zdarzenie będące skutkiem innego zdarzenia
(np. `features.ready` po `candle.closed`) niesie jego identyfikator w kopercie (ADR-0003);
puste = zdarzenie nie jest skutkiem innego (korelacja = ono samo).
Uprawnienia jawnie (ADR-0002, punkt 9): goatcash_app DML, goatcash_readonly odczyt.
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

STATUSES = ("ok", "warmup", "missing_data", "not_applicable", "undefined")
COMPRESS_AFTER = "90 days"

_REQUIRE_EMPTY = """
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM feature_values) THEN
        RAISE EXCEPTION 'feature_values ma dane: migracja 0004 wymaga pustej tabeli';
    END IF;
END $$;
"""


def _hypertable(segment_by: str) -> None:
    op.execute(
        "SELECT create_hypertable('public.feature_values', by_range('as_of', INTERVAL '7 days'))"
    )
    op.execute(
        "ALTER TABLE public.feature_values SET (timescaledb.compress, "
        f"timescaledb.compress_segmentby = '{segment_by}', "
        "timescaledb.compress_orderby = 'as_of DESC')"
    )
    op.execute(
        f"SELECT add_compression_policy('public.feature_values', INTERVAL '{COMPRESS_AFTER}')"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON feature_values TO goatcash_app")
    op.execute("GRANT SELECT ON feature_values TO goatcash_readonly")


def upgrade() -> None:
    op.execute(_REQUIRE_EMPTY)
    op.execute("DROP TABLE feature_values")
    statuses = ", ".join(f"'{s}'" for s in STATUSES)
    op.execute(
        f"""
        CREATE TABLE feature_values (
            feature_set_id bigint NOT NULL REFERENCES feature_sets,
            asset_id       bigint NOT NULL REFERENCES assets,
            quote_asset_id bigint NOT NULL REFERENCES assets,
            feature        text NOT NULL,
            as_of          timestamptz NOT NULL,
            data_cutoff    timestamptz NOT NULL,
            value          double precision NOT NULL,
            status         text NOT NULL CHECK (status IN ({statuses})),
            ingested_at    timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (feature_set_id, asset_id, quote_asset_id, feature, as_of),
            CHECK (data_cutoff <= as_of),
            -- wartość jest liczbą tylko przy statusie ok; poza ok zawsze NaN (bez interpolacji)
            CHECK ((status = 'ok') = (value <> 'NaN'::double precision))
        )
        """
    )
    _hypertable("feature_set_id, asset_id, quote_asset_id, feature")
    op.execute("ALTER TABLE event_outbox ADD COLUMN correlation_id uuid")


def downgrade() -> None:
    op.execute("ALTER TABLE event_outbox DROP COLUMN correlation_id")
    op.execute(_REQUIRE_EMPTY)
    op.execute("DROP TABLE feature_values")
    op.execute(
        """
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
        )
        """
    )
    _hypertable("feature_set_id, instrument_id, feature")
