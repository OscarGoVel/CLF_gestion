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
from web_app.auth import hash_password
from web_app.database import pool_usuarios, get_pool_empresa
from web_app.rbac import (
    require_rol,
    PERMISOS_DEFAULT,
    PERMISOS_LABELS,
    _get_permisos_empresa,
    invalidar_cache_permisos,
)

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

ROLES = ["Administrador", "Operador", "Almacenista", "Solo lectura"]


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

    phash, salt = hash_password(password)
    try:
        with pool_usuarios.conexion() as (_, cur):
            cur.execute("""
                INSERT INTO usuarios (username, nombre, password_hash, salt, rol, activo)
                VALUES (%s, %s, %s, %s, %s, 1)
                RETURNING id
            """, (username, nombre, phash, salt, rol))
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
            new_hash, new_salt = hash_password(password)
            cur.execute(
                "UPDATE usuarios SET nombre = %s, rol = %s, password_hash = %s, salt = %s WHERE id = %s",
                (nombre, rol, new_hash, new_salt, uid),
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


# ─────────────────────────────────────────────────────────────────────────────
# PERMISOS POR ROL
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/permisos", response_class=HTMLResponse)
async def ver_permisos(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    permisos_actuales = _get_permisos_empresa(user["empresa_db"])
    return templates.TemplateResponse(
        request=request,
        name="admin/permisos.html",
        context={
            "user": user,
            "permisos_default": PERMISOS_DEFAULT,
            "permisos_labels": PERMISOS_LABELS,
            "permisos_actuales": permisos_actuales,
            "roles_configurables": ["Operador", "Almacenista", "Solo lectura"],
            "guardado": "guardado" in request.query_params,
        },
    )


@router.post("/permisos", response_class=HTMLResponse)
async def guardar_permisos(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    form_data = await request.form()
    roles_configurables = ["Operador", "Almacenista", "Solo lectura"]

    checked: list[tuple[str, str]] = []
    for key in PERMISOS_DEFAULT:
        for rol in roles_configurables:
            if form_data.get(f"perm_{key}_{rol}") == "on":
                checked.append((key, rol))

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS config_permisos (
                permiso_key TEXT NOT NULL,
                rol         TEXT NOT NULL,
                PRIMARY KEY (permiso_key, rol)
            )
        """)
        cur.execute("DELETE FROM config_permisos WHERE rol != 'Administrador'")
        for key, rol in checked:
            cur.execute(
                "INSERT INTO config_permisos (permiso_key, rol) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (key, rol),
            )

    invalidar_cache_permisos(user["empresa_db"])

    audit.registrar(
        "permisos_actualizados",
        username=user.get("username"),
        detalle=f"{len(checked)} permisos configurados",
        ip=request.client.host if request.client else None,
    )
    return RedirectResponse("/admin/permisos?guardado=1", status_code=303)


# ─────────────────────────────────────────────────────────────────────────────
# UBICACIONES — Sucursales y Áreas
# ─────────────────────────────────────────────────────────────────────────────

def _asegurar_ubicaciones(empresa_db: str) -> None:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sucursales (
                id          SERIAL PRIMARY KEY,
                nombre      TEXT NOT NULL,
                descripcion TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS areas (
                id          SERIAL PRIMARY KEY,
                sucursal_id INTEGER NOT NULL REFERENCES sucursales(id) ON DELETE CASCADE,
                nombre      TEXT NOT NULL
            )
        """)


def _cargar_sucursales(cur) -> list:
    cur.execute("""
        SELECT s.id, s.nombre, s.descripcion,
               COUNT(a.id) AS total_areas
        FROM sucursales s
        LEFT JOIN areas a ON a.sucursal_id = s.id
        GROUP BY s.id
        ORDER BY s.nombre
    """)
    cols = [d[0] for d in cur.description]
    sucursales = [dict(zip(cols, r)) for r in cur.fetchall()]
    for suc in sucursales:
        cur.execute(
            "SELECT id, nombre FROM areas WHERE sucursal_id = %s ORDER BY nombre",
            (suc["id"],),
        )
        suc["areas"] = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]
    return sucursales


@router.get("/ubicaciones", response_class=HTMLResponse)
async def ver_ubicaciones(
    request: Request,
    user=Depends(require_rol("Administrador")),
):
    _asegurar_ubicaciones(user["empresa_db"])
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        sucursales = _cargar_sucursales(cur)
    return templates.TemplateResponse(
        request=request,
        name="admin/ubicaciones.html",
        context={
            "user": user,
            "sucursales": sucursales,
            "guardado": "guardado" in request.query_params,
        },
    )


@router.post("/sucursales", response_class=HTMLResponse)
async def crear_sucursal(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    user=Depends(require_rol("Administrador")),
):
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse("/admin/ubicaciones", status_code=303)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "INSERT INTO sucursales (nombre, descripcion) VALUES (%s, %s)",
            (nombre, descripcion.strip() or None),
        )
    return RedirectResponse("/admin/ubicaciones?guardado=1", status_code=303)


