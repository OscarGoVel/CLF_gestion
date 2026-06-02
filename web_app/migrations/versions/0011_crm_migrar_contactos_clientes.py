"""Migrar clientes.contacto → crm_contactos (un contacto principal por cliente)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-02
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Garantizar que crm_contactos existe (por si migrate_crm.py no fue ejecutado)
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm_contactos (
            id            SERIAL PRIMARY KEY,
            cliente_id    INTEGER NOT NULL REFERENCES clientes(id),
            nombre        TEXT NOT NULL,
            cargo         TEXT,
            email         TEXT NOT NULL,
            telefono      TEXT,
            es_principal  BOOLEAN DEFAULT FALSE,
            opt_out       BOOLEAN DEFAULT FALSE,
            fecha_opt_out TIMESTAMPTZ,
            activo        BOOLEAN DEFAULT TRUE,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Insertar un contacto principal por cada cliente que tenga nombre de contacto
    # y email, y que aún no tenga ningún registro en crm_contactos.
    op.execute("""
        INSERT INTO crm_contactos (cliente_id, nombre, email, telefono, es_principal)
        SELECT
            c.id,
            c.contacto,
            c.email,
            c.telefono,
            TRUE
        FROM clientes c
        WHERE c.contacto IS NOT NULL AND TRIM(c.contacto) != ''
          AND c.email    IS NOT NULL AND TRIM(c.email)    != ''
          AND NOT EXISTS (
              SELECT 1 FROM crm_contactos cc WHERE cc.cliente_id = c.id
          )
    """)


def downgrade() -> None:
    # La migración de datos no se revierte: eliminar contactos migrados
    # podría borrar contactos creados manualmente después de la migración.
    pass
