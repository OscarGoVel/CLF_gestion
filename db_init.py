#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_init.py — Inicialización de base de datos
Función centralizada que crea todas las tablas y relaciones del sistema.
Usada por main.py al arrancar y por selector_empresa.py al crear una empresa nueva.
"""

import sqlite3


def inicializar_bd(db_path):
    """
    Crea todas las tablas, índices y datos por defecto en la BD indicada.
    Es idempotente: usa CREATE TABLE IF NOT EXISTS, seguro de llamar múltiples veces.

    Args:
        db_path: ruta al archivo .db (se crea si no existe)

    Returns:
        (conn, cursor) — conexión abierta lista para usar
    """
    conn   = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ── Catálogos base ────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_comercial TEXT NOT NULL,
            razon_social     TEXT,
            tipo             TEXT NOT NULL,
            rfc              TEXT,
            direccion        TEXT,
            contacto         TEXT,
            telefono         TEXT,
            email            TEXT,
            fecha_registro   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subcategorias (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria_id INTEGER,
            nombre       TEXT NOT NULL,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS corporativos (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre         TEXT NOT NULL,
            razon_social   TEXT,
            rfc            TEXT,
            direccion      TEXT,
            contacto       TEXT,
            telefono       TEXT,
            email          TEXT,
            notas          TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metodos_pago (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT UNIQUE NOT NULL,
            descripcion TEXT,
            activo      INTEGER DEFAULT 1
        )
    ''')

    # Métodos de pago por defecto
    for nombre, desc in [
        ('Efectivo',       'Pago en efectivo'),
        ('Transferencia',  'Transferencia bancaria'),
        ('Tarjeta Débito', 'Tarjeta de débito'),
        ('Tarjeta Crédito','Tarjeta de crédito'),
        ('Cheque',         'Pago con cheque'),
    ]:
        try:
            cursor.execute(
                'INSERT INTO metodos_pago (nombre, descripcion) VALUES (?, ?)',
                (nombre, desc))
        except sqlite3.IntegrityError:
            pass

    # ── Productos ─────────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT UNIQUE NOT NULL,
            nombre           TEXT NOT NULL,
            descripcion      TEXT,
            categoria_id     INTEGER,
            subcategoria_id  INTEGER,
            unidad_medida    TEXT,
            precio_base      REAL NOT NULL,
            aplica_iva       INTEGER DEFAULT 1,
            precio_venta     REAL,
            stock_actual     REAL DEFAULT 0,
            stock_minimo     REAL DEFAULT 0,
            clave_sat        TEXT,
            clave_unidad_sat TEXT,
            precio_base_fecha TEXT,
            fecha_registro   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id)    REFERENCES categorias(id),
            FOREIGN KEY (subcategoria_id) REFERENCES subcategorias(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS producto_proveedor (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id  INTEGER NOT NULL,
            proveedor_id INTEGER NOT NULL,
            es_principal INTEGER DEFAULT 0,
            notas        TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id)  REFERENCES productos(id),
            FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
            UNIQUE(producto_id, proveedor_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS producto_claves_sat (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id    INTEGER NOT NULL,
            clave_sat      TEXT NOT NULL,
            fuente         TEXT DEFAULT 'xml_import',
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id),
            UNIQUE(producto_id, clave_sat)
        )
    ''')

    # ── Cotizaciones ──────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cotizaciones (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            folio             TEXT UNIQUE NOT NULL,
            fecha             DATE NOT NULL,
            cliente_id        INTEGER NOT NULL,
            subtotal          REAL DEFAULT 0,
            iva               REAL DEFAULT 0,
            total             REAL DEFAULT 0,
            notas             TEXT,
            estado            TEXT DEFAULT 'Pendiente',
            orden_compra      TEXT,
            fecha_orden_compra DATE,
            fecha_entrega     DATE,
            fecha_factura     DATE,
            fecha_pago        DATE,
            monto_entregado   REAL DEFAULT 0,
            monto_facturado   REAL DEFAULT 0,
            monto_pagado      REAL DEFAULT 0,
            numero_factura    TEXT,
            entrega_parcial   INTEGER DEFAULT 0,
            oc_documento      TEXT,
            factura_documento TEXT,
            observaciones     TEXT,
            fecha_registro    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cotizacion_detalle (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id   INTEGER NOT NULL,
            producto_id     INTEGER NOT NULL,
            cantidad        REAL NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal        REAL NOT NULL,
            iva             REAL DEFAULT 0,
            total           REAL NOT NULL,
            costo_snapshot  REAL,
            tiene_stock     INTEGER DEFAULT 1,
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id),
            FOREIGN KEY (producto_id)   REFERENCES productos(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seguimiento_etapas (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id INTEGER NOT NULL,
            etapa         TEXT NOT NULL,
            completada    INTEGER DEFAULT 0,
            referencia    TEXT,
            fecha_etapa   DATE,
            notas         TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(cotizacion_id, etapa),
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documentos_cotizacion (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id  INTEGER NOT NULL,
            tipo           TEXT NOT NULL,
            nombre_archivo TEXT NOT NULL,
            ruta_archivo   TEXT NOT NULL,
            notas          TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entregas_parciales (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id     INTEGER NOT NULL,
            producto_id       INTEGER NOT NULL,
            cantidad_entregada REAL NOT NULL,
            fecha_entrega     DATE NOT NULL,
            notas             TEXT,
            usuario           TEXT,
            fecha_registro    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id),
            FOREIGN KEY (producto_id)   REFERENCES productos(id)
        )
    ''')

    # ── Compras ───────────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            folio            TEXT UNIQUE NOT NULL,
            proveedor_id     INTEGER,
            fecha_compra     DATETIME NOT NULL,
            subtotal         REAL DEFAULT 0,
            iva              REAL DEFAULT 0,
            total            REAL DEFAULT 0,
            metodo_pago_id   INTEGER,
            notas            TEXT,
            ticket_referencia TEXT,
            cotizacion_id    INTEGER,
            factura_xml_id   INTEGER,
            fecha_registro   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proveedor_id)   REFERENCES proveedores(id),
            FOREIGN KEY (metodo_pago_id) REFERENCES metodos_pago(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compra_detalle (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id      INTEGER NOT NULL,
            producto_id    INTEGER NOT NULL,
            cantidad       REAL NOT NULL,
            costo_unitario REAL NOT NULL,
            costo_total    REAL NOT NULL,
            FOREIGN KEY (compra_id)  REFERENCES compras(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')

    # ── Stock ─────────────────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos_stock (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id   INTEGER NOT NULL,
            tipo          TEXT NOT NULL,
            motivo        TEXT,
            cantidad      REAL NOT NULL,
            stock_antes   REAL NOT NULL,
            stock_despues REAL NOT NULL,
            referencia    TEXT,
            notas         TEXT,
            fecha         DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')

    # ── Facturas (CFDI) ───────────────────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            cotizacion_id    INTEGER,
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
            subtotal         REAL DEFAULT 0,
            descuento        REAL DEFAULT 0,
            iva              REAL DEFAULT 0,
            total            REAL DEFAULT 0,
            ruta_xml         TEXT,
            notas            TEXT,
            fecha_registro   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factura_conceptos (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id        INTEGER NOT NULL,
            clave_prod_serv   TEXT,
            no_identificacion TEXT,
            cantidad          REAL,
            clave_unidad      TEXT,
            unidad            TEXT,
            descripcion       TEXT,
            valor_unitario    REAL,
            importe           REAL,
            descuento         REAL DEFAULT 0,
            FOREIGN KEY (factura_id) REFERENCES facturas(id)
        )
    ''')

    # ── Junction tables (many-to-many) ────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS factura_cotizaciones (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id    INTEGER NOT NULL,
            cotizacion_id INTEGER NOT NULL,
            fecha_vinculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (factura_id)    REFERENCES facturas(id),
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id),
            UNIQUE(factura_id, cotizacion_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordenes_compra (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            numero         TEXT,
            cliente_id     INTEGER,
            fecha          TEXT,
            monto_total    REAL DEFAULT 0,
            documento      TEXT,
            notas          TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oc_cotizaciones (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            oc_id         INTEGER NOT NULL,
            cotizacion_id INTEGER NOT NULL,
            fecha_vinculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (oc_id)         REFERENCES ordenes_compra(id),
            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id),
            UNIQUE(oc_id, cotizacion_id)
        )
    ''')

    # ── Asignación de costos de compra a cotizaciones ────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS compra_detalle_cotizacion (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_detalle_id INTEGER NOT NULL,
            cotizacion_id     INTEGER,
            cantidad          REAL    NOT NULL,
            notas             TEXT,
            fecha_registro    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (compra_detalle_id) REFERENCES compra_detalle(id),
            FOREIGN KEY (cotizacion_id)     REFERENCES cotizaciones(id)
        )
    ''')

    # ── Backfill factura_cotizaciones desde facturas.cotizacion_id ──────────────
    cursor.execute('''
        INSERT OR IGNORE INTO factura_cotizaciones (factura_id, cotizacion_id)
        SELECT id, cotizacion_id FROM facturas
        WHERE cotizacion_id IS NOT NULL
    ''')

    # ── Historial de precios de productos ────────────────────────────────────────
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS producto_precio_historial (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            precio      REAL    NOT NULL,
            fecha       TEXT    NOT NULL,
            motivo      TEXT,
            fuente      TEXT DEFAULT 'manual',
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')

    # ── Migraciones columnas faltantes ───────────────────────────────────────────
    for tabla, cols in [
        ('cotizacion_detalle', [('costo_snapshot', 'REAL')]),
        ('compras',            [('cotizacion_id',  'INTEGER'),
                                ('factura_xml_id', 'INTEGER')]),
    ]:
        for col, tipo in cols:
            try:
                cursor.execute(f'ALTER TABLE {tabla} ADD COLUMN {col} {tipo}')
            except Exception:
                pass

    # ── Migraciones SAT en clientes y proveedores ─────────────────────────────────
    for tabla, cols in [
        ('clientes',    [('regimen_fiscal','TEXT'), ('uso_cfdi','TEXT'), ('cp_fiscal','TEXT'),
                         ('corporativo_id','INTEGER')]),
        ('proveedores', [('regimen_fiscal','TEXT'), ('cp_fiscal','TEXT')]),
    ]:
        for col, tipo in cols:
            try:
                cursor.execute(f'ALTER TABLE {tabla} ADD COLUMN {col} {tipo}')
            except sqlite3.OperationalError:
                pass  # Ya existe

    conn.commit()
    return conn, cursor


if __name__ == '__main__':
    # Prueba rápida
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        ruta = f.name
    conn, cursor = inicializar_bd(ruta)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tablas = [r[0] for r in cursor.fetchall()]
    print(f'✅ BD creada con {len(tablas)} tablas:')
    for t in tablas:
        print(f'   {t}')
    conn.close()
    os.unlink(ruta)
