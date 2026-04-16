#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_schema.py
Crea el esquema PostgreSQL equivalente al de SQLite (db_init.py).
Es idempotente — seguro de ejecutar múltiples veces (CREATE TABLE IF NOT EXISTS).

Ejecución:
    python migrate_schema.py

Requiere que config.json tenga las credenciales PostgreSQL correctas.
"""

import sys
import psycopg2
import json
import os
import traceback

_BASE = os.path.dirname(os.path.abspath(__file__))

def _cfg():
    path = os.path.join(_BASE, 'config.json')
    for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise RuntimeError("No se pudo leer config.json con ninguna codificación conocida.")

def _conectar(dbname):
    cfg = _cfg()['postgresql']
    # Evitar que libpq lea pgpass.conf (puede tener encoding Windows-1252)
    os.environ['PGPASSWORD'] = cfg['password']
    os.environ['PGPASSFILE'] = os.devnull
    return psycopg2.connect(
        host=cfg['host'], port=cfg.get('port', 5432),
        dbname=dbname, user=cfg['user'], password=cfg['password']
    )

# ─────────────────────────────────────────────────────────────────────────────
# ESQUEMA DE EMPRESA  (clf_empresa)
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_EMPRESA = """

-- Catálogos base
CREATE TABLE IF NOT EXISTS clientes (
    id               SERIAL PRIMARY KEY,
    nombre_comercial TEXT NOT NULL,
    razon_social     TEXT,
    tipo             TEXT NOT NULL,
    rfc              TEXT,
    direccion        TEXT,
    contacto         TEXT,
    telefono         TEXT,
    email            TEXT,
    regimen_fiscal   TEXT,
    uso_cfdi         TEXT,
    cp_fiscal        TEXT,
    corporativo_id   INTEGER,
    fecha_registro   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS categorias (
    id     SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subcategorias (
    id           SERIAL PRIMARY KEY,
    categoria_id INTEGER REFERENCES categorias(id),
    nombre       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS corporativos (
    id     SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS proveedores (
    id             SERIAL PRIMARY KEY,
    nombre         TEXT NOT NULL,
    razon_social   TEXT,
    rfc            TEXT,
    direccion      TEXT,
    contacto       TEXT,
    telefono       TEXT,
    email          TEXT,
    notas          TEXT,
    regimen_fiscal TEXT,
    cp_fiscal      TEXT,
    uso_cfdi       TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS metodos_pago (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT UNIQUE NOT NULL,
    descripcion TEXT,
    activo      INTEGER DEFAULT 1
);

-- Productos
CREATE TABLE IF NOT EXISTS productos (
    id                SERIAL PRIMARY KEY,
    codigo            TEXT UNIQUE NOT NULL,
    nombre            TEXT NOT NULL,
    descripcion       TEXT,
    categoria_id      INTEGER REFERENCES categorias(id),
    subcategoria_id   INTEGER REFERENCES subcategorias(id),
    unidad_medida     TEXT,
    precio_base       NUMERIC(14,4) NOT NULL,
    aplica_iva        INTEGER DEFAULT 1,
    precio_venta      NUMERIC(14,4),
    stock_actual      NUMERIC(14,4) DEFAULT 0,
    stock_minimo      NUMERIC(14,4) DEFAULT 0,
    clave_sat         TEXT,
    clave_unidad_sat  TEXT,
    precio_base_fecha TEXT,
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS producto_proveedor (
    id             SERIAL PRIMARY KEY,
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    proveedor_id   INTEGER NOT NULL REFERENCES proveedores(id),
    es_principal   INTEGER DEFAULT 0,
    notas          TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(producto_id, proveedor_id)
);

CREATE TABLE IF NOT EXISTS producto_claves_sat (
    id             SERIAL PRIMARY KEY,
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    clave_sat      TEXT NOT NULL,
    fuente         TEXT DEFAULT 'xml_import',
    fecha_registro TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(producto_id, clave_sat)
);

-- Cotizaciones
CREATE TABLE IF NOT EXISTS cotizaciones (
    id                SERIAL PRIMARY KEY,
    folio             TEXT UNIQUE NOT NULL,
    fecha             DATE NOT NULL,
    cliente_id        INTEGER NOT NULL REFERENCES clientes(id),
    subtotal          NUMERIC(14,4) DEFAULT 0,
    iva               NUMERIC(14,4) DEFAULT 0,
    total             NUMERIC(14,4) DEFAULT 0,
    notas             TEXT,
    estado            TEXT DEFAULT 'Pendiente',
    orden_compra      TEXT,
    fecha_orden_compra DATE,
    fecha_entrega     DATE,
    fecha_factura     DATE,
    fecha_pago        DATE,
    monto_entregado   NUMERIC(14,4) DEFAULT 0,
    monto_facturado   NUMERIC(14,4) DEFAULT 0,
    monto_pagado      NUMERIC(14,4) DEFAULT 0,
    numero_factura    TEXT,
    entrega_parcial   INTEGER DEFAULT 0,
    oc_documento      TEXT,
    factura_documento TEXT,
    observaciones     TEXT,
    aplica_iva        INTEGER DEFAULT 0,
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cotizacion_detalle (
    id              SERIAL PRIMARY KEY,
    cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id),
    producto_id     INTEGER NOT NULL REFERENCES productos(id),
    cantidad        NUMERIC(14,4) NOT NULL,
    precio_unitario NUMERIC(14,4) NOT NULL,
    subtotal        NUMERIC(14,4) NOT NULL,
    iva             NUMERIC(14,4) DEFAULT 0,
    total           NUMERIC(14,4) NOT NULL,
    costo_snapshot  NUMERIC(14,4),
    tiene_stock     INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS seguimiento_etapas (
    id             SERIAL PRIMARY KEY,
    cotizacion_id  INTEGER NOT NULL REFERENCES cotizaciones(id),
    etapa          TEXT NOT NULL,
    completada     INTEGER DEFAULT 0,
    referencia     TEXT,
    fecha_etapa    DATE,
    notas          TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cotizacion_id, etapa)
);

CREATE TABLE IF NOT EXISTS documentos_cotizacion (
    id             SERIAL PRIMARY KEY,
    cotizacion_id  INTEGER NOT NULL REFERENCES cotizaciones(id),
    tipo           TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo   TEXT NOT NULL,
    notas          TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entregas_parciales (
    id                 SERIAL PRIMARY KEY,
    cotizacion_id      INTEGER NOT NULL REFERENCES cotizaciones(id),
    producto_id        INTEGER NOT NULL REFERENCES productos(id),
    cantidad_entregada NUMERIC(14,4) NOT NULL,
    fecha_entrega      DATE NOT NULL,
    notas              TEXT,
    usuario            TEXT,
    fecha_registro     TIMESTAMPTZ DEFAULT NOW()
);

-- Compras
CREATE TABLE IF NOT EXISTS compras (
    id                SERIAL PRIMARY KEY,
    folio             TEXT UNIQUE NOT NULL,
    proveedor_id      INTEGER REFERENCES proveedores(id),
    fecha_compra      TIMESTAMPTZ NOT NULL,
    subtotal          NUMERIC(14,4) DEFAULT 0,
    iva               NUMERIC(14,4) DEFAULT 0,
    total             NUMERIC(14,4) DEFAULT 0,
    metodo_pago_id    INTEGER REFERENCES metodos_pago(id),
    notas             TEXT,
    ticket_referencia TEXT,
    cotizacion_id     INTEGER,
    factura_xml_id    INTEGER,
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS compra_detalle (
    id             SERIAL PRIMARY KEY,
    compra_id      INTEGER NOT NULL REFERENCES compras(id),
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    cantidad       NUMERIC(14,4) NOT NULL,
    costo_unitario NUMERIC(14,4) NOT NULL,
    costo_total    NUMERIC(14,4) NOT NULL
);

-- Stock
CREATE TABLE IF NOT EXISTS movimientos_stock (
    id            SERIAL PRIMARY KEY,
    producto_id   INTEGER NOT NULL REFERENCES productos(id),
    tipo          TEXT NOT NULL,
    motivo        TEXT,
    cantidad      NUMERIC(14,4) NOT NULL,
    stock_antes   NUMERIC(14,4) NOT NULL,
    stock_despues NUMERIC(14,4) NOT NULL,
    referencia    TEXT,
    notas         TEXT,
    usuario       TEXT,
    fecha         TIMESTAMPTZ DEFAULT NOW()
);

-- Facturas CFDI
CREATE TABLE IF NOT EXISTS facturas (
    id               SERIAL PRIMARY KEY,
    cotizacion_id    INTEGER REFERENCES cotizaciones(id),
    uuid             TEXT UNIQUE NOT NULL,
    serie            TEXT,
    folio_factura    TEXT,
    fecha            TEXT,
    fecha_timbrado   TEXT,
    no_cert_sat      TEXT,
    rfc_emisor       TEXT,
    nombre_emisor    TEXT,
    rfc_receptor     TEXT,
    nombre_receptor  TEXT,
    uso_cfdi         TEXT,
    tipo             TEXT,
    metodo_pago      TEXT,
    forma_pago       TEXT,
    moneda           TEXT DEFAULT 'MXN',
    subtotal         NUMERIC(14,4) DEFAULT 0,
    descuento        NUMERIC(14,4) DEFAULT 0,
    iva              NUMERIC(14,4) DEFAULT 0,
    total            NUMERIC(14,4) DEFAULT 0,
    ruta_xml         TEXT,
    notas            TEXT,
    fecha_registro   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS factura_conceptos (
    id                SERIAL PRIMARY KEY,
    factura_id        INTEGER NOT NULL REFERENCES facturas(id),
    clave_prod_serv   TEXT,
    no_identificacion TEXT,
    cantidad          NUMERIC(14,4),
    clave_unidad      TEXT,
    unidad            TEXT,
    descripcion       TEXT,
    valor_unitario    NUMERIC(14,4),
    importe           NUMERIC(14,4),
    descuento         NUMERIC(14,4) DEFAULT 0
);

-- Tablas de relación (many-to-many)
CREATE TABLE IF NOT EXISTS factura_cotizaciones (
    id            SERIAL PRIMARY KEY,
    factura_id    INTEGER NOT NULL REFERENCES facturas(id),
    cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id),
    fecha_vinculo TIMESTAMPTZ DEFAULT NOW(),
    notas         TEXT,
    UNIQUE(factura_id, cotizacion_id)
);

CREATE TABLE IF NOT EXISTS ordenes_compra (
    id             SERIAL PRIMARY KEY,
    numero         TEXT,
    cliente_id     INTEGER REFERENCES clientes(id),
    fecha          TEXT,
    monto_total    NUMERIC(14,4) DEFAULT 0,
    documento      TEXT,
    notas          TEXT,
    fecha_registro TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS oc_cotizaciones (
    id            SERIAL PRIMARY KEY,
    oc_id         INTEGER NOT NULL REFERENCES ordenes_compra(id),
    cotizacion_id INTEGER NOT NULL REFERENCES cotizaciones(id),
    fecha_vinculo TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(oc_id, cotizacion_id)
);

CREATE TABLE IF NOT EXISTS compra_detalle_cotizacion (
    id                SERIAL PRIMARY KEY,
    compra_detalle_id INTEGER NOT NULL REFERENCES compra_detalle(id),
    cotizacion_id     INTEGER REFERENCES cotizaciones(id),
    cantidad          NUMERIC(14,4) NOT NULL,
    notas             TEXT,
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
);

-- Historial de precios
CREATE TABLE IF NOT EXISTS producto_precio_historial (
    id             SERIAL PRIMARY KEY,
    producto_id    INTEGER NOT NULL REFERENCES productos(id),
    precio         NUMERIC(14,4) NOT NULL,
    fecha          TEXT NOT NULL,
    motivo         TEXT,
    fuente         TEXT DEFAULT 'manual',
    fecha_registro TIMESTAMPTZ DEFAULT NOW()
);

-- Usuarios (copia local por empresa, no confundir con clf_usuarios)
CREATE TABLE IF NOT EXISTS usuarios (
    id             SERIAL PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    nombre         TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    salt           TEXT,
    rol            TEXT NOT NULL DEFAULT 'Operador',
    activo         INTEGER NOT NULL DEFAULT 1,
    fecha_creacion TIMESTAMPTZ DEFAULT NOW(),
    ultimo_acceso  TIMESTAMPTZ
);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS salt TEXT;
ALTER TABLE producto_precio_historial ADD COLUMN IF NOT EXISTS proveedor_id INTEGER REFERENCES proveedores(id);
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE;
ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS utilidad_pct NUMERIC(6,2) DEFAULT 0;
CREATE TABLE IF NOT EXISTS compra_detalle_cotizacion (
    id                SERIAL PRIMARY KEY,
    compra_detalle_id INTEGER NOT NULL REFERENCES compra_detalle(id),
    cotizacion_id     INTEGER REFERENCES cotizaciones(id),
    cantidad          NUMERIC(14,4) NOT NULL,
    notas             TEXT,
    fecha_registro    TIMESTAMPTZ DEFAULT NOW()
);
"""

# ─────────────────────────────────────────────────────────────────────────────
# ESQUEMA DE USUARIOS  (clf_usuarios)
# ─────────────────────────────────────────────────────────────────────────────

SCHEMA_USUARIOS = """
CREATE TABLE IF NOT EXISTS usuarios (
    id             SERIAL PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    nombre         TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    salt           TEXT,
    rol            TEXT NOT NULL DEFAULT 'Operador',
    activo         INTEGER NOT NULL DEFAULT 1,
    fecha_creacion TIMESTAMPTZ DEFAULT NOW(),
    ultimo_acceso  TIMESTAMPTZ
);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS salt TEXT;

CREATE TABLE IF NOT EXISTS preferencias_usuario (
    usuario_id INTEGER NOT NULL,
    clave      TEXT    NOT NULL,
    valor      TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (usuario_id, clave)
);
"""

# Índices de rendimiento — seguros de ejecutar múltiples veces (IF NOT EXISTS)
INDICES_EMPRESA = """
-- Cotizaciones
CREATE INDEX IF NOT EXISTS idx_cot_estado        ON cotizaciones(estado);
CREATE INDEX IF NOT EXISTS idx_cot_fecha         ON cotizaciones(fecha);
CREATE INDEX IF NOT EXISTS idx_cot_fecha_entrega ON cotizaciones(fecha_entrega);
CREATE INDEX IF NOT EXISTS idx_cot_cliente       ON cotizaciones(cliente_id);
-- Facturas
CREATE INDEX IF NOT EXISTS idx_fac_uuid          ON facturas(uuid);
CREATE INDEX IF NOT EXISTS idx_fac_rfc_emisor    ON facturas(rfc_emisor);
CREATE INDEX IF NOT EXISTS idx_fac_rfc_receptor  ON facturas(rfc_receptor);
-- Productos
CREATE INDEX IF NOT EXISTS idx_prod_codigo       ON productos(codigo);
-- Detalle cotización y conceptos de factura
CREATE INDEX IF NOT EXISTS idx_cotdet_cotizacion ON cotizacion_detalle(cotizacion_id);
CREATE INDEX IF NOT EXISTS idx_facdet_factura    ON factura_conceptos(factura_id);
-- Movimientos de stock
CREATE INDEX IF NOT EXISTS idx_mov_producto      ON movimientos_stock(producto_id);
CREATE INDEX IF NOT EXISTS idx_mov_fecha         ON movimientos_stock(fecha);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Ejecución
# ─────────────────────────────────────────────────────────────────────────────

def crear_schema_empresa():
    cfg  = _cfg()
    pg   = cfg['postgresql']
    # Obtener el nombre de la BD de empresa desde la primera empresa configurada
    empresas = cfg.get('empresas', [])
    if not empresas:
        print("✗ No hay empresas configuradas en config.json")
        return False

    for emp in empresas:
        dbname = emp.get('pg_database')
        if not dbname:
            print(f"  ⚠ Empresa '{emp.get('nombre', '?')}' no tiene pg_database — omitida")
            continue

        print(f"\n→ Creando esquema empresa en BD: {dbname}")
        try:
            conn = _conectar(dbname)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(SCHEMA_EMPRESA)
            cur.execute(INDICES_EMPRESA)
            # Métodos de pago por defecto
            for nombre, desc in [
                ('Efectivo',        'Pago en efectivo'),
                ('Transferencia',   'Transferencia bancaria'),
                ('Tarjeta Débito',  'Tarjeta de débito'),
                ('Tarjeta Crédito', 'Tarjeta de crédito'),
                ('Cheque',          'Pago con cheque'),
            ]:
                cur.execute("""
                    INSERT INTO metodos_pago (nombre, descripcion)
                    VALUES (%s, %s)
                    ON CONFLICT (nombre) DO NOTHING
                """, (nombre, desc))
            conn.close()
            print(f"  ✓ Esquema creado en {dbname}")
        except Exception as e:
            msg = str(e)
            # La BD no existe en PostgreSQL todavía — advertencia, no fallo
            if 'does not exist' in msg or 'no existe' in msg.lower() or isinstance(e, UnicodeDecodeError):
                print(f"  ⚠ BD '{dbname}' no existe en PostgreSQL — créala en pgAdmin y vuelve a ejecutar")
            else:
                print(f"  ✗ Error en {dbname}: {e}")
                traceback.print_exc()
                return False

    return True


def crear_schema_usuarios():
    cfg    = _cfg()
    dbname = cfg['postgresql'].get('database_usuarios', 'clf_usuarios')
    print(f"\n→ Creando esquema usuarios en BD: {dbname}")
    try:
        conn = _conectar(dbname)
        conn.autocommit = True
        cur  = conn.cursor()
        cur.execute(SCHEMA_USUARIOS)
        conn.close()
        print(f"  ✓ Esquema creado en {dbname}")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 55)
    print("  migrate_schema.py — Creación de esquema PostgreSQL")
    print("=" * 55)

    ok_emp = crear_schema_empresa()
    ok_usr = crear_schema_usuarios()

    print()
    if ok_emp and ok_usr:
        print("✅ Esquemas creados correctamente.")
        print("   Siguiente paso: ejecuta  python migrate_data.py")
    else:
        print("✗ Hubo errores. Revisa la conexión y los permisos en PostgreSQL.")
        sys.exit(1)
