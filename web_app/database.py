# -*- coding: utf-8 -*-
"""
web_app/database.py
Pool de conexiones PostgreSQL para la web app.

Por que es necesario:
    La app de escritorio abre una conexion por ventana y la mantiene toda la sesion.
    En la web, cada peticion HTTP puede venir de un usuario diferente al mismo tiempo.
    Sin pool, cada peticion abriria y cerraria una conexion nueva (lento, y PostgreSQL
    tiene un limite de ~100 conexiones simultaneas por defecto).

    El pool mantiene N conexiones abiertas y las presta a cada peticion, devolviendolas
    al terminar. Esto reduce la latencia y evita agotar los recursos del servidor.

Uso:
    from web_app.database import pool_empresa, pool_usuarios

    with pool_usuarios.conexion() as (conn, cursor):
        cursor.execute("SELECT ...")
        rows = cursor.fetchall()
    # La conexion se devuelve al pool automaticamente al salir del 'with'
"""

import json
import logging
import os
import time
import threading
from contextlib import contextmanager
from pathlib import Path

_log_db = logging.getLogger("clf.db")
_SLOW_QUERY_MS = 500   # log si una consulta DB tarda mas de 500ms

_BASE_DIR = Path(__file__).parent.parent
_CONFIG   = _BASE_DIR / "config.json"

_lock = threading.Lock()


def _cfg() -> dict:
    try:
        with open(_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_TABLAS_SIN_ID = {'preferencias_usuario', 'producto_proveedor', 'seguimiento_etapas',
                  'factura_cotizaciones', 'oc_cotizaciones', 'compra_detalle_cotizacion'}


def _sql_tiene_id(sql: str) -> bool:
    import re
    m = re.search(r'INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(\w+)', sql, re.IGNORECASE)
    if m:
        return m.group(1).lower() not in _TABLAS_SIN_ID
    return True


class _PgCursor:
    """Wrapper de psycopg2.cursor compatible con sqlite3.Cursor (? → %s, lastrowid, etc.)"""

    def __init__(self, pg_cursor):
        self._c = pg_cursor
        self.lastrowid = None

    def execute(self, sql: str, params=None):
        import re as _re
        was_ignore = bool(_re.search(r'INSERT\s+OR\s+IGNORE\s+INTO', sql, _re.IGNORECASE))
        if was_ignore:
            sql = _re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO', 'INSERT INTO', sql, flags=_re.IGNORECASE)
        sql = _re.sub(r'GROUP_CONCAT\(\s*DISTINCT\s+([\w\.]+)\s*\)', r"STRING_AGG(DISTINCT \1, ',')", sql, flags=_re.IGNORECASE)
        sql = _re.sub(r'GROUP_CONCAT\(', 'STRING_AGG(', sql, flags=_re.IGNORECASE)
        _STRFTIME_MAP = {'%Y-%m-%d': 'YYYY-MM-DD', '%Y-%m': 'YYYY-MM', '%Y': 'YYYY', '%m': 'MM', '%d': 'DD'}
        def _strftime_to_tochar(m):
            fmt_sqlite = m.group(1)
            col = m.group(2)
            fmt_pg = _STRFTIME_MAP.get(fmt_sqlite, fmt_sqlite.replace('%Y','YYYY').replace('%m','MM').replace('%d','DD'))
            return f"TO_CHAR({col}, '{fmt_pg}')"
        sql = _re.sub(r"strftime\(\s*'([^']+)'\s*,\s*([^)]+?)\s*\)", _strftime_to_tochar, sql, flags=_re.IGNORECASE)
        sql = sql.replace('?', '%s')
        stripped  = sql.strip().upper()
        is_insert = stripped.startswith('INSERT')
        has_return = 'RETURNING' in stripped
        has_id_col = _sql_tiene_id(sql)
        if is_insert and was_ignore:
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

    @staticmethod
    def _norm(row):
        if row is None:
            return None
        import decimal as _dec, datetime as _dt

        class _DateStr(str):
            __slots__ = ('_dt_obj',)
            def strftime(self, fmt):
                return self._dt_obj.strftime(fmt)

        def _conv(v):
            if isinstance(v, _dec.Decimal):
                return float(v)
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

    def fetchone(self):  return self._norm(self._c.fetchone())
    def fetchall(self):  return [self._norm(r) for r in self._c.fetchall()]
    def fetchmany(self, n=None):
        rows = self._c.fetchmany(n) if n else self._c.fetchmany()
        return [self._norm(r) for r in rows]

    @property
    def description(self): return self._c.description
    @property
    def rowcount(self):    return self._c.rowcount
    def close(self):       self._c.close()


class _PgConn:
    """Wrapper de psycopg2.connection compatible con sqlite3.Connection."""

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def cursor(self):    return _PgCursor(self._conn.cursor())
    def commit(self):    self._conn.commit()
    def rollback(self):  self._conn.rollback()
    def close(self):     self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


class PgPool:
    """
    Wrapper de psycopg2.pool.ThreadedConnectionPool con la interfaz de db_connection.
    Expone conexiones compatibles con el codigo existente (placeholders ?, lastrowid, etc.)
    """

    def __init__(self, dbname: str, minconn: int = 2, maxconn: int = 10):
        self._dbname  = dbname
        self._minconn = minconn
        self._maxconn = maxconn
        self._pool    = None

    def _init(self):
        """Inicializa el pool en el primer uso (lazy init)."""
        if self._pool is not None:
            return
        with _lock:
            if self._pool is not None:
                return
            import psycopg2.pool
            cfg = _cfg()
            pg  = cfg.get("postgresql", {})
            password = os.environ.get("CLF_PG_PASSWORD") or pg.get("password", "")
            os.environ["PGPASSFILE"] = os.devnull
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                self._minconn,
                self._maxconn,
                host=pg.get("host", "localhost"),
                port=pg.get("port", 5432),
                dbname=self._dbname,
                user=pg.get("user", "postgres"),
                password=password,
            )

    @contextmanager
    def conexion(self):
        """
        Context manager que entrega (conn, cursor) compatibles con db_connection
        y devuelve la conexion al pool al terminar.

        Ejemplo:
            with pool_usuarios.conexion() as (conn, cursor):
                cursor.execute("SELECT id FROM usuarios WHERE username = ?", (u,))
        """
        self._init()

        t0 = time.monotonic()
        raw_conn = self._pool.getconn()
        raw_conn.autocommit = False
        conn   = _PgConn(raw_conn)
        cursor = conn.cursor()
        try:
            yield conn, cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            self._pool.putconn(raw_conn)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > _SLOW_QUERY_MS:
                _log_db.warning(
                    f"SLOW QUERY [{self._dbname}] {elapsed_ms:.0f}ms"
                )

    def estado(self) -> dict:
        """Retorna estado del pool para el health check."""
        if self._pool is None:
            return {"estado": "no_iniciado"}
        p = self._pool
        return {
            "estado":    "activo",
            "db":        self._dbname,
            "min":       self._minconn,
            "max":       self._maxconn,
            "cerradas":  len(p._pool),
        }

    def cerrar(self):
        if self._pool:
            self._pool.closeall()
            self._pool = None


