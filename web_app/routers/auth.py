# -*- coding: utf-8 -*-
"""
web_app/routers/auth.py
Endpoints de autenticacion: POST /auth/login, GET /auth/logout
"""

from pathlib import Path
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import db_connection
from web_app.auth import verificar_password, crear_token, TOKEN_EXPIRE_HOURS

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.post("/auth/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    # ── Consultar usuario en la BD de usuarios ────────────────────────────
    def _login_error(msg: str):
        return templates.TemplateResponse(
            request=request, name="login.html", context={"error": msg}
        )

    try:
        conn, cursor = db_connection.conectar_usuarios()
        cursor.execute(
            "SELECT id, nombre, password_hash, rol, activo FROM usuarios WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        conn.close()
    except Exception as e:
        return _login_error(f"Error de conexion a la base de datos: {e}")

    # ── Validaciones ──────────────────────────────────────────────────────
    if row is None:
        return _login_error("Usuario no encontrado.")

    uid, nombre, phash, rol, activo = row

    if not activo:
        return _login_error("Usuario desactivado. Contacta al administrador.")

    if not verificar_password(password, phash):
        return _login_error("Contrasena incorrecta.")

    # ── Crear token y redirigir al dashboard ──────────────────────────────
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
async def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie("access_token")
    return response
