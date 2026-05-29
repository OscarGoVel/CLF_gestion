"""pg_trgm extension + GIN index en productos.nombre para búsqueda fuzzy

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-29
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_productos_nombre_trgm
        ON productos USING GIN (nombre gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_productos_nombre_trgm")
