"""razon_social_id FK en tablas de documentos + backfill + índices

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-27
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLAS = [
    "cotizaciones",
    "compras",
    "facturas",
    "devoluciones",
    "cuentas_por_pagar",
]


def upgrade() -> None:
    for tabla in _TABLAS:
        op.execute(
            f"ALTER TABLE {tabla} "
            f"ADD COLUMN IF NOT EXISTS razon_social_id INT REFERENCES razones_sociales(id)"
        )

    _backfill = (
        "UPDATE {tabla} "
        "SET razon_social_id = (SELECT id FROM razones_sociales WHERE es_default LIMIT 1) "
        "WHERE razon_social_id IS NULL"
    )
    for tabla in _TABLAS:
        op.execute(_backfill.format(tabla=tabla))

    op.execute("CREATE INDEX IF NOT EXISTS idx_cotizaciones_rs  ON cotizaciones(razon_social_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_compras_rs       ON compras(razon_social_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_facturas_rs      ON facturas(razon_social_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_devoluciones_rs  ON devoluciones(razon_social_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cxp_rs           ON cuentas_por_pagar(razon_social_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cxp_rs")
    op.execute("DROP INDEX IF EXISTS idx_devoluciones_rs")
    op.execute("DROP INDEX IF EXISTS idx_facturas_rs")
    op.execute("DROP INDEX IF EXISTS idx_compras_rs")
    op.execute("DROP INDEX IF EXISTS idx_cotizaciones_rs")
    for tabla in reversed(_TABLAS):
        op.execute(f"ALTER TABLE {tabla} DROP COLUMN IF EXISTS razon_social_id")