def _get_db_usuarios() -> str:
    cfg = _cfg()
    return cfg.get("postgresql", {}).get("database_usuarios", "clf_usuarios")


def get_empresas() -> list[dict]:
    """Retorna la lista de empresas definidas en config.json."""
    return _cfg().get("empresas", [])


# ── Pools por empresa ─────────────────────────────────────────────────────────

_pools_empresa: dict[str, "PgPool"] = {}
_pools_lock = threading.Lock()


def get_pool_empresa(pg_database: str) -> "PgPool":
    """Retorna (o crea) el pool de conexiones para una empresa dado su pg_database."""
    if pg_database not in _pools_empresa:
        with _pools_lock:
            if pg_database not in _pools_empresa:
                _min = int(os.environ.get("CLF_POOL_MIN", 2))
                _max = int(os.environ.get("CLF_POOL_MAX", 10))
                _pools_empresa[pg_database] = PgPool(pg_database, minconn=_min, maxconn=_max)
    return _pools_empresa[pg_database]


def cerrar_todos_pools_empresa():
    """Cierra todos los pools de empresa al apagar el servidor."""
    with _pools_lock:
        for pool in _pools_empresa.values():
            pool.cerrar()
        _pools_empresa.clear()


# ── Pool de usuarios (único) ──────────────────────────────────────────────────

_db_usuarios = _get_db_usuarios()
pool_usuarios = PgPool(_db_usuarios,
                       minconn=int(os.environ.get("CLF_POOL_USR_MIN", 2)),
                       maxconn=int(os.environ.get("CLF_POOL_USR_MAX", 5)))

# pool_empresa: alias al pool de la primera empresa (backward-compat para health/metrics)
_empresas_cfg = get_empresas()
_db_empresa_default = _empresas_cfg[0]["pg_database"] if _empresas_cfg else "clf_empresa"
pool_empresa = get_pool_empresa(_db_empresa_default)
