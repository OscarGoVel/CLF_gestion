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

from web_app.auth import verificar_password, hash_password, crear_token
from web_app.database import pool_usuarios, get_empresas
from web_app.config import settings
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
    empresa_id: str = Form(...),
):
    empresas = get_empresas()

    def _error(msg: str):
        audit.registrar(
            audit.LOGIN_FALLO,
            username=username,
            detalle=msg,
            ip=_ip(request),
        )
        return templates.TemplateResponse(
            request=request, name="login.html",
            context={"error": msg, "empresas": empresas},
        )

    # ── Validar empresa seleccionada ──────────────────────────────────────
    empresa = next((e for e in empresas if e["id"] == empresa_id), None)
    if empresa is None:
        return _error("Empresa no válida.")

    # ── Consultar usuario ─────────────────────────────────────────────────
    try:
        with pool_usuarios.conexion() as (conn, cursor):
            cursor.execute(
                "SELECT id, nombre, password_hash, salt, rol, activo FROM usuarios WHERE username = %s",
                (username,),
            )
            row = cursor.fetchone()
            if row is None:
                return _error("Usuario o contraseña incorrectos.")

            uid, nombre, phash, salt, rol, activo = row

            if not activo:
                return _error("Usuario desactivado. Contacta al administrador.")

            if not verificar_password(password, phash, salt):
                return _error("Usuario o contraseña incorrectos.")

            # Rolling upgrade: si el usuario aún usaba salt estático, re-hashear ahora
            if not salt:
                new_hash, new_salt = hash_password(password)
                cursor.execute(
                    "UPDATE usuarios SET password_hash = %s, salt = %s WHERE id = %s",
                    (new_hash, new_salt, uid),
                )

    except Exception as e:
        return _error(f"Error de conexión a la base de datos: {e}")

    # ── Login exitoso ─────────────────────────────────────────────────────
    audit.registrar(
        audit.LOGIN_OK,
        username=username,
        usuario_id=uid,
        detalle=f"rol={rol} empresa={empresa_id}",
        ip=_ip(request),
    )

    token = crear_token({
        "sub":            str(uid),
        "username":       username,
        "nombre":         nombre,
        "rol":            rol,
        "empresa_id":     empresa_id,
        "empresa_db":     empresa["pg_database"],
        "empresa_nombre": empresa["nombre"],
    })

    response = RedirectResponse("/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.es_produccion,
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
