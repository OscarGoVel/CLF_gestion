#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_connection.py
Capa de abstracción de base de datos.
Soporta SQLite (legacy) y PostgreSQL (multi-usuario en red).
El motor activo se controla en config.json → "motor": "sqlite" | "postgresql"
"""

import os
import json

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG   = os.path.join(_BASE_DIR, 'config.json')
_USERS_DB = os.path.join(_BASE_DIR, 'app_usuarios.db')


def _cfg() -> dict:
    try:
        with open(_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def motor_activo() -> str:
    """Devuelve 'sqlite' o 'postgresql' según config.json."""
    return _cfg().get('motor', 'sqlite')


# Tablas sin columna 'id' (clave compuesta o sin PK serial)
_TABLAS_SIN_ID = {'preferencias_usuario', 'producto_proveedor', 'seguimiento_etapas',
                  'factura_cotizaciones', 'oc_cotizaciones', 'compra_detalle_cotizacion'}

def _sql_tiene_id(sql: str) -> bool:
    """Devuelve False si el INSERT es a una tabla conocida sin columna id."""
    import re
    m = re.search(r'INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)', sql, re.IGNORECASE)
    if m:
        return m.group(1).lower() not in _TABLAS_SIN_ID
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Adapter psycopg2 → interfaz sqlite3
# Hace que el código escrito para sqlite3 funcione con PostgreSQL sin cambios.
# ─────────────────────────────────────────────────────────────────────────────

class _PgCursor:
    """
    Wrapper de psycopg2.cursor compatible con sqlite3.Cursor:
      · Traduce placeholders  ?  →  %s  automáticamente
      · Expone lastrowid via RETURNING id en sentencias INSERT
      · Expone description, rowcount, fetchone / fetchall / fetchmany
    """

    def __init__(self, pg_cursor):
        self._c = pg_cursor
        self.lastrowid = None

    # ── ejecución ─────────────────────────────────────────────────────────

    def execute(self, sql: str, params=None):
        import re as _re
        # Traducir INSERT OR IGNORE INTO → INSERT INTO ... ON CONFLICT DO NOTHING
        was_ignore = bool(_re.search(r'INSERT\s+OR\s+IGNORE\s+INTO', sql, _re.IGNORECASE))
        if was_ignore:
            sql = _re.sub(
                r'INSERT\s+OR\s+IGNORE\s+INTO',
                'INSERT INTO',
                sql,
                flags=_re.IGNORECASE,
            )
        # Traducir GROUP_CONCAT → STRING_AGG
        # Caso 1: GROUP_CONCAT(DISTINCT col_simple) → STRING_AGG(DISTINCT col, ',')
        sql = _re.sub(
            r'GROUP_CONCAT\(\s*DISTINCT\s+([\w\.]+)\s*\)',
            r"STRING_AGG(DISTINCT \1, ',')",
            sql,
            flags=_re.IGNORECASE,
        )
        # Caso 2: GROUP_CONCAT(expr) o GROUP_CONCAT(expr, sep) → STRING_AGG(...)
        sql = _re.sub(r'GROUP_CONCAT\(', 'STRING_AGG(', sql, flags=_re.IGNORECASE)
        # Traducir strftime SQLite → TO_CHAR PostgreSQL
        # El formato SQLite usa % que psycopg2 interpreta como placeholder (IndexError)
        _STRFTIME_MAP = {
            '%Y-%m-%d': 'YYYY-MM-DD',
            '%Y-%m':    'YYYY-MM',
            '%Y':       'YYYY',
            '%m':       'MM',
            '%d':       'DD',
        }
        def _strftime_to_tochar(m):
            fmt_sqlite = m.group(1)   # ej. '%Y-%m'
            col        = m.group(2)   # ej. 'fecha_compra'
            fmt_pg = _STRFTIME_MAP.get(fmt_sqlite, fmt_sqlite.replace('%Y','YYYY')
                                                               .replace('%m','MM')
                                                               .replace('%d','DD'))
            return f"TO_CHAR({col}, '{fmt_pg}')"
        sql = _re.sub(
            r"strftime\(\s*'([^']+)'\s*,\s*([^)]+?)\s*\)",
            _strftime_to_tochar,
            sql,
            flags=_re.IGNORECASE,
        )
        sql = sql.replace('?', '%s')
        stripped   = sql.strip().upper()
        is_insert  = stripped.startswith('INSERT')
        has_return = 'RETURNING' in stripped
        # Solo agregar RETURNING id si hay columna id (tablas con clave compuesta no la tienen)
        has_id_col = _sql_tiene_id(sql)

        if is_insert and was_ignore:
            # ON CONFLICT DO NOTHING: no usar RETURNING (puede retornar nada)
            conflict_sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
            self._c.execute(conflict_sql, params) if params else self._c.execute(conflict_sql)
            self.lastrowid = None
        elif is_insert and not has_return and has_id_col:
            sql = sql.rstrip().rstrip(';') + ' RETURNING id'
            self._c.execute(sql, params) if params else self._c.execute(sql)
            row = self._c.fetchone()
            self.lastrowid = row[0] if row else None
        else:
            self._c.execute(sql, params) if params else self._c.execute(sql)
            self.lastrowid = None

    def executemany(self, sql: str, seq):
        self._c.executemany(sql.replace('?', '%s'), seq)
        self.lastrowid = None

    # ── resultados ────────────────────────────────────────────────────────

    @staticmethod
    def _norm(row):
        """Normaliza tipos PostgreSQL → tipos compatibles con código SQLite y Jinja2."""
        if row is None:
            return None
        import decimal as _dec
        import datetime as _dt

        class _DateStr(str):
            """str con .strftime(): sliceable para código desktop, templatable para Jinja2."""
            __slots__ = ('_dt_obj',)
            def strftime(self, fmt):
                return self._dt_obj.strftime(fmt)

        def _conv(v):
            if isinstance(v, _dec.Decimal):
                return float(v)
            # Convertir date/datetime a _DateStr: se comporta como str (desktop)
            # y tiene .strftime() (Jinja2/web)
            if isinstance(v, _dt.datetime):
                s = _DateStr(v.strftime('%Y-%m-%d %H:%M:%S'))
                s._dt_obj = v
                return s
            if isinstance(v, _dt.date):
                s = _DateStr(v.strftime('%Y-%m-%d'))
                s._dt_obj = v
                return s
            return v

        return tuple(_conv(v) for v in row)

    def fetchone(self):
        return self._norm(self._c.fetchone())

    def fetchall(self):
        return [self._norm(r) for r in self._c.fetchall()]

    def fetchmany(self, n=None):
        rows = self._c.fetchmany(n) if n else self._c.fetchmany()
        return [self._norm(r) for r in rows]

    # ── propiedades ───────────────────────────────────────────────────────

    @property
    def description(self):
        return self._c.description

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        self._c.close()


class _PgConn:
    """
    Wrapper de psycopg2.connection compatible con sqlite3.Connection.
    Expone commit / rollback / close y context manager.
    """

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):
        return _PgCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
# Funciones públicas
# ─────────────────────────────────────────────────────────────────────────────

def conectar_empresa(db_path: str = None, pg_database: str = None):
    """
    Retorna (conn, cursor) para la BD de empresa.
      SQLite      → abre db_path
      PostgreSQL  → conecta al servidor; usa pg_database o el default en config.json
    """
    cfg = _cfg()

    if cfg.get('motor') == 'postgresql':
        import psycopg2
        import os as _os
        pg     = cfg['postgresql']
        dbname = pg_database or pg.get('database', 'clf_empresa')
        _os.environ['PGPASSWORD'] = pg['password']
        _os.environ['PGPASSFILE'] = _os.devnull
        raw    = psycopg2.connect(
            host=pg['host'],
            port=pg.get('port', 5432),
            dbname=dbname,
            user=pg['user'],
            password=pg['password'],
        )
        raw.autocommit = True   # Igual que SQLite: cada sentencia es independiente
        conn = _PgConn(raw)
        return conn, conn.cursor()

    else:
        import sqlite3
        conn = sqlite3.connect(db_path)
        return conn, conn.cursor()


def conectar_usuarios():
    """
    Retorna (conn, cursor) para la BD central de usuarios.
      SQLite      → abre app_usuarios.db
      PostgreSQL  → conecta a database_usuarios configurada en config.json
    """
    cfg = _cfg()

    if cfg.get('motor') == 'postgresql':
        import psycopg2
        import os as _os
        pg  = cfg['postgresql']
        _os.environ['PGPASSWORD'] = pg['password']
        _os.environ['PGPASSFILE'] = _os.devnull
        raw = psycopg2.connect(
            host=pg['host'],
            port=pg.get('port', 5432),
            dbname=pg.get('database_usuarios', 'clf_usuarios'),
            user=pg['user'],
            password=pg['password'],
        )
        raw.autocommit = True   # Igual que SQLite: cada sentencia es independiente
        conn = _PgConn(raw)
        return conn, conn.cursor()

    else:
        import sqlite3
        conn = sqlite3.connect(_USERS_DB)
        return conn, conn.cursor()