@router.post("/sucursales/{suc_id}/editar", response_class=HTMLResponse)
async def editar_sucursal(
    request: Request,
    suc_id: int,
    nombre: str = Form(...),
    descripcion: str = Form(""),
    user=Depends(require_rol("Administrador")),
):
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse("/admin/ubicaciones", status_code=303)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "UPDATE sucursales SET nombre = %s, descripcion = %s WHERE id = %s",
            (nombre, descripcion.strip() or None, suc_id),
        )
    return RedirectResponse("/admin/ubicaciones?guardado=1", status_code=303)


@router.post("/sucursales/{suc_id}/eliminar", response_class=HTMLResponse)
async def eliminar_sucursal(
    request: Request,
    suc_id: int,
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        # Verificar que no tenga áreas con productos asignados
        cur.execute("""
            SELECT COUNT(*) FROM stock_ubicaciones su
            JOIN areas a ON a.id = su.area_id
            WHERE a.sucursal_id = %s
        """, (suc_id,))
        if cur.fetchone()[0] > 0:
            # Devolver error como HTMX fragment
            return HTMLResponse(
                '<p class="text-xs text-red-500 px-2">No se puede eliminar: hay productos asignados a áreas de esta sucursal.</p>'
            )
        cur.execute("DELETE FROM sucursales WHERE id = %s", (suc_id,))
    return RedirectResponse("/admin/ubicaciones?guardado=1", status_code=303)


@router.post("/areas", response_class=HTMLResponse)
async def crear_area(
    request: Request,
    sucursal_id: int = Form(...),
    nombre: str = Form(...),
    user=Depends(require_rol("Administrador")),
):
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse("/admin/ubicaciones", status_code=303)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "INSERT INTO areas (sucursal_id, nombre) VALUES (%s, %s)",
            (sucursal_id, nombre),
        )
    return RedirectResponse("/admin/ubicaciones?guardado=1", status_code=303)


@router.post("/areas/{area_id}/editar", response_class=HTMLResponse)
async def editar_area(
    request: Request,
    area_id: int,
    nombre: str = Form(...),
    user=Depends(require_rol("Administrador")),
):
    nombre = nombre.strip()
    if not nombre:
        return RedirectResponse("/admin/ubicaciones", status_code=303)
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("UPDATE areas SET nombre = %s WHERE id = %s", (nombre, area_id))
    return RedirectResponse("/admin/ubicaciones?guardado=1", status_code=303)


@router.post("/areas/{area_id}/eliminar", response_class=HTMLResponse)
async def eliminar_area(
    request: Request,
    area_id: int,
    user=Depends(require_rol("Administrador")),
):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT COUNT(*) FROM stock_ubicaciones WHERE area_id = %s", (area_id,)
        )
        if cur.fetchone()[0] > 0:
            return HTMLResponse(
                '<p class="text-xs text-red-500 px-2">No se puede eliminar: hay productos asignados a esta área.</p>'
            )
        cur.execute("DELETE FROM areas WHERE id = %s", (area_id,))
    return RedirectResponse("/admin/ubicaciones?guardado=1", status_code=303)
