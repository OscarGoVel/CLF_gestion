# -*- coding: utf-8 -*-
"""
web_app/routers/api_razones_sociales.py
/api/razones-sociales — CRUD de razones sociales (entidades legales).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/razones-sociales", tags=["api"])


class RazonSocialIn(BaseModel):
    nombre: str
    rfc: str
    regimen_fiscal: Optional[str] = None
    codigo_postal: Optional[str] = None
    domicilio: Optional[str] = None
    es_default: bool = False
    activa: bool = True


def _serial(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ── GET /api/razones-sociales ─────────────────────────────────────────────────

@router.get("")
async def listar(user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT id, nombre, rfc, regimen_fiscal, codigo_postal, domicilio,
                   es_default, activa, created_at
            FROM razones_sociales
            ORDER BY es_default DESC, nombre ASC
        """)
        return JSONResponse({"razones_sociales": _rows(cur)})


# ── POST /api/razones-sociales ────────────────────────────────────────────────

@router.post("")
async def crear(body: RazonSocialIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    empresa_db = user["empresa_db"]
    rfc = body.rfc.strip().upper()
    with get_pool_empresa(empresa_db).conexion() as (conn, cur):
        if body.es_default:
            cur.execute("UPDATE razones_sociales SET es_default = FALSE")
        cur.execute("""
            INSERT INTO razones_sociales
                (nombre, rfc, regimen_fiscal, codigo_postal, domicilio, es_default, activa)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (body.nombre.strip(), rfc, body.regimen_fiscal, body.codigo_postal,
              body.domicilio, body.es_default, body.activa))
        new_id = cur.fetchone()[0]
        conn.commit()
    return JSONResponse({"id": new_id}, status_code=201)


# ── PUT /api/razones-sociales/{id} ───────────────────────────────────────────

@router.put("/{rs_id}")
async def actualizar(rs_id: int, body: RazonSocialIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    empresa_db = user["empresa_db"]
    rfc = body.rfc.strip().upper()
    with get_pool_empresa(empresa_db).conexion() as (conn, cur):
        cur.execute("SELECT id FROM razones_sociales WHERE id = %s", (rs_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Razón social no encontrada")
        if body.es_default:
            cur.execute("UPDATE razones_sociales SET es_default = FALSE WHERE id != %s", (rs_id,))
        cur.execute("""
            UPDATE razones_sociales
            SET nombre = %s, rfc = %s, regimen_fiscal = %s, codigo_postal = %s,
                domicilio = %s, es_default = %s, activa = %s
            WHERE id = %s
        """, (body.nombre.strip(), rfc, body.regimen_fiscal, body.codigo_postal,
              body.domicilio, body.es_default, body.activa, rs_id))
        conn.commit()
    return JSONResponse({"ok": True})


# ── DELETE /api/razones-sociales/{id} — desactiva ────────────────────────────

@router.delete("/{rs_id}")
async def desactivar(rs_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (conn, cur):
        cur.execute("SELECT es_default FROM razones_sociales WHERE id = %s", (rs_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Razón social no encontrada")
        if row[0]:
            raise HTTPException(status_code=400, detail="No se puede desactivar la RS predeterminada")
        cur.execute("UPDATE razones_sociales SET activa = FALSE WHERE id = %s", (rs_id,))
        conn.commit()
    return JSONResponse({"ok": True})


# ── PUT /api/razones-sociales/{id}/default ────────────────────────────────────

@router.put("/{rs_id}/default")
async def marcar_default(rs_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (conn, cur):
        cur.execute("SELECT id FROM razones_sociales WHERE id = %s AND activa", (rs_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Razón social no encontrada o inactiva")
        cur.execute("UPDATE razones_sociales SET es_default = FALSE")
        cur.execute("UPDATE razones_sociales SET es_default = TRUE WHERE id = %s", (rs_id,))
        conn.commit()
    return JSONResponse({"ok": True})
