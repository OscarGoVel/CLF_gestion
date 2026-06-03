# -*- coding: utf-8 -*-
"""
web_app/historial.py
Registro de eventos de negocio por entidad (cotizaciones, compras, etc.).
"""

import logging

from web_app.database import get_pool_empresa

logger = logging.getLogger(__name__)


def log_evento(empresa_db: str, entidad: str, entidad_id: int,
               accion: str, detalle: str = None, usuario: str = None):
    """Inserta un evento en historial_eventos. Silencioso si falla."""
    try:
        with get_pool_empresa(empresa_db).conexion() as (_, cur):
            cur.execute(
                """INSERT INTO historial_eventos (entidad, entidad_id, accion, detalle, usuario)
                   VALUES (%s, %s, %s, %s, %s)""",
                (entidad, entidad_id, accion, detalle, usuario),
            )
    except Exception as e:
        logger.debug("historial.log_evento falló: %s", e)
