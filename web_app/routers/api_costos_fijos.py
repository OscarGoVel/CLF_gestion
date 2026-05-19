# -*- coding: utf-8 -*-
"""
web_app/routers/api_costos_fijos.py
/api/costos-fijos — CRUD de costos fijos mensuales.
Módulo nuevo — tabla costos_fijos creada en main.py lifespan.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/costos-fijos", tags=["api"])

CATEGORIAS = ("renta", "nomina", "servicios", "depreciacion", "otro")


def _s(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


class CostoFijoIn(BaseModel):
    periodo: str          # "YYYY-MM"
    categoria: str
    descripcion: str
    monto: float


# ── GET /api/costos-fijos ─────────────────────────────────────────────────────

@router.get("")
async def listar(
    periodo: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    from datetime import date
    if not periodo:
        periodo = date.today().strftime("%Y-%m")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            SELECT id, periodo, categoria, descripcion, monto, created_by, created_at
            FROM costos_fijos
            WHERE periodo = %s
            ORDER BY categoria, descripcion
        """, (periodo,))
        items = _rows(cur)

        cur.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM costos_fijos WHERE periodo = %s",
            (periodo,),
        )
        total = _s(cur.fetchone()[0])

    return {"periodo": periodo, "items": items, "total": total}


# ── GET /api/costos-fijos/total/{periodo} ────────────────────────────────────

@router.get("/total/{periodo}")
async def total_periodo(periodo: str, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM costos_fijos WHERE periodo = %s",
            (periodo,),
        )
        total = _s(cur.fetchone()[0])
    return {"periodo": periodo, "total": total}


# ── POST /api/costos-fijos ────────────────────────────────────────────────────

@router.post("")
async def crear(body: CostoFijoIn, user: dict = Depends(get_usuario_api)):
    if body.categoria not in CATEGORIAS:
        raise HTTPException(status_code=422, detail=f"Categoría inválida. Opciones: {CATEGORIAS}")
    if body.monto <= 0:
        raise HTTPException(status_code=422, detail="El monto debe ser positivo")
    if not body.descripcion.strip():
        raise HTTPException(status_code=422, detail="Descripción requerida")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            INSERT INTO costos_fijos (periodo, categoria, descripcion, monto, created_by)
            VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at
        """, (body.periodo, body.categoria, body.descripcion.strip(),
              body.monto, user["nombre"]))
        row = cur.fetchone()

    return {
        "id": row[0],
        "periodo": body.periodo,
        "categoria": body.categoria,
        "descripcion": body.descripcion,
        "monto": body.monto,
        "created_at": _s(row[1]),
    }


# ── PUT /api/costos-fijos/{id} ────────────────────────────────────────────────

@router.put("/{costo_id}")
async def editar(
    costo_id: int,
    body: CostoFijoIn,
    user: dict = Depends(get_usuario_api),
):
    if body.categoria not in CATEGORIAS:
        raise HTTPException(status_code=422, detail=f"Categoría inválida. Opciones: {CATEGORIAS}")
    if body.monto <= 0:
        raise HTTPException(status_code=422, detail="El monto debe ser positivo")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("""
            UPDATE costos_fijos
            SET periodo = %s, categoria = %s, descripcion = %s, monto = %s
            WHERE id = %s RETURNING id
        """, (body.periodo, body.categoria, body.descripcion.strip(),
              body.monto, costo_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Costo no encontrado")

    return {"ok": True}


# ── DELETE /api/costos-fijos/{id} ────────────────────────────────────────────

@router.delete("/{costo_id}")
async def eliminar(costo_id: int, user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(
            "DELETE FROM costos_fijos WHERE id = %s RETURNING id", (costo_id,)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Costo no encontrado")
    return {"ok": True}
