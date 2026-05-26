"""Initial schema — todas las migraciones incrementales de main.py

Revision ID: 0001
Revises:
Create Date: 2026-05-26
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE producto_precio_historial ADD COLUMN IF NOT EXISTS proveedor_id INTEGER REFERENCES proveedores(id)")
    op.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE")
    op.execute("ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS utilidad_pct NUMERIC(6,2) DEFAULT 0")
    op.execute("""
        CREATE TABLE IF NOT EXISTS compra_detalle_cotizacion (
            id                SERIAL PRIMARY KEY,
            compra_detalle_id INTEGER NOT NULL REFERENCES compra_detalle(id),
            cotizacion_id     INTEGER REFERENCES cotizaciones(id),
            cantidad          NUMERIC(14,4) NOT NULL,
            notas             TEXT,
            fecha_registro    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS compradores (
            id             SERIAL PRIMARY KEY,
            cliente_id     INTEGER NOT NULL REFERENCES clientes(id),
            nombre         TEXT NOT NULL,
            cargo          TEXT,
            telefono       TEXT,
            email          TEXT,
            activo         BOOLEAN DEFAULT TRUE,
            fecha_registro TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS comprador_id INTEGER REFERENCES compradores(id)")
    op.execute("ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS descripcion_libre TEXT")
    op.execute("ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS pendiente_catalogo BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE cotizacion_detalle ALTER COLUMN producto_id DROP NOT NULL")
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS costo_promedio NUMERIC(14,4) DEFAULT 0")
    op.execute("ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS costo_entrega NUMERIC(14,4)")
    op.execute("ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS costo_entrega_tipo TEXT")
    op.execute("ALTER TABLE estudios_mercado ADD COLUMN IF NOT EXISTS margen_pct NUMERIC(5,4) DEFAULT 0.35")
    op.execute("ALTER TABLE estudios_mercado ADD COLUMN IF NOT EXISTS cotizacion_id INTEGER REFERENCES cotizaciones(id)")
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_venta NUMERIC(14,4)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS estudio_aplicaciones (
            id             SERIAL PRIMARY KEY,
            estudio_id     INTEGER NOT NULL REFERENCES estudios_mercado(id) ON DELETE CASCADE,
            cotizacion_id  INTEGER NOT NULL REFERENCES cotizaciones(id),
            aplicado_por   INTEGER REFERENCES usuarios(id),
            forzado        BOOLEAN DEFAULT FALSE,
            estado_cot     TEXT,
            fecha          TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS costos_fijos (
            id           SERIAL PRIMARY KEY,
            periodo      TEXT NOT NULL,
            categoria    TEXT NOT NULL,
            descripcion  TEXT NOT NULL,
            monto        NUMERIC(14,2) NOT NULL,
            created_by   TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS margen_pct NUMERIC(8,4)")
    op.execute("ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS resultado VARCHAR(20)")
    op.execute("ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS motivo_perdida VARCHAR(50)")
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_desactualizado BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_venta_fecha TIMESTAMPTZ")
    op.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id              SERIAL PRIMARY KEY,
            cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id),
            monto           NUMERIC(14,2) NOT NULL,
            fecha_pago      DATE NOT NULL,
            metodo          TEXT,
            referencia      TEXT,
            registrado_por  INTEGER REFERENCES usuarios(id),
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pagos_cotizacion ON pagos(cotizacion_id)")
    op.execute("ALTER TABLE facturas ADD COLUMN IF NOT EXISTS cancelada BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE facturas ADD COLUMN IF NOT EXISTS motivo_cancelacion TEXT")
    op.execute("ALTER TABLE compras ADD COLUMN IF NOT EXISTS estado TEXT DEFAULT 'Creada'")
    op.execute("ALTER TABLE compra_detalle ADD COLUMN IF NOT EXISTS cantidad_recibida NUMERIC(14,4) DEFAULT 0")
    op.execute("""
        CREATE TABLE IF NOT EXISTS devoluciones (
            id              SERIAL PRIMARY KEY,
            folio           TEXT NOT NULL,
            cotizacion_id   INTEGER REFERENCES cotizaciones(id),
            cliente_id      INTEGER REFERENCES clientes(id),
            fecha           DATE NOT NULL,
            motivo          TEXT,
            estado          TEXT DEFAULT 'Abierta',
            total           NUMERIC(14,2) DEFAULT 0,
            notas           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS devolucion_detalle (
            id              SERIAL PRIMARY KEY,
            devolucion_id   INTEGER NOT NULL REFERENCES devoluciones(id) ON DELETE CASCADE,
            producto_id     INTEGER NOT NULL REFERENCES productos(id),
            cantidad        NUMERIC(14,4) NOT NULL,
            precio_unitario NUMERIC(14,4) NOT NULL,
            total           NUMERIC(14,2) NOT NULL,
            retorna_stock   BOOLEAN DEFAULT TRUE
        )
    """)
    op.execute("ALTER TABLE productos ADD COLUMN IF NOT EXISTS maneja_lotes BOOLEAN DEFAULT FALSE")
    op.execute("""
        CREATE TABLE IF NOT EXISTS lotes (
            id                SERIAL PRIMARY KEY,
            producto_id       INTEGER NOT NULL REFERENCES productos(id),
            numero_lote       TEXT NOT NULL,
            fecha_vencimiento DATE,
            cantidad          NUMERIC(14,4) NOT NULL DEFAULT 0,
            fecha_entrada     DATE,
            notas             TEXT,
            created_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS traslados (
            id              SERIAL PRIMARY KEY,
            cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id),
            origen          TEXT,
            destino         TEXT,
            transportista   TEXT,
            placas          TEXT,
            fecha_traslado  DATE,
            notas           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE crm_secuencia_inscripciones ADD COLUMN IF NOT EXISTS origen TEXT")
    op.execute("""
        CREATE TABLE IF NOT EXISTS prospectos (
            id                     SERIAL PRIMARY KEY,
            nombre                 TEXT NOT NULL,
            cliente_id             INTEGER REFERENCES clientes(id),
            contacto_nombre        TEXT,
            contacto_email         TEXT,
            contacto_tel           TEXT,
            etapa                  TEXT NOT NULL DEFAULT 'nuevo',
            valor_estimado         NUMERIC(14,2),
            probabilidad           INTEGER DEFAULT 0,
            responsable_id         INTEGER REFERENCES usuarios(id),
            notas                  TEXT,
            fecha_estimada_cierre  DATE,
            motivo_perdida         TEXT,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_prospectos_etapa ON prospectos(etapa)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS cuentas_por_pagar (
            id                SERIAL PRIMARY KEY,
            compra_id         INTEGER REFERENCES compras(id),
            proveedor_id      INTEGER NOT NULL REFERENCES proveedores(id),
            monto_total       NUMERIC(14,2) NOT NULL,
            monto_pagado      NUMERIC(14,2) DEFAULT 0,
            fecha_vencimiento DATE,
            estado            TEXT DEFAULT 'Pendiente',
            referencia_pago   TEXT,
            notas             TEXT,
            created_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cxp_proveedor ON cuentas_por_pagar(proveedor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cxp_estado ON cuentas_por_pagar(estado)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS crm_campana_atribuciones (
            id               SERIAL PRIMARY KEY,
            campana_id       INTEGER NOT NULL REFERENCES crm_campanas(id) ON DELETE CASCADE,
            cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
            cotizacion_id    INTEGER NOT NULL REFERENCES cotizaciones(id),
            monto            NUMERIC(14,2) NOT NULL,
            dias_desde_envio INTEGER,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(campana_id, cotizacion_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_crm_attr_campana ON crm_campana_atribuciones(campana_id)")


def downgrade() -> None:
    # Downgrade elimina en orden inverso solo los objetos creados por esta migración.
    # ALTER TABLE ... DROP COLUMN IF EXISTS y DROP TABLE IF EXISTS son seguros.
    op.execute("DROP INDEX IF EXISTS idx_crm_attr_campana")
    op.execute("DROP TABLE IF EXISTS crm_campana_atribuciones")
    op.execute("DROP INDEX IF EXISTS idx_cxp_estado")
    op.execute("DROP INDEX IF EXISTS idx_cxp_proveedor")
    op.execute("DROP TABLE IF EXISTS cuentas_por_pagar")
    op.execute("DROP INDEX IF EXISTS idx_prospectos_etapa")
    op.execute("DROP TABLE IF EXISTS prospectos")
    op.execute("DROP TABLE IF EXISTS traslados")
    op.execute("DROP TABLE IF EXISTS lotes")
    op.execute("DROP TABLE IF EXISTS devolucion_detalle")
    op.execute("DROP TABLE IF EXISTS devoluciones")
    op.execute("DROP INDEX IF EXISTS idx_pagos_cotizacion")
    op.execute("DROP TABLE IF EXISTS pagos")
    op.execute("DROP TABLE IF EXISTS costos_fijos")
    op.execute("DROP TABLE IF EXISTS estudio_aplicaciones")
    op.execute("DROP TABLE IF EXISTS compra_detalle_cotizacion")
    op.execute("DROP TABLE IF EXISTS compradores")
