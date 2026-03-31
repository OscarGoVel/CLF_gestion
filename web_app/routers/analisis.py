# -*- coding: utf-8 -*-
"""
web_app/routers/analisis.py
Módulo de Análisis: KPIs, tendencias, rankings de clientes y productos.
"""

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual

router = APIRouter(prefix="/analisis")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

ESTADO_COLOR = {
    "Pagada":     "#3b82f6",
    "Pendiente":  "#f59e0b",
    "Entregada":  "#22c55e",
    "Programada": "#a855f7",
    "Cancelada":  "#ef4444",
}


def _f(v):
    return float(v) if isinstance(v, Decimal) else (v if v is not None else 0)


@router.get("", response_class=HTMLResponse)
async def dashboard_analisis(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):

        # ── KPIs generales ────────────────────────────────────────────────
        cur.execute("""
            SELECT
                COUNT(*)                                          AS total_cots,
                COALESCE(SUM(total), 0)                          AS monto_total,
                COALESCE(SUM(total) FILTER (WHERE estado='Pagada'), 0)    AS cobrado,
                COALESCE(SUM(total) FILTER (WHERE estado='Pendiente'), 0) AS pendiente,
                COALESCE(SUM(total) FILTER (WHERE estado='Entregada'), 0) AS por_cobrar,
                COUNT(*) FILTER (WHERE estado='Pagada')           AS num_pagadas,
                COUNT(*) FILTER (WHERE estado='Cancelada')        AS num_canceladas
            FROM cotizaciones
        """)
        r = cur.fetchone()
        kpis = {
            "total_cots":    r[0],
            "monto_total":   _f(r[1]),
            "cobrado":       _f(r[2]),
            "pendiente":     _f(r[3]),
            "por_cobrar":    _f(r[4]),
            "num_pagadas":   r[5],
            "num_canceladas":r[6],
            "tasa_cobro":    round(_f(r[2]) / _f(r[1]) * 100, 1) if r[1] else 0,
        }

        # ── Tendencia mensual (últimos 12 meses) ─────────────────────────
        cur.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', fecha), 'Mon YY') AS mes_label,
                DATE_TRUNC('month', fecha)                    AS mes_ord,
                COUNT(*)                                      AS total,
                COALESCE(SUM(total), 0)                       AS monto,
                COUNT(*) FILTER (WHERE estado='Pagada')       AS pagadas,
                COALESCE(SUM(total) FILTER (WHERE estado='Pagada'), 0) AS monto_pagado
            FROM cotizaciones
            WHERE fecha >= NOW() - INTERVAL '12 months'
            GROUP BY mes_ord, mes_label
            ORDER BY mes_ord
        """)
        meses_raw = cur.fetchall()
        meses = [
            {"label": r[0], "total": r[2], "monto": _f(r[3]),
             "pagadas": r[4], "monto_pagado": _f(r[5])}
            for r in meses_raw
        ]

        # ── Por estado ────────────────────────────────────────────────────
        cur.execute("""
            SELECT estado, COUNT(*), COALESCE(SUM(total), 0)
            FROM cotizaciones
            GROUP BY estado
            ORDER BY SUM(total) DESC
        """)
        por_estado = [
            {"estado": r[0], "count": r[1], "monto": _f(r[2]),
             "color": ESTADO_COLOR.get(r[0], "#9ca3af")}
            for r in cur.fetchall()
        ]
        total_no_cancelado = sum(
            e["monto"] for e in por_estado if e["estado"] != "Cancelada"
        )

        # ── Top clientes ──────────────────────────────────────────────────
        cur.execute("""
            SELECT c.nombre_comercial, c.tipo,
                   COUNT(cot.id)          AS num_cots,
                   COALESCE(SUM(cot.total), 0) AS monto_total,
                   COALESCE(SUM(cot.total) FILTER (WHERE cot.estado='Pagada'), 0) AS cobrado
            FROM clientes c
            JOIN cotizaciones cot ON cot.cliente_id = c.id
            WHERE cot.estado != 'Cancelada'
            GROUP BY c.id
            ORDER BY monto_total DESC
            LIMIT 10
        """)
        top_clientes = [
            {"nombre": r[0], "tipo": r[1],
             "num_cots": r[2], "monto": _f(r[3]), "cobrado": _f(r[4])}
            for r in cur.fetchall()
        ]
        max_cliente = top_clientes[0]["monto"] if top_clientes else 1

        # ── Top productos ─────────────────────────────────────────────────
        cur.execute("""
            SELECT p.nombre,
                   COUNT(cd.id)                          AS apariciones,
                   COALESCE(SUM(cd.total), 0) AS monto
            FROM productos p
            JOIN cotizacion_detalle cd ON cd.producto_id = p.id
            JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
            WHERE cot.estado != 'Cancelada'
            GROUP BY p.id
            ORDER BY monto DESC
            LIMIT 10
        """)
        top_productos = [
            {"nombre": r[0], "apariciones": r[1], "monto": _f(r[2])}
            for r in cur.fetchall()
        ]
        max_producto = top_productos[0]["monto"] if top_productos else 1

        # ── Por tipo de cliente ───────────────────────────────────────────
        cur.execute("""
            SELECT c.tipo,
                   COUNT(DISTINCT c.id)      AS num_clientes,
                   COUNT(cot.id)             AS num_cots,
                   COALESCE(SUM(cot.total), 0) AS monto
            FROM clientes c
            JOIN cotizaciones cot ON cot.cliente_id = c.id
            WHERE cot.estado != 'Cancelada'
            GROUP BY c.tipo
            ORDER BY monto DESC
        """)
        por_tipo = [
            {"tipo": r[0], "clientes": r[1], "cots": r[2], "monto": _f(r[3])}
            for r in cur.fetchall()
        ]

    return templates.TemplateResponse(
        request=request,
        name="analisis/index.html",
        context={
            "user": user,
            "kpis": kpis,
            "meses": meses,
            "por_estado": por_estado,
            "total_no_cancelado": total_no_cancelado,
            "top_clientes": top_clientes,
            "max_cliente": max_cliente,
            "top_productos": top_productos,
            "max_producto": max_producto,
            "por_tipo": por_tipo,
            "seccion": "analisis",
        },
    )
