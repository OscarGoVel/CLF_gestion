# -*- coding: utf-8 -*-
"""
web_app/routers/api_analisis.py
GET /api/analisis — KPIs, tendencia mensual, rankings para el SPA React.
"""

from decimal import Decimal
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/analisis", tags=["api"])

ESTADO_COLOR = {
    "Pendiente":              "#f59e0b",
    "Programada":             "#a855f7",
    "Parcialmente Entregada": "#8b5cf6",
    "Entregada":              "#22c55e",
    "Facturada":              "#06b6d4",
    "Pagada":                 "#3b82f6",
    "Cancelada":              "#ef4444",
}

ESTADOS_VENTA = (
    'Programada', 'Parcialmente Entregada', 'Entregada', 'Facturada', 'Pagada'
)


def _f(v) -> float:
    if isinstance(v, Decimal):
        return float(v)
    return float(v) if v is not None else 0.0


@router.get("")
async def get_analisis(user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]

    with get_pool_empresa(empresa_db).conexion() as (_, cur):

        # ── KPIs globales ─────────────────────────────────────────────────────
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE estado IN %s)                        AS total_cots,
                COALESCE(SUM(total) FILTER (WHERE estado IN %s), 0)         AS monto_total,
                COALESCE(SUM(COALESCE(monto_pagado,0)) FILTER (WHERE estado IN %s), 0) AS cobrado,
                COALESCE(SUM(total - COALESCE(monto_pagado,0)) FILTER (
                    WHERE estado IN ('Programada','Parcialmente Entregada','Entregada','Facturada')
                    AND (total - COALESCE(monto_pagado,0)) > 0.01
                ), 0)                                                        AS pendiente_cobro,
                COUNT(*) FILTER (WHERE estado='Pagada')                     AS num_pagadas,
                COUNT(*) FILTER (WHERE estado='Cancelada')                  AS num_canceladas
            FROM cotizaciones
        """, (ESTADOS_VENTA, ESTADOS_VENTA, ESTADOS_VENTA))
        r = cur.fetchone()
        monto_total = _f(r[1])
        cobrado     = _f(r[2])
        kpis = {
            "total_cots":      r[0],
            "monto_total":     monto_total,
            "cobrado":         cobrado,
            "pendiente_cobro": _f(r[3]),
            "num_pagadas":     r[4],
            "num_canceladas":  r[5],
            "tasa_cobro":      round(cobrado / monto_total * 100, 1) if monto_total else 0,
        }

        # ── Tendencia mensual (últimos 12 meses) ──────────────────────────────
        cur.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', fecha), 'Mon YY')   AS mes_label,
                DATE_TRUNC('month', fecha)                       AS mes_ord,
                COUNT(*) FILTER (WHERE estado IN %s)             AS total,
                COALESCE(SUM(total) FILTER (WHERE estado IN %s), 0) AS monto,
                COUNT(*) FILTER (WHERE estado='Pagada')          AS pagadas,
                COALESCE(SUM(COALESCE(monto_pagado,0)) FILTER (WHERE estado IN %s), 0) AS cobrado
            FROM cotizaciones
            WHERE fecha >= NOW() - INTERVAL '12 months'
            GROUP BY mes_ord, mes_label
            ORDER BY mes_ord
        """, (ESTADOS_VENTA, ESTADOS_VENTA, ESTADOS_VENTA))
        meses = [
            {"label": r[0], "total": r[2], "monto": _f(r[3]),
             "pagadas": r[4], "cobrado": _f(r[5])}
            for r in cur.fetchall()
        ]

        # ── Por estado ────────────────────────────────────────────────────────
        cur.execute("""
            SELECT estado, COUNT(*), COALESCE(SUM(total), 0)
            FROM cotizaciones
            GROUP BY estado
            ORDER BY SUM(total) DESC NULLS LAST
        """)
        por_estado = [
            {"estado": r[0], "count": r[1], "monto": _f(r[2]),
             "color": ESTADO_COLOR.get(r[0], "#9ca3af")}
            for r in cur.fetchall()
        ]

        # ── Top 10 clientes ───────────────────────────────────────────────────
        cur.execute("""
            SELECT c.nombre_comercial, c.tipo,
                   COUNT(cot.id)                                             AS num_cots,
                   COALESCE(SUM(cot.total) FILTER (WHERE cot.estado IN %s), 0)  AS monto,
                   COALESCE(SUM(COALESCE(cot.monto_pagado,0)) FILTER (WHERE cot.estado IN %s), 0) AS cobrado
            FROM clientes c
            JOIN cotizaciones cot ON cot.cliente_id = c.id
            WHERE cot.estado IN %s
            GROUP BY c.id
            ORDER BY monto DESC
            LIMIT 10
        """, (ESTADOS_VENTA, ESTADOS_VENTA, ESTADOS_VENTA))
        top_clientes = [
            {"nombre": r[0], "tipo": r[1], "num_cots": r[2],
             "monto": _f(r[3]), "cobrado": _f(r[4])}
            for r in cur.fetchall()
        ]

        # ── Top 10 productos ──────────────────────────────────────────────────
        cur.execute("""
            SELECT p.nombre,
                   COUNT(cd.id)                    AS apariciones,
                   COALESCE(SUM(cd.total), 0)      AS monto
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

        # ── Por tipo de cliente ───────────────────────────────────────────────
        cur.execute("""
            SELECT c.tipo,
                   COUNT(DISTINCT c.id)            AS num_clientes,
                   COUNT(cot.id)                   AS num_cots,
                   COALESCE(SUM(cot.total), 0)     AS monto
            FROM clientes c
            JOIN cotizaciones cot ON cot.cliente_id = c.id
            WHERE cot.estado != 'Cancelada'
            GROUP BY c.tipo
            ORDER BY monto DESC
        """)
        por_tipo = [
            {"tipo": r[0] or "Sin tipo", "clientes": r[1], "cots": r[2], "monto": _f(r[3])}
            for r in cur.fetchall()
        ]

    return JSONResponse({
        "kpis":         kpis,
        "meses":        meses,
        "por_estado":   por_estado,
        "top_clientes": top_clientes,
        "top_productos": top_productos,
        "por_tipo":     por_tipo,
    })
