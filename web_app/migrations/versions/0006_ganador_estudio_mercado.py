"""campo ganador en estudio_mercado_cotizaciones

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-29
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE estudio_mercado_cotizaciones "
        "ADD COLUMN IF NOT EXISTS ganador BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE estudio_mercado_cotizaciones DROP COLUMN IF EXISTS ganador"
    )
