"""cotizacion_detalle_id en estudio_mercado_items

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE estudio_mercado_items "
        "ADD COLUMN IF NOT EXISTS cotizacion_detalle_id INTEGER REFERENCES cotizacion_detalle(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE estudio_mercado_items DROP COLUMN IF EXISTS cotizacion_detalle_id"
    )
