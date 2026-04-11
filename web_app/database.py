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

        # Importamos el wrapper de db_connection para mantener compatibilidad
        import sys
        if str(_BASE_DIR) not in sys.path:
            sys.path.insert(0, str(_BASE_DIR))
        from db_connection import _PgConn

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
