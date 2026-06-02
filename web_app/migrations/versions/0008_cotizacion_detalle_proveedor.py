"""proveedor_id en cotizacion_detalle

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE cotizacion_detalle "
        "ADD COLUMN IF NOT EXISTS proveedor_id INTEGER REFERENCES proveedores(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE cotizacion_detalle DROP COLUMN IF EXISTS proveedor_id"
    )
