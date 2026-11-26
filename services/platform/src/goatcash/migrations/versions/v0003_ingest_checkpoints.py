"""Punkty kontrolne pobierania świec i precyzja instrumentów (roadmapa E4, punkty 2 i 6).

Revision ID: 0003
Poprzednia: 0002
Utworzono: 2026-11-26

Jeden wiersz na zadanie i parę: `cursor_ts` = początek następnego okna (wszystko przed
nim jest przetworzone). Zapis w tej samej transakcji co świece okna, więc przerwanie
procesu nie zostawia punktu kontrolnego przed albo za zapisanymi danymi.
Precyzja instrumentu (krok ceny i ilości z giełdy, punkt 2 „Normalizacja”) nie miała
kolumn w 0001: `instruments.price_tick` i `instruments.amount_step` (dodatnie, opcjonalne).
Uprawnienia jawnie (ADR-0002, punkt 9): goatcash_app DML, goatcash_readonly odczyt.
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE ingest_checkpoints (
            job        text NOT NULL,
            pair       text NOT NULL,
            cursor_ts  timestamptz NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (job, pair)
        )
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ingest_checkpoints TO goatcash_app")
    op.execute("GRANT SELECT ON ingest_checkpoints TO goatcash_readonly")
    op.execute(
        "ALTER TABLE instruments"
        " ADD COLUMN price_tick numeric CHECK (price_tick > 0),"
        " ADD COLUMN amount_step numeric CHECK (amount_step > 0)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE instruments DROP COLUMN price_tick, DROP COLUMN amount_step")
    op.execute("DROP TABLE ingest_checkpoints")
