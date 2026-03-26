# -*- coding: utf-8 -*-
"""
web_app/dependencies.py
Dependencias reutilizables de FastAPI.
"""

from typing import Optional
from fastapi import Request
from web_app.auth import decodificar_token


def get_usuario_actual(request: Request) -> Optional[dict]:
    """
    Lee el token JWT de la cookie 'access_token' y lo decodifica.
    Retorna el payload como dict, o None si no hay sesion valida.
    Los tokens sin empresa_db (emitidos antes de la v2) fuerzan nuevo login.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decodificar_token(token)
    if payload is None:
        return None
    if "empresa_db" not in payload:
        return None
    return payload
