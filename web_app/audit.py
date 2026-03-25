# -*- coding: utf-8 -*-
"""
web_app/audit.py
Registro de eventos de seguridad en la base de datos.

Tabla: audit_log (en clf_usuarios)
Columnas: id, usuario_id, username, evento, detalle, ip, ts
"""

from datetime import datetime, timezone

import db_connection

# ── Tipos de evento ───────────────────────────────────────────────────────────
LOGIN_OK      = "login_exitoso"
LOGIN_FALLO   = "login_fallido"
LOGOUT        = "logout"
ACCESO_DENEGADO = "acceso_denegado"


def _asegurar_tabla():
    """Crea la tabla audit_log si no existe (solo se llama una vez al arrancar)."""
    conn, cursor = db_connection.conectar_usuarios()
    try:
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
        conn.commit()
    finally:
        conn.close()


def registrar(evento: str, *, username: str = None, usuario_id: int = None,
              detalle: str = None, ip: str = None):
    """
    Inserta un evento en audit_log.
    No lanza excepciones — el fallo de auditoria no debe interrumpir la peticion.
    """
    try:
        conn, cursor = db_connection.conectar_usuarios()
        cursor.execute(
            """
            INSERT INTO audit_log (usuario_id, username, evento, detalle, ip)
            VALUES (?, ?, ?, ?, ?)
            """,
            (usuario_id, username, evento, detalle, ip),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # auditoria silenciosa


def obtener_ultimos(limite: int = 50) -> list[dict]:
    """Devuelve los ultimos eventos de auditoria como lista de dicts."""
    conn, cursor = db_connection.conectar_usuarios()
    try:
        cursor.execute(
            """
            SELECT id, usuario_id, username, evento, detalle, ip, ts
            FROM audit_log
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limite,),
        )
        cols = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()
