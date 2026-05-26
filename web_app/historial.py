# -*- coding: utf-8 -*-
"""
web_app/historial.py
Registro de eventos de negocio por entidad (cotizaciones, compras, etc.).
"""

from web_app.database import get_pool_empresa


def log_evento(empresa_db: str, entidad: str, entidad_id: int,
               accion: str, detalle: str = None, usuario: str = None):
    """Inserta un evento en historial_eventos. Silencioso si falla."""
    try:
        with get_pool_empresa(empresa_db).conexion() as (conn, cur):
            cur.execute(
                """INSERT INTO historial_eventos (entidad, entidad_id, accion, detalle, usuario)
                   VALUES (%s, %s, %s, %s, %s)""",
                (entidad, entidad_id, accion, detalle, usuario),
            )
    except Exception:
        pass
