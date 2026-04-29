# -*- coding: utf-8 -*-
"""
web_app/routers/analisis.py
Módulo de Análisis: KPIs, tendencias, rankings de clientes y productos.
"""

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_actual
from core.constants import ESTADO_COLOR_HEX as ESTADO_COLOR

router = APIRouter(prefix="/analisis")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


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
                COUNT(*) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'
                ))                                                          AS total_cots,
                COALESCE(SUM(total) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'
                )), 0)                                                      AS monto_total,
                COALESCE(SUM(COALESCE(monto_pagado, 0)) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'
                )), 0)                                                      AS cobrado,
                COALESCE(SUM(total - COALESCE(monto_pagado, 0)) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada'
                ) AND (total - COALESCE(monto_pagado, 0)) > 0.01), 0)     AS pendiente_cobro,
                COUNT(*) FILTER (WHERE estado='Pagada')                    AS num_pagadas,
                COUNT(*) FILTER (WHERE estado='Cancelada')                 AS num_canceladas
            FROM cotizaciones
        """)
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

        # ── Tendencia mensual (últimos 12 meses) ─────────────────────────
        cur.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', fecha), 'Mon YY') AS mes_label,
                DATE_TRUNC('month', fecha)                    AS mes_ord,
                COUNT(*) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'
                ))                                            AS total,
                COALESCE(SUM(total) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'
                )), 0)                                        AS monto,
                COUNT(*) FILTER (WHERE estado='Pagada')       AS pagadas,
                COALESCE(SUM(COALESCE(monto_pagado,0)) FILTER (WHERE estado IN (
                    'Programada','Parcialmente Entregada',
                    'Entregada','Facturada','Pagada'
                )), 0)                                        AS monto_pagado
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
                   COALESCE(SUM(cot.total) FILTER (WHERE cot.estado IN (
                       'Programada','Parcialmente Entregada',
                       'Entregada','Facturada','Pagada'
                   )), 0) AS monto_total,
                   COALESCE(SUM(COALESCE(cot.monto_pagado, 0)) FILTER (WHERE cot.estado IN (
                       'Programada','Parcialmente Entregada',
                       'Entregada','Facturada','Pagada'
                   )), 0) AS cobrado
            FROM clientes c
            JOIN cotizaciones cot ON cot.cliente_id = c.id
            WHERE cot.estado IN (
                'Programada','Parcialmente Entregada',
                'Entregada','Facturada','Pagada'
            )
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


@router.get("/costos", response_class=HTMLResponse)
async def analisis_costos(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403, detail="Solo administradores")

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):

        # ── KPIs globales de costo ────────────────────────────────────────
        # Solo estados que representan ventas confirmadas o cerradas
        _ESTADOS_COSTO = ('Programada', 'Entregada', 'Facturada', 'Pagada')
        cur.execute("""
            SELECT
                COUNT(DISTINCT c.id)                                     AS total_cots,
                COALESCE(SUM(cd.costo_snapshot * cd.cantidad), 0)        AS costo_snap_total,
                COALESCE(SUM(cd.precio_unitario * cd.cantidad), 0)       AS venta_total
            FROM cotizaciones c
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            WHERE c.estado IN %s
        """, (_ESTADOS_COSTO,))
        r = cur.fetchone()
        total_cots    = r[0] or 0
        costo_snap_total = _f(r[1])
        venta_total      = _f(r[2])

        cur.execute("""
            SELECT COUNT(DISTINCT cdc.cotizacion_id)
            FROM compra_detalle_cotizacion cdc
            JOIN cotizaciones c ON c.id = cdc.cotizacion_id
            WHERE c.estado IN %s
        """, (_ESTADOS_COSTO,))
        con_costo_real = cur.fetchone()[0] or 0
        sin_costo_real = total_cots - con_costo_real

        margen_snap_global = round(
            (venta_total - costo_snap_total) / venta_total * 100, 1
        ) if venta_total else 0
        utilidad_snap = round(venta_total - costo_snap_total, 2)

        # ── Margen real cerrado: solo Entregadas/Pagadas con compras vinculadas ──
        cur.execute("""
            SELECT
                COALESCE(SUM(cd.precio_unitario * cd.cantidad), 0) AS venta_cerrada
            FROM cotizaciones c
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            WHERE c.estado IN ('Entregada','Facturada','Pagada')
              AND EXISTS (
                  SELECT 1 FROM compra_detalle_cotizacion cdc2
                  WHERE cdc2.cotizacion_id = c.id
              )
        """)
        venta_cerrada = _f(cur.fetchone()[0])

        cur.execute("""
            SELECT
                COALESCE(SUM(
                    costo_real.costo_prom * cd.cantidad
                ), 0) AS costo_real_cerrado
            FROM cotizaciones c
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            JOIN (
                SELECT cdc.cotizacion_id, comp.producto_id,
                       SUM(comp.costo_unitario * cdc.cantidad) / NULLIF(SUM(cdc.cantidad), 0)
                           AS costo_prom
                FROM compra_detalle_cotizacion cdc
                JOIN compra_detalle comp ON comp.id = cdc.compra_detalle_id
                GROUP BY cdc.cotizacion_id, comp.producto_id
            ) costo_real ON costo_real.cotizacion_id = c.id
                         AND costo_real.producto_id  = cd.producto_id
            WHERE c.estado IN ('Entregada','Facturada','Pagada')
        """)
        costo_real_cerrado = _f(cur.fetchone()[0])

        margen_real_cerrado = round(
            (venta_cerrada - costo_real_cerrado) / venta_cerrada * 100, 1
        ) if venta_cerrada else None
        utilidad_real_cerrada = round(venta_cerrada - costo_real_cerrado, 2)

        kpis_costos = {
            "venta_total":          venta_total,
            "costo_snap_total":     costo_snap_total,
            "utilidad_snap":        utilidad_snap,
            "margen_snap":          margen_snap_global,
            "sin_costo_real":       sin_costo_real,
            "con_costo_real":       con_costo_real,
            "total_cots":           total_cots,
            # Métricas de costo real confirmado (solo entregadas con compras)
            "venta_cerrada":        venta_cerrada,
            "costo_real_cerrado":   costo_real_cerrado,
            "utilidad_real":        utilidad_real_cerrada,
            "margen_real":          margen_real_cerrado,
        }

        # ── Tendencia mensual venta vs costo (12 meses) ──────────────────
        cur.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', c.fecha), 'Mon YY')         AS mes_label,
                DATE_TRUNC('month', c.fecha)                            AS mes_ord,
                COALESCE(SUM(cd.precio_unitario * cd.cantidad), 0)      AS venta,
                COALESCE(SUM(cd.costo_snapshot * cd.cantidad), 0)       AS costo_snap
            FROM cotizaciones c
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            WHERE c.fecha >= NOW() - INTERVAL '12 months'
              AND c.estado IN %s
            GROUP BY mes_ord, mes_label
            ORDER BY mes_ord
        """, (_ESTADOS_COSTO,))
        tendencia = [
            {"label": r[0], "venta": _f(r[2]), "costo_snap": _f(r[3])}
            for r in cur.fetchall()
        ]

        # ── Lista de cotizaciones con márgenes ────────────────────────────
        cur.execute("""
            SELECT
                c.id,
                c.folio,
                c.fecha,
                c.estado,
                COALESCE(cl.nombre_comercial, '—')                      AS cliente,
                COALESCE(SUM(cd.precio_unitario * cd.cantidad), 0)      AS venta_sub,
                COALESCE(SUM(cd.costo_snapshot * cd.cantidad), 0)       AS costo_snap_sum,
                EXISTS(
                    SELECT 1 FROM compra_detalle_cotizacion cdc
                    WHERE cdc.cotizacion_id = c.id
                )                                                        AS tiene_compras
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            WHERE c.estado IN %s
            GROUP BY c.id, c.folio, c.fecha, c.estado, cl.nombre_comercial
            ORDER BY c.fecha DESC
            LIMIT 60
        """, (_ESTADOS_COSTO,))
        cols = [d[0] for d in cur.description]
        lista_cots = []
        for row in cur.fetchall():
            d = dict(zip(cols, row))
            d["venta_sub"]      = _f(d["venta_sub"])
            d["costo_snap_sum"] = _f(d["costo_snap_sum"])
            d["fecha"]          = str(d["fecha"]) if d["fecha"] else ""
            if d["venta_sub"] > 0:
                d["margen_snap"] = round(
                    (d["venta_sub"] - d["costo_snap_sum"]) / d["venta_sub"] * 100, 1
                )
            else:
                d["margen_snap"] = None
            lista_cots.append(d)

    return templates.TemplateResponse(
        request=request,
        name="analisis/costos.html",
        context={
            "user":        user,
            "kpis":        kpis_costos,
            "tendencia":   tendencia,
            "lista_cots":  lista_cots,
            "seccion":     "costos",
            "ESTADO_COLOR": ESTADO_COLOR,
        },
    )
