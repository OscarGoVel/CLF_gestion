"""codigo_barras en productos + índice

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-28
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS codigo_barras TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_productos_codigo_barras ON productos(codigo_barras)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_productos_codigo_barras")
