# -*- coding: utf-8 -*-
"""
web_app/routers/admin.py
Gestion de usuarios del sistema — solo Administrador.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app import audit
from web_app.auth import _hash_password
from web_app.database import pool_usuarios
from web_app.rbac import require_rol

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

ROLES = ["Administrador", "Operador", "Solo lectura"]


# ─────────────────────────────────────────────────────────────────────────────
# LISTA
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/usuarios", response_class=HTMLResponse)
async def lista_usuarios(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    with pool_usuarios.conexion() as (_, cur):
        cur.execute("""
            SELECT id, username, nombre, rol, activo, fecha_creacion, ultimo_acceso
            FROM usuarios
            ORDER BY activo DESC, nombre
        """)
        cols    = [d[0] for d in cur.description]
        usuarios = [dict(zip(cols, r)) for r in cur.fetchall()]

    return templates.TemplateResponse(
        request=request,
        name="admin/usuarios.html",
        context={"user": user, "usuarios": usuarios, "roles": ROLES},
    )


# ─────────────────────────────────────────────────────────────────────────────
# CREAR  (GET /nuevo antes que GET /{uid})
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/usuarios/nuevo", response_class=HTMLResponse)
async def nuevo_usuario_form(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    return templates.TemplateResponse(
        request=request,
        name="admin/usuario_form.html",
        context={"user": user, "usr": None, "roles": ROLES},
    )


@router.post("/usuarios/nuevo", response_class=HTMLResponse)
async def crear_usuario(
    request: Request,
    user=Depends(require_rol("Administrador")),
    username: str = Form(""),
    nombre: str = Form(""),
    rol: str = Form("Operador"),
    password: str = Form(""),
    password2: str = Form(""),
):
    username = username.strip().lower()
    nombre   = nombre.strip()

    error = None
    if not username:
        error = "El nombre de usuario es obligatorio."
    elif not nombre:
        error = "El nombre completo es obligatorio."
    elif not password:
        error = "La contraseña es obligatoria."
    elif password != password2:
        error = "Las contraseñas no coinciden."
    elif len(password) < 6:
        error = "La contraseña debe tener al menos 6 caracteres."
    elif rol not in ROLES:
        error = "Rol inválido."

    if error:
        vals = dict(username=username, nombre=nombre, rol=rol)
        return templates.TemplateResponse(
            request=request,
            name="admin/usuario_form.html",
            context={"user": user, "usr": vals, "roles": ROLES, "error": error},
        )

    phash = _hash_password(password)
    try:
        with pool_usuarios.conexion() as (_, cur):
            cur.execute("""
                INSERT INTO usuarios (username, nombre, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, 1)
                RETURNING id
            """, (username, nombre, phash, rol))
            new_id = cur.fetchone()[0]
    except Exception as e:
        error = (f"El usuario '{username}' ya está en uso."
                 if "unique" in str(e).lower() or "duplicate" in str(e).lower()
                 else "Error al crear el usuario. Intenta de nuevo.")
        vals = dict(username=username, nombre=nombre, rol=rol)
        return templates.TemplateResponse(
            request=request,
            name="admin/usuario_form.html",
            context={"user": user, "usr": vals, "roles": ROLES, "error": error},
        )

    audit.registrar(
        "usuario_creado",
        username=user.get("username"),
        detalle=f"nuevo_user={username} rol={rol}",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/usuarios", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# EDITAR
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/usuarios/{uid}/editar", response_class=HTMLResponse)
async def editar_usuario_form(
    request: Request,
    uid: int,
    user=Depends(require_rol("Administrador")),
):
    with pool_usuarios.conexion() as (_, cur):
        cur.execute(
            "SELECT id, username, nombre, rol, activo FROM usuarios WHERE id = %s", (uid,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Usuario no encontrado")
        usr = dict(zip([d[0] for d in cur.description], row))

    return templates.TemplateResponse(
        request=request,
        name="admin/usuario_form.html",
        context={"user": user, "usr": usr, "roles": ROLES},
    )


@router.post("/usuarios/{uid}/editar", response_class=HTMLResponse)
async def guardar_usuario(
    request: Request,
    uid: int,
    user=Depends(require_rol("Administrador")),
    nombre: str = Form(""),
    rol: str = Form("Operador"),
    password: str = Form(""),
    password2: str = Form(""),
):
    nombre = nombre.strip()

    error = None
    if not nombre:
        error = "El nombre completo es obligatorio."
    elif rol not in ROLES:
        error = "Rol inválido."
    elif password and password != password2:
        error = "Las contraseñas no coinciden."
    elif password and len(password) < 6:
        error = "La contraseña debe tener al menos 6 caracteres."

    if error:
        with pool_usuarios.conexion() as (_, cur):
            cur.execute(
                "SELECT id, username, nombre, rol, activo FROM usuarios WHERE id = %s", (uid,)
            )
            row = cur.fetchone()
            cols = [d[0] for d in cur.description]
            usr  = dict(zip(cols, row)) if row else {"id": uid, "nombre": nombre, "rol": rol}
        return templates.TemplateResponse(
            request=request,
            name="admin/usuario_form.html",
            context={"user": user, "usr": usr, "roles": ROLES, "error": error},
        )

    with pool_usuarios.conexion() as (_, cur):
        if password:
            cur.execute(
                "UPDATE usuarios SET nombre = %s, rol = %s, password_hash = %s WHERE id = %s",
                (nombre, rol, _hash_password(password), uid),
            )
        else:
            cur.execute(
                "UPDATE usuarios SET nombre = %s, rol = %s WHERE id = %s",
                (nombre, rol, uid),
            )

    audit.registrar(
        "usuario_editado",
        username=user.get("username"),
        detalle=f"uid={uid} nombre={nombre} rol={rol}" + (" +pwd" if password else ""),
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/usuarios", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# TOGGLE ACTIVO (HTMX)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/usuarios/{uid}/toggle", response_class=HTMLResponse)
async def toggle_usuario(
    request: Request,
    uid: int,
    user=Depends(require_rol("Administrador")),
):
    # No puede desactivarse a sí mismo
    if str(uid) == str(user.get("sub")):
        return HTMLResponse(
            "<span class='text-xs text-red-500 px-2'>No puedes desactivarte a ti mismo</span>"
        )

    with pool_usuarios.conexion() as (_, cur):
        cur.execute("SELECT activo, username FROM usuarios WHERE id = %s", (uid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404)
        nuevo_activo = 0 if row[0] else 1
        cur.execute("UPDATE usuarios SET activo = %s WHERE id = %s", (nuevo_activo, uid))

    audit.registrar(
        "usuario_activado" if nuevo_activo else "usuario_desactivado",
        username=user.get("username"),
        detalle=f"uid={uid} target={row[1]}",
        ip=request.client.host if request.client else None,
    )

    _cls_on  = "px-3 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-600 transition-colors cursor-pointer border-0"
    _cls_off = "px-3 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-600 hover:bg-green-100 hover:text-green-700 transition-colors cursor-pointer border-0"

    if nuevo_activo:
        return HTMLResponse(
            f'<button hx-post="/admin/usuarios/{uid}/toggle" hx-swap="outerHTML" class="{_cls_on}">Activo</button>'
        )
    return HTMLResponse(
        f'<button hx-post="/admin/usuarios/{uid}/toggle" hx-swap="outerHTML" class="{_cls_off}">Inactivo</button>'
    )
