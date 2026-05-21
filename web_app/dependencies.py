# -*- coding: utf-8 -*-
"""
web_app/dependencies.py
Dependencias reutilizables de FastAPI.
"""

from typing import Optional
from fastapi import Request, Header, HTTPException
from web_app.auth import decodificar_token


def _jti_revocado(jti: str) -> bool:
    try:
        from web_app.database import pool_usuarios
        with pool_usuarios.conexion() as (_, cur):
            cur.execute(
                "SELECT 1 FROM jwt_blacklist WHERE jti = %s AND exp > NOW()",
                (jti,),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


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


def get_usuario_api(authorization: Optional[str] = Header(default=None)) -> dict:
    """
    Dependencia para rutas /api/* del SPA React.
    Lee el JWT del header Authorization: Bearer <token>.
    Lanza 401 si falta o es inválido.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token requerido")
    token = authorization[len("Bearer "):]
    payload = decodificar_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    if "empresa_db" not in payload:
        raise HTTPException(status_code=401, detail="Token incompleto, vuelve a iniciar sesión")
    jti = payload.get("jti")
    if jti and _jti_revocado(jti):
        raise HTTPException(status_code=401, detail="Sesión cerrada, vuelve a iniciar sesión")
    return payload
