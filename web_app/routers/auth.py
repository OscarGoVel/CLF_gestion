# -*- coding: utf-8 -*-
"""
web_app/routers/auth.py
Endpoints de autenticacion con rate limiting y audit log.
"""

from pathlib import Path
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

import db_connection
from web_app.auth import verificar_password, crear_token, TOKEN_EXPIRE_HOURS
from web_app import audit

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _ip(request: Request) -> str:
    return request.client.host if request.client else "desconocida"


@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    def _error(msg: str):
        audit.registrar(
            audit.LOGIN_FALLO,
            username=username,
            detalle=msg,
            ip=_ip(request),
        )
        return templates.TemplateResponse(
            request=request, name="login.html", context={"error": msg}
        )

    # ── Consultar usuario ─────────────────────────────────────────────────
    try:
        conn, cursor = db_connection.conectar_usuarios()
        cursor.execute(
            "SELECT id, nombre, password_hash, rol, activo FROM usuarios WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        conn.close()
    except Exception as e:
        return _error(f"Error de conexion a la base de datos: {e}")

    if row is None:
        return _error("Usuario o contrasena incorrectos.")

    uid, nombre, phash, rol, activo = row

    if not activo:
        return _error("Usuario desactivado. Contacta al administrador.")

    if not verificar_password(password, phash):
        return _error("Usuario o contrasena incorrectos.")

    # ── Login exitoso ─────────────────────────────────────────────────────
    audit.registrar(
        audit.LOGIN_OK,
        username=username,
        usuario_id=uid,
        detalle=f"rol={rol}",
        ip=_ip(request),
    )

    token = crear_token({
        "sub":      str(uid),
        "username": username,
        "nombre":   nombre,
        "rol":      rol,
    })

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=TOKEN_EXPIRE_HOURS * 3600,
        samesite="lax",
    )
    return response


@router.get("/auth/logout")
async def logout(request: Request):
    user_cookie = request.cookies.get("access_token")
    if user_cookie:
        from web_app.auth import decodificar_token
        payload = decodificar_token(user_cookie)
        if payload:
            audit.registrar(
                audit.LOGOUT,
                username=payload.get("username"),
                usuario_id=int(payload.get("sub", 0)),
                ip=_ip(request),
            )
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response
