"""Tabla historial_eventos para auditoría de cambios por entidad

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-26
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS historial_eventos (
            id          SERIAL PRIMARY KEY,
            entidad     TEXT NOT NULL,
            entidad_id  INTEGER NOT NULL,
            accion      TEXT NOT NULL,
            detalle     TEXT,
            usuario     TEXT,
            ts          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_historial_entidad ON historial_eventos (entidad, entidad_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS historial_eventos")
