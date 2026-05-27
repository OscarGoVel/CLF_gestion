# -*- coding: utf-8 -*-
"""
web_app/routers/api_cuentas_pagar.py
/api/cuentas-pagar — cuentas por pagar a proveedores.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/cuentas-pagar", tags=["api"])

_ESTADOS = ("Pendiente", "Parcial", "Pagada", "Vencida")


def _s(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ── GET /api/cuentas-pagar/resumen ────────────────────────────────────────────

@router.get("/resumen")
async def resumen(user: dict = Depends(get_usuario_api)):
    hoy = date.today()
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT
                SUM(monto_total - monto_pagado) FILTER (WHERE estado <> 'Pagada')        AS total_pendiente,
                SUM(monto_total - monto_pagado) FILTER (
                    WHERE estado <> 'Pagada'
                      AND fecha_vencimiento < %s
                )                                                                         AS total_vencido,
                SUM(monto_total - monto_pagado) FILTER (
                    WHERE estado <> 'Pagada'
                      AND fecha_vencimiento BETWEEN %s AND %s
                )                                                                         AS proximo_vencer,
                COUNT(*) FILTER (WHERE estado NOT IN ('Pagada'))                          AS total_items,
                COUNT(*) FILTER (
                    WHERE estado <> 'Pagada' AND fecha_vencimiento < %s
                )                                                                         AS items_vencidos
            FROM cuentas_por_pagar
        """, (hoy, hoy, hoy.replace(day=hoy.day).__class__(
            hoy.year, hoy.month, min(hoy.day + 7, 28)), hoy))
        r = cur.fetchone()
    return JSONResponse({
        "total_pendiente": _s(r[0]) or 0,
        "total_vencido":   _s(r[1]) or 0,
        "proximo_vencer":  _s(r[2]) or 0,
        "total_items":     r[3] or 0,
        "items_vencidos":  r[4] or 0,
    })


# ── GET /api/cuentas-pagar ────────────────────────────────────────────────────

