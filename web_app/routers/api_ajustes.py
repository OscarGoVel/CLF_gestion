# -*- coding: utf-8 -*-
"""
web_app/routers/api_ajustes.py
/api/ajustes — perfil de usuario, contraseña y gestión de usuarios para el SPA React.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from web_app.auth import hash_password, verificar_password
from web_app.database import pool_usuarios
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/ajustes", tags=["api"])

ROLES = ["Administrador", "Operador", "Almacenista", "Solo lectura"]


def _serial_user(row, cols):
    u = dict(zip(cols, row))
    for k in ("fecha_creacion", "ultimo_acceso"):
        if u.get(k) and hasattr(u[k], "isoformat"):
            u[k] = u[k].isoformat()
        elif u.get(k):
            u[k] = str(u[k])
    return u


def _require_admin(user: dict):
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")


# ── Perfil ────────────────────────────────────────────────────────────────────

@router.get("/perfil")
async def get_perfil(user: dict = Depends(get_usuario_api)):
    uid = int(user["sub"])
    with pool_usuarios.conexion() as (_, cur):
        cur.execute(
            "SELECT id, username, nombre, rol, activo, fecha_creacion, ultimo_acceso "
            "FROM usuarios WHERE id = %s",
            (uid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        perfil = _serial_user(row, [d[0] for d in cur.description])
    return JSONResponse(perfil)


class PerfilIn(BaseModel):
    nombre: str


@router.put("/perfil")
async def update_perfil(body: PerfilIn, user: dict = Depends(get_usuario_api)):
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="El nombre no puede estar vacío")
    uid = int(user["sub"])
    with pool_usuarios.conexion() as (conn, cur):
        cur.execute("UPDATE usuarios SET nombre = %s WHERE id = %s", (nombre, uid))
        conn.commit()
    return JSONResponse({"ok": True})


class PasswordIn(BaseModel):
    password_actual: str
    password_nuevo: str


@router.post("/password")
async def cambiar_password(body: PasswordIn, user: dict = Depends(get_usuario_api)):
    if len(body.password_nuevo) < 6:
        raise HTTPException(status_code=422, detail="La contraseña debe tener al menos 6 caracteres")
    uid = int(user["sub"])
    with pool_usuarios.conexion() as (conn, cur):
        cur.execute("SELECT password_hash, salt FROM usuarios WHERE id = %s", (uid,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        phash, salt = row
        if not verificar_password(body.password_actual, phash, salt):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        new_hash, new_salt = hash_password(body.password_nuevo)
        cur.execute(
            "UPDATE usuarios SET password_hash = %s, salt = %s WHERE id = %s",
            (new_hash, new_salt, uid),
        )
        conn.commit()
    return JSONResponse({"ok": True})


# ── Usuarios (admin) ──────────────────────────────────────────────────────────

@router.get("/usuarios")
async def listar_usuarios(user: dict = Depends(get_usuario_api)):
    _require_admin(user)
    with pool_usuarios.conexion() as (_, cur):
        cur.execute(
            "SELECT id, username, nombre, rol, activo, fecha_creacion, ultimo_acceso "
            "FROM usuarios ORDER BY activo DESC, nombre"
        )
        cols = [d[0] for d in cur.description]
        usuarios = [_serial_user(r, cols) for r in cur.fetchall()]
    return JSONResponse({"usuarios": usuarios, "roles": ROLES})


class UsuarioIn(BaseModel):
    username: str
    nombre: str
    rol: str
    password: str


@router.post("/usuarios", status_code=201)
async def crear_usuario(body: UsuarioIn, user: dict = Depends(get_usuario_api)):
    _require_admin(user)
    username = body.username.strip().lower()
    nombre   = body.nombre.strip()
    if not username or not nombre:
        raise HTTPException(status_code=422, detail="username y nombre son requeridos")
    if len(body.password) < 6:
        raise HTTPException(status_code=422, detail="Contraseña de al menos 6 caracteres")
    if body.rol not in ROLES:
        raise HTTPException(status_code=422, detail="Rol inválido")
    phash, salt = hash_password(body.password)
    try:
        with pool_usuarios.conexion() as (conn, cur):
            cur.execute(
                "INSERT INTO usuarios (username, nombre, password_hash, salt, rol, activo) "
                "VALUES (%s,%s,%s,%s,%s,1) RETURNING id",
                (username, nombre, phash, salt, body.rol),
            )
            new_id = cur.fetchone()[0]
            conn.commit()
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"El usuario '{username}' ya existe")
        raise HTTPException(status_code=500, detail="Error al crear usuario")
    return JSONResponse({"id": new_id}, status_code=201)


class UsuarioEditIn(BaseModel):
    nombre: str
    rol: str
    password: Optional[str] = None


@router.put("/usuarios/{uid}")
async def editar_usuario(uid: int, body: UsuarioEditIn, user: dict = Depends(get_usuario_api)):
    _require_admin(user)
    nombre = body.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="nombre requerido")
    if body.rol not in ROLES:
        raise HTTPException(status_code=422, detail="Rol inválido")
    with pool_usuarios.conexion() as (conn, cur):
        cur.execute("SELECT id FROM usuarios WHERE id = %s", (uid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if body.password:
            if len(body.password) < 6:
                raise HTTPException(status_code=422, detail="Contraseña de al menos 6 caracteres")
            phash, salt = hash_password(body.password)
            cur.execute(
                "UPDATE usuarios SET nombre=%s, rol=%s, password_hash=%s, salt=%s WHERE id=%s",
                (nombre, body.rol, phash, salt, uid),
            )
        else:
            cur.execute(
                "UPDATE usuarios SET nombre=%s, rol=%s WHERE id=%s",
                (nombre, body.rol, uid),
            )
        conn.commit()
    return JSONResponse({"ok": True})


@router.patch("/usuarios/{uid}/activo")
async def toggle_activo(uid: int, user: dict = Depends(get_usuario_api)):
    _require_admin(user)
    if str(uid) == user.get("sub"):
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo")
    with pool_usuarios.conexion() as (conn, cur):
        cur.execute(
            "UPDATE usuarios SET activo = NOT activo WHERE id = %s RETURNING activo",
            (uid,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        conn.commit()
    return JSONResponse({"activo": bool(row[0])})
