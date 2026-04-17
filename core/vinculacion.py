# -*- coding: utf-8 -*-
"""
core/vinculacion.py
Lógica pura de detección de pendientes de vinculación CFDI.
Sin dependencias de UI ni de frameworks web.
Compatible con cursores SQLite (desktop) y el cursor adaptador de db_connection.py.
"""

# RFC propio — se excluye de detección de proveedores y clientes
CLF_RFC = 'CLF240418U94'


def detectar_pendientes(cursor):
    """Escanea facturas y retorna dict de pendientes por categoría."""
    pendientes = {
        "clientes":    [],
        "proveedores": [],
        "productos":   [],
        "cotizaciones": [],
    }

    # Clientes: RFC receptor no registrado en catálogo de clientes
    cursor.execute("""
        SELECT DISTINCT f.id, f.uuid, f.rfc_receptor, f.nombre_receptor
        FROM facturas f
        WHERE f.rfc_receptor IS NOT NULL AND f.rfc_receptor != ''
          AND UPPER(f.rfc_receptor) != UPPER(?)
          AND NOT EXISTS (
              SELECT 1 FROM clientes c
              WHERE c.rfc IS NOT NULL AND c.rfc != ''
                AND UPPER(c.rfc) = UPPER(f.rfc_receptor)
          )
    """, (CLF_RFC,))
    pendientes["clientes"] = cursor.fetchall()

    # Proveedores: RFC emisor no registrado, excluyendo RFC propio
    cursor.execute("""
        SELECT DISTINCT f.id, f.uuid, f.rfc_emisor, f.nombre_emisor
        FROM facturas f
        WHERE f.rfc_emisor IS NOT NULL AND f.rfc_emisor != ''
          AND UPPER(f.rfc_emisor) != UPPER(?)
          AND NOT EXISTS (
              SELECT 1 FROM proveedores p
              WHERE p.rfc IS NOT NULL AND p.rfc != ''
                AND UPPER(p.rfc) = UPPER(f.rfc_emisor)
          )
    """, (CLF_RFC,))
    pendientes["proveedores"] = cursor.fetchall()

    # Productos sin vincular por código o clave SAT
    cursor.execute("""
        SELECT MIN(fc.factura_id),
               MIN(f.uuid),
               MAX(fc.no_identificacion)  AS no_id,
               MAX(fc.descripcion)        AS descripcion,
               MAX(fc.clave_prod_serv)    AS clave_prod_serv
        FROM factura_conceptos fc
        JOIN facturas f ON f.id = fc.factura_id
        WHERE (
            (fc.no_identificacion IS NOT NULL AND fc.no_identificacion != '')
            OR
            (fc.clave_prod_serv IS NOT NULL AND fc.clave_prod_serv != '')
        )
          AND NOT EXISTS (
              SELECT 1 FROM productos p
              WHERE fc.no_identificacion IS NOT NULL AND fc.no_identificacion != ''
                AND UPPER(p.codigo) = UPPER(fc.no_identificacion)
          )
          AND NOT EXISTS (
              SELECT 1 FROM producto_claves_sat pcs
              WHERE fc.clave_prod_serv IS NOT NULL AND fc.clave_prod_serv != ''
                AND UPPER(pcs.clave_sat) = UPPER(fc.clave_prod_serv)
          )
        GROUP BY UPPER(COALESCE(NULLIF(fc.no_identificacion,''), fc.clave_prod_serv))
    """)
    pendientes["productos"] = cursor.fetchall()

    # Facturas de VENTA sin cotización vinculada (CLF es el emisor)
    cursor.execute("""
        SELECT f.id, f.uuid, f.total, f.rfc_receptor, f.fecha,
               'venta' AS tipo_fac, f.nombre_receptor
        FROM facturas f
        WHERE UPPER(f.rfc_emisor) = UPPER(?)
          AND NOT EXISTS (
              SELECT 1 FROM factura_cotizaciones fc WHERE fc.factura_id = f.id
          )
    """, (CLF_RFC,))
    ventas_sin_cot = cursor.fetchall()

    # Facturas de COMPRA sin registro en compras (CLF es el receptor)
    cursor.execute("""
        SELECT f.id, f.uuid, f.total, f.rfc_emisor, f.fecha,
               'compra' AS tipo_fac, f.nombre_emisor
        FROM facturas f
        WHERE UPPER(f.rfc_receptor) = UPPER(?)
          AND NOT EXISTS (
              SELECT 1 FROM compras c WHERE c.factura_xml_id = f.id
          )
    """, (CLF_RFC,))
    compras_sin_reg = cursor.fetchall()

    pendientes["cotizaciones"] = ventas_sin_cot + compras_sin_reg
    return pendientes


def cargar_clientes(cursor):
    cursor.execute("""
        SELECT id, nombre_comercial, razon_social, rfc, tipo,
               regimen_fiscal, uso_cfdi, cp_fiscal, contacto, email
        FROM clientes ORDER BY nombre_comercial
    """)
    return cursor.fetchall()


def cargar_proveedores(cursor):
    cursor.execute("""
        SELECT id, nombre, razon_social, rfc,
               regimen_fiscal, cp_fiscal, contacto, email
        FROM proveedores ORDER BY nombre
    """)
    return cursor.fetchall()


def cargar_productos(cursor):
    cursor.execute("""
        SELECT id, codigo, nombre, precio_venta, unidad_medida, clave_sat
        FROM productos ORDER BY nombre
    """)
    return cursor.fetchall()


def cargar_cotizaciones(cursor, factura_id):
    cursor.execute("""
        SELECT c.id, c.folio, c.fecha, cl.nombre_comercial, cl.rfc,
               c.total, c.estado, c.monto_entregado
        FROM cotizaciones c
        JOIN clientes cl ON cl.id = c.cliente_id
        WHERE c.estado NOT IN ('Cancelada')
          AND c.id NOT IN (
              SELECT fc.cotizacion_id
              FROM factura_cotizaciones fc
              JOIN facturas f ON f.id = fc.factura_id
              WHERE fc.factura_id != ?
                AND f.tipo = (SELECT tipo FROM facturas WHERE id = ?)
          )
        ORDER BY c.folio DESC
    """, (factura_id, factura_id))
    return cursor.fetchall()
