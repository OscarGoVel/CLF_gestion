#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_data.py
Migra todos los datos existentes de SQLite → PostgreSQL.

⚠  Ejecutar UNA SOLA VEZ, después del esquema ya creado (migrate_schema.py).
   El SQLite original NO se modifica — siempre hay rollback disponible.

Ejecución:
    python migrate_data.py

Al terminar muestra un reporte por tabla con filas migradas / errores.
"""

import sqlite3
import psycopg2
import json
import os
import sys
from datetime import datetime

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

def _conectar_pg(dbname):
    cfg = _cfg()['postgresql']
    os.environ['PGPASSWORD'] = cfg['password']
    os.environ['PGPASSFILE'] = os.devnull
    return psycopg2.connect(
        host=cfg['host'], port=cfg.get('port', 5432),
        dbname=dbname, user=cfg['user'], password=cfg['password']
    )

def _conectar_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Orden de tablas respetando Foreign Keys
# ─────────────────────────────────────────────────────────────────────────────

ORDEN_EMPRESA = [
    'categorias',
    'subcategorias',
    'corporativos',
    'proveedores',
    'metodos_pago',
    'clientes',
    'productos',
    'producto_proveedor',
    'producto_claves_sat',
    'cotizaciones',
    'cotizacion_detalle',
    'seguimiento_etapas',
    'documentos_cotizacion',
    'entregas_parciales',
    'compras',
    'compra_detalle',
    'movimientos_stock',
    'facturas',
    'factura_conceptos',
    'factura_cotizaciones',
    'ordenes_compra',
    'oc_cotizaciones',
    'compra_detalle_cotizacion',
    'producto_precio_historial',
    'usuarios',
]

ORDEN_USUARIOS = [
    'usuarios',
    'preferencias_usuario',
]


# ─────────────────────────────────────────────────────────────────────────────
# Migración genérica de una tabla
# ─────────────────────────────────────────────────────────────────────────────

def migrar_tabla(sqlite_conn, pg_conn, tabla):
    """
    Copia todas las filas de `tabla` desde SQLite a PostgreSQL.
    Usa los mismos IDs del origen (OVERRIDING SYSTEM VALUE para SERIAL).
    Devuelve (filas_migradas, errores).
    """
    sc = sqlite_conn.cursor()

    # Verificar que la tabla existe en SQLite
    sc.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,))
    if not sc.fetchone():
        return 0, 0   # tabla no existe en este SQLite, se omite silenciosamente

    sc.execute(f'SELECT * FROM {tabla}')
    filas = sc.fetchall()
    if not filas:
        return 0, 0

    columnas = [d[0] for d in sc.description]
    cols_str  = ', '.join(columnas)
    phold     = ', '.join(['%s'] * len(columnas))

    # Si hay columna 'id' usamos OVERRIDING SYSTEM VALUE para respetar IDs originales
    tiene_id = 'id' in columnas
    if tiene_id:
        insert_sql = (
            f'INSERT INTO {tabla} ({cols_str}) '
            f'OVERRIDING SYSTEM VALUE '
            f'VALUES ({phold}) '
            f'ON CONFLICT DO NOTHING'
        )
    else:
        insert_sql = (
            f'INSERT INTO {tabla} ({cols_str}) '
            f'VALUES ({phold}) '
            f'ON CONFLICT DO NOTHING'
        )

    pc  = pg_conn.cursor()
    ok  = 0
    err = 0

    for fila in filas:
        try:
            valores = [_sanitizar_valor(fila[c]) for c in columnas]
            pc.execute("SAVEPOINT sp_fila")
            pc.execute(insert_sql, valores)
            pc.execute("RELEASE SAVEPOINT sp_fila")
            ok += 1
        except Exception as e:
            pc.execute("ROLLBACK TO SAVEPOINT sp_fila")
            err += 1
            if err <= 3:   # Solo mostrar los primeros 3 errores por tabla
                print(f"      ⚠ Error en fila: {e}")

    return ok, err


def _sanitizar_valor(v):
    """Limpia valores que SQLite acepta pero PostgreSQL rechaza."""
    if not isinstance(v, str):
        return v
    # Fechas corruptas tipo '2026-0226' → intenta insertar None antes que abortar
    import re
    if re.match(r'^\d{4}-\d{2}\d{2}$', v):   # falta el segundo guión
        try:
            v = v[:7] + '-' + v[7:]           # '2026-0226' → '2026-02-26'
        except Exception:
            return None
    return v


def resetear_secuencias(pg_conn, tablas):
    """
    Actualiza las secuencias SERIAL al máximo ID actual para evitar
    conflictos al insertar nuevos registros después de la migración.
    """
    pc = pg_conn.cursor()
    for tabla in tablas:
        try:
            pc.execute(f"""
                SELECT setval(
                    pg_get_serial_sequence('{tabla}', 'id'),
                    COALESCE(MAX(id), 1)
                ) FROM {tabla}
            """)
        except Exception:
            pass   # Tabla sin columna 'id' o sin secuencia


# ─────────────────────────────────────────────────────────────────────────────
# Migración de empresa
# ─────────────────────────────────────────────────────────────────────────────

def migrar_empresa(emp):
    db_path   = emp.get('db_path')
    pg_db     = emp.get('pg_database')
    nombre    = emp.get('nombre', emp.get('id'))

    if not db_path or not os.path.exists(db_path):
        print(f"  ✗ No se encontró el archivo SQLite: {db_path}")
        return False
    if not pg_db:
        print(f"  ✗ Empresa '{nombre}' no tiene pg_database configurado.")
        return False

    print(f"\n{'─'*55}")
    print(f"  Empresa: {nombre}")
    print(f"  SQLite : {db_path}")
    print(f"  PG BD  : {pg_db}")
    print(f"{'─'*55}")

    sqlite_conn = _conectar_sqlite(db_path)
    try:
        pg_conn = _conectar_pg(pg_db)
    except Exception:
        print(f"  ⚠ BD '{pg_db}' no existe en PostgreSQL — créala en pgAdmin y vuelve a ejecutar.")
        sqlite_conn.close()
        return True   # No es error fatal, solo esta empresa se omite
    pg_conn.autocommit = False

    reporte = []
    total_ok = total_err = 0

    for tabla in ORDEN_EMPRESA:
        ok, err = migrar_tabla(sqlite_conn, pg_conn, tabla)
        if ok > 0 or err > 0:
            reporte.append((tabla, ok, err))
            total_ok  += ok
            total_err += err
            estado = "✓" if err == 0 else "⚠"
            print(f"  {estado}  {tabla:<35} {ok:>5} filas  {('/ '+str(err)+' errores') if err else ''}")

    pg_conn.commit()
    resetear_secuencias(pg_conn, ORDEN_EMPRESA)
    pg_conn.commit()

    if total_err == 0:
        print(f"\n  ✅ Migración completa — {total_ok} filas migradas.")
    else:
        print(f"\n  ⚠ Migración con advertencias — {total_ok} filas migradas, {total_err} filas omitidas.")
        print("    Las filas omitidas tenían datos inválidos (ver ⚠ arriba).")

    sqlite_conn.close()
    pg_conn.close()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Migración de usuarios
# ─────────────────────────────────────────────────────────────────────────────

def migrar_usuarios():
    cfg       = _cfg()
    users_db  = os.path.join(_BASE, 'app_usuarios.db')
    pg_db     = cfg['postgresql'].get('database_usuarios', 'clf_usuarios')

    print(f"\n{'─'*55}")
    print(f"  BD usuarios")
    print(f"  SQLite : {users_db}")
    print(f"  PG BD  : {pg_db}")
    print(f"{'─'*55}")

    if not os.path.exists(users_db):
        print("  ⚠ app_usuarios.db no existe — omitiendo.")
        return True

    sqlite_conn = _conectar_sqlite(users_db)
    pg_conn     = _conectar_pg(pg_db)
    pg_conn.autocommit = False

    total_ok = total_err = 0

    for tabla in ORDEN_USUARIOS:
        ok, err = migrar_tabla(sqlite_conn, pg_conn, tabla)
        if ok > 0 or err > 0:
            total_ok  += ok
            total_err += err
            estado = "✓" if err == 0 else "⚠"
            print(f"  {estado}  {tabla:<35} {ok:>5} filas  {('/ '+str(err)+' errores') if err else ''}")

    if total_err == 0:
        pg_conn.commit()
        print(f"\n  ✅ Commit realizado — {total_ok} filas migradas.")
        resetear_secuencias(pg_conn, ['usuarios'])
        pg_conn.commit()
    else:
        pg_conn.rollback()
        print(f"\n  ✗ Rollback — {total_err} errores. Datos NO migrados.")

    sqlite_conn.close()
    pg_conn.close()
    return total_err == 0


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    inicio = datetime.now()
    print("=" * 55)
    print("  migrate_data.py — Migración SQLite → PostgreSQL")
    print(f"  Inicio: {inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    cfg      = _cfg()
    empresas = cfg.get('empresas', [])
    errores  = []

    for emp in empresas:
        ok = migrar_empresa(emp)
        if not ok:
            errores.append(emp.get('nombre', emp.get('id')))

    ok_usr = migrar_usuarios()
    if not ok_usr:
        errores.append('BD Usuarios')

    fin = datetime.now()
    print(f"\n{'='*55}")
    print(f"  Fin: {fin.strftime('%H:%M:%S')}  |  Duración: {(fin-inicio).seconds}s")

    if not errores:
        print("  ✅ Migración completada sin errores.")
        print()
        print("  Siguiente paso:")
        print('  En config.json cambia  "motor": "sqlite"  →  "motor": "postgresql"')
        print("  y prueba la aplicación.")
    else:
        print(f"  ✗ Errores en: {', '.join(errores)}")
        print("    Revisa los mensajes anteriores y vuelve a ejecutar.")
        sys.exit(1)
