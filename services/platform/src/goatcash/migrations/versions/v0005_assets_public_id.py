"""Publiczny identyfikator aktywa `assets.public_id` dla API (roadmapa E6, decyzja D2).

Revision ID: 0005
Poprzednia: 0004
Utworzono: 2026-11-28

Kontrakt API (E2) identyfikuje aktywo przez UUID, a `assets.asset_id` to kolejny numer
(`bigint`), którego nie pokazujemy na zewnątrz. Decyzja właściciela 28.11.2026 (D2):
osobna kolumna `public_id`.

Kolumna jest generowana z symbolu (`md5('goatcash:asset:' || symbol)::uuid`, STORED,
unikalna): nie wymaga zmian w procesie ingest, a migracja w dół i ponownie w górę daje
dokładnie te same identyfikatory (test `test_migration_0005.py`, bramka G6p). W dół znika
tylko ta kolumna; wszystkie inne dane zostają bez zmian. Ten sam wzór liczy
`goatcash.marketdata.api.asset_public_id` (test porównuje oba).
Uprawnienia: kolumna dziedziczy uprawnienia tabeli (`goatcash_readonly` ma SELECT na `assets`).
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE assets ADD COLUMN public_id uuid NOT NULL "
        "GENERATED ALWAYS AS (md5('goatcash:asset:' || symbol)::uuid) STORED"
    )
    op.execute("ALTER TABLE assets ADD CONSTRAINT assets_public_id_key UNIQUE (public_id)")


def downgrade() -> None:
    op.execute("ALTER TABLE assets DROP COLUMN public_id")
