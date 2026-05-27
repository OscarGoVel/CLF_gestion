"""Tabla razones_sociales con seed de RS default (CLF)

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS razones_sociales (
            id              SERIAL PRIMARY KEY,
            nombre          TEXT NOT NULL,
            rfc             TEXT NOT NULL UNIQUE,
            regimen_fiscal  TEXT,
            codigo_postal   TEXT,
            domicilio       TEXT,
            es_default      BOOLEAN DEFAULT FALSE,
            activa          BOOLEAN DEFAULT TRUE,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        INSERT INTO razones_sociales (nombre, rfc, domicilio, es_default)
        VALUES (
            'Comercializadora, Logistica y Fuerza Yucateca S.A. de C.V.',
            'CLF240418U94',
            'Calle 17 No. 56 Depto. 74, Kanasin, Yucatan',
            TRUE
        )
        ON CONFLICT (rfc) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS razones_sociales")
