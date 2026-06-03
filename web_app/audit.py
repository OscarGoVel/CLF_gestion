# -*- coding: utf-8 -*-
"""
web_app/audit.py
Registro de eventos de seguridad en la base de datos.

Tabla: audit_log (en clf_usuarios)
Columnas: id, usuario_id, username, evento, detalle, ip, ts
"""

import logging

from web_app.database import pool_usuarios

logger = logging.getLogger(__name__)

# ── Tipos de evento ───────────────────────────────────────────────────────────
LOGIN_OK        = "login_exitoso"
LOGIN_FALLO     = "login_fallido"
LOGOUT          = "logout"
ACCESO_DENEGADO = "acceso_denegado"


def _asegurar_tabla():
    """Crea la tabla audit_log si no existe (solo se llama una vez al arrancar)."""
    with pool_usuarios.conexion() as (_, cursor):
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id         SERIAL PRIMARY KEY,
                usuario_id INTEGER,
                username   TEXT,
                evento     TEXT NOT NULL,
                detalle    TEXT,
                ip         TEXT,
                ts         TIMESTAMPTZ DEFAULT NOW()
            )
        """)


def registrar(evento: str, *, username: str = None, usuario_id: int = None,
              detalle: str = None, ip: str = None):
    """
    Inserta un evento en audit_log.
    No lanza excepciones — el fallo de auditoría no debe interrumpir la petición.
    """
    try:
        with pool_usuarios.conexion() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO audit_log (usuario_id, username, evento, detalle, ip)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (usuario_id, username, evento, detalle, ip),
            )
    except Exception as e:
        logger.debug("audit.registrar falló: %s", e)


def obtener_ultimos(limite: int = 50) -> list[dict]:
    """Devuelve los últimos eventos de auditoría como lista de dicts."""
    with pool_usuarios.conexion() as (_, cursor):
        cursor.execute(
            """
            SELECT id, usuario_id, username, evento, detalle, ip, ts
            FROM audit_log
            ORDER BY ts DESC
            LIMIT %s
            """,
            (limite,),
        )
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