@router.get("")
async def listar(
    estado: str = Query(""),
    proveedor_id: int = Query(0),
    vencidas: bool = Query(False),
    razon_social_id: Optional[int] = Query(None),
    user: dict = Depends(get_usuario_api),
):
    hoy = date.today()
    empresa_db = user["empresa_db"]
    where, params = ["1=1"], []

    if razon_social_id is not None:
        where.append("cxp.razon_social_id = %s")
        params.append(razon_social_id)

    if estado:
        where.append("cxp.estado = %s")
        params.append(estado)
    elif not vencidas:
        where.append("cxp.estado <> 'Pagada'")

    if vencidas:
        where.append("cxp.fecha_vencimiento < %s AND cxp.estado <> 'Pagada'")
        params.append(hoy)

    if proveedor_id:
        where.append("cxp.proveedor_id = %s")
        params.append(proveedor_id)

    sql = f"""
        SELECT
            cxp.id,
            cxp.compra_id,
            comp.folio                             AS compra_folio,
            cxp.proveedor_id,
            prov.nombre                            AS proveedor_nombre,
            cxp.monto_total,
            cxp.monto_pagado,
            cxp.monto_total - cxp.monto_pagado     AS saldo,
            cxp.fecha_vencimiento,
            cxp.estado,
            cxp.referencia_pago,
            cxp.notas,
            cxp.created_at,
            CASE
                WHEN cxp.estado = 'Pagada' THEN 'pagada'
                WHEN cxp.fecha_vencimiento IS NOT NULL
                     AND cxp.fecha_vencimiento < %s THEN 'vencida'
                WHEN cxp.fecha_vencimiento IS NOT NULL
                     AND cxp.fecha_vencimiento <= %s THEN 'proximo'
                ELSE 'ok'
            END                                    AS alerta
        FROM cuentas_por_pagar cxp
        JOIN proveedores prov ON prov.id = cxp.proveedor_id
        LEFT JOIN compras comp ON comp.id = cxp.compra_id
        WHERE {" AND ".join(where)}
        ORDER BY
            CASE WHEN cxp.estado = 'Pagada' THEN 1 ELSE 0 END,
            cxp.fecha_vencimiento ASC NULLS LAST,
            cxp.id DESC
    """

    prox_limite = date(hoy.year, hoy.month,
                       min(hoy.day + 7, 28)) if hoy.day <= 21 else date(
        hoy.year + (hoy.month // 12), (hoy.month % 12) + 1, 7)

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(sql, [hoy, prox_limite] + params)
        items = _rows(cur)

        # KPIs rápidos
        cur.execute("""
            SELECT
                SUM(monto_total - monto_pagado) FILTER (WHERE estado <> 'Pagada') AS pendiente,
                SUM(monto_total - monto_pagado) FILTER (
                    WHERE estado <> 'Pagada' AND fecha_vencimiento < %s
                )                                                                  AS vencido
            FROM cuentas_por_pagar
        """, (hoy,))
        kr = cur.fetchone()

        cur.execute("""
            SELECT id, nombre FROM proveedores ORDER BY nombre
        """)
        proveedores = [{"id": r[0], "nombre": r[1]} for r in cur.fetchall()]

    kpis = {
        "pendiente": _s(kr[0]) or 0,
        "vencido":   _s(kr[1]) or 0,
    }
    return JSONResponse({"items": items, "kpis": kpis, "proveedores": proveedores})


# ── POST /api/cuentas-pagar ───────────────────────────────────────────────────

class CxPIn(BaseModel):
    proveedor_id: int
    compra_id: Optional[int] = None
    monto_total: float
    fecha_vencimiento: Optional[str] = None
    referencia_pago: Optional[str] = None
    notas: Optional[str] = None


@router.post("", status_code=201)
async def crear(body: CxPIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if body.monto_total <= 0:
        raise HTTPException(status_code=422, detail="El monto debe ser mayor a 0")

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT id FROM proveedores WHERE id = %s", (body.proveedor_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Proveedor no encontrado")
        if body.compra_id:
            cur.execute("SELECT id FROM compras WHERE id = %s", (body.compra_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Compra no encontrada")

        cur.execute("""
            INSERT INTO cuentas_por_pagar
                (proveedor_id, compra_id, monto_total, fecha_vencimiento,
                 referencia_pago, notas)
            VALUES (%s, %s, %s, %s::date, %s, %s)
        """, (body.proveedor_id, body.compra_id, body.monto_total,
              body.fecha_vencimiento or None,
              body.referencia_pago or None, body.notas or None))
        new_id = cur.lastrowid

    return JSONResponse({"id": new_id}, status_code=201)


# ── PATCH /api/cuentas-pagar/{id}/pagar ──────────────────────────────────────

class PagarIn(BaseModel):
    monto: float
    referencia: Optional[str] = None
    notas: Optional[str] = None


@router.patch("/{cxp_id}/pagar")
async def registrar_pago(cxp_id: int, body: PagarIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if body.monto <= 0:
        raise HTTPException(status_code=422, detail="El monto debe ser mayor a 0")

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT monto_total, monto_pagado, estado
            FROM cuentas_por_pagar WHERE id = %s
        """, (cxp_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cuenta por pagar no encontrada")
        monto_total, monto_pagado, estado = float(row[0]), float(row[1] or 0), row[2]
        if estado == "Pagada":
            raise HTTPException(status_code=422, detail="Esta cuenta ya está pagada")

        nuevo_pagado = monto_pagado + body.monto
        nuevo_estado = "Pagada" if nuevo_pagado >= monto_total else "Parcial"

        cur.execute("""
            UPDATE cuentas_por_pagar
               SET monto_pagado     = %s,
                   estado           = %s,
                   referencia_pago  = COALESCE(NULLIF(%s,''), referencia_pago),
                   notas            = COALESCE(NULLIF(%s,''), notas)
             WHERE id = %s
        """, (nuevo_pagado, nuevo_estado,
              body.referencia or '', body.notas or '',
              cxp_id))

    return JSONResponse({"ok": True, "monto_pagado": nuevo_pagado, "estado": nuevo_estado})


# ── DELETE /api/cuentas-pagar/{id} ───────────────────────────────────────────

@router.delete("/{cxp_id}", status_code=204)
async def eliminar(cxp_id: int, user: dict = Depends(get_usuario_api)):
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo el Administrador puede eliminar")
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("DELETE FROM cuentas_por_pagar WHERE id = %s", (cxp_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="No encontrada")
    return None
