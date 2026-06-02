"""descripcion_articulo en estudio_mercado_cotizaciones

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE estudio_mercado_cotizaciones "
        "ADD COLUMN IF NOT EXISTS descripcion_articulo TEXT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE estudio_mercado_cotizaciones DROP COLUMN IF EXISTS descripcion_articulo"
    )
