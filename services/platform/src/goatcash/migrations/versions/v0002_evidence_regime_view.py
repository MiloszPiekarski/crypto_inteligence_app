"""Kolumna `evidence.regime_view` z kontraktu `Evidence` v1 (roadmapa E2, „Kontrakty”).

Revision ID: 0002
Poprzednia: 0001
Utworzono: 2026-11-23

Migracja 0001 odwzorowała listę kolumn `evidence` z tabeli grup danych roadmapy, w której
brak `regime_view`; kontrakt `Evidence` v1 go wymaga (wartość albo null).
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE evidence ADD COLUMN regime_view text CHECK (regime_view IN "
        "('trend_up', 'trend_down', 'range', 'high_volatility', 'crisis'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE evidence DROP COLUMN regime_view")
