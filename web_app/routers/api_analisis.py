# -*- coding: utf-8 -*-
"""
web_app/routers/api_analisis.py
GET /api/analisis — KPIs, tendencia mensual, rankings para el SPA React.
"""

import csv
import io
from datetime import date as _date
from decimal import Decimal
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

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

        # ── Tasa de conversión ────────────────────────────────────────────────
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE resultado = 'ganada')        AS ganadas,
                COUNT(*) FILTER (WHERE resultado = 'perdida')       AS perdidas,
                COUNT(*) FILTER (WHERE resultado = 'sin_respuesta') AS sin_respuesta,
                COUNT(*) FILTER (WHERE resultado IS NOT NULL)       AS con_resultado
            FROM cotizaciones
        """)
        cr = cur.fetchone()
        ganadas, perdidas = cr[0], cr[1]
        tasa_conv = round(ganadas / (ganadas + perdidas) * 100, 1) if (ganadas + perdidas) > 0 else None
        conversion = {
            "ganadas":       ganadas,
            "perdidas":      perdidas,
            "sin_respuesta": cr[2],
            "con_resultado": cr[3],
            "tasa":          tasa_conv,
        }

        # ── Motivos de pérdida ────────────────────────────────────────────────
        cur.execute("""
            SELECT COALESCE(motivo_perdida, 'sin_dato') AS motivo, COUNT(*) AS cnt
            FROM cotizaciones
            WHERE resultado = 'perdida'
            GROUP BY motivo_perdida
            ORDER BY cnt DESC
        """)
        total_perdidas = perdidas or 1
        motivos_perdida = [
            {"motivo": r[0], "count": r[1], "pct": round(r[1] / total_perdidas * 100, 1)}
            for r in cur.fetchall()
        ]

        # ── Aging de cartera global ───────────────────────────────────────────
        from datetime import date as _date
        hoy = _date.today().isoformat()
        cur.execute("""
            SELECT
                (%s::date - COALESCE(fecha_entrega, fecha)::date) AS dias,
                total - COALESCE(monto_pagado, 0) AS pendiente
            FROM cotizaciones
            WHERE estado IN ('Programada','Parcialmente Entregada','Entregada','Facturada')
              AND (total - COALESCE(monto_pagado, 0)) > 0.01
        """, (hoy,))
        aging = {"dias_0_30": 0.0, "dias_30_60": 0.0, "dias_60_90": 0.0, "dias_mas_90": 0.0}
        for dias, pend in cur.fetchall():
            d = float(dias or 0)
            p = _f(pend)
            if d <= 30:    aging["dias_0_30"]   += p
            elif d <= 60:  aging["dias_30_60"]  += p
            elif d <= 90:  aging["dias_60_90"]  += p
            else:          aging["dias_mas_90"] += p
        aging = {k: round(v, 2) for k, v in aging.items()}

        # ── DSO top 10 clientes ───────────────────────────────────────────────
        cur.execute("""
            SELECT cl.nombre_comercial,
                   AVG(c.fecha_pago - c.fecha_entrega) FILTER (
                       WHERE c.estado = 'Pagada'
                         AND c.fecha_pago IS NOT NULL
                         AND c.fecha_entrega IS NOT NULL
                   ) AS dso,
                   COUNT(*) FILTER (WHERE c.estado = 'Pagada') AS pagadas
            FROM clientes cl
            JOIN cotizaciones c ON c.cliente_id = cl.id
            GROUP BY cl.id, cl.nombre_comercial
            HAVING COUNT(*) FILTER (WHERE c.estado = 'Pagada') > 0
            ORDER BY dso DESC NULLS LAST
            LIMIT 10
        """)
        dso_clientes = [
            {"nombre": r[0], "dso": round(float(r[1]), 1) if r[1] else None, "pagadas": r[2]}
            for r in cur.fetchall()
        ]

        # ── Alertas de margen negativo ────────────────────────────────────────
        cur.execute("""
            SELECT cot.id, cot.folio, cot.estado,
                   cl.nombre_comercial                          AS cliente,
                   COALESCE(p.nombre, cd.descripcion_libre, 'Libre') AS producto,
                   cd.precio_unitario,
                   cd.costo_snapshot,
                   cd.margen_pct
            FROM cotizacion_detalle cd
            JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
            LEFT JOIN clientes cl ON cl.id = cot.cliente_id
            LEFT JOIN productos p ON p.id = cd.producto_id
            WHERE cd.margen_pct < 0
              AND cot.estado NOT IN ('Cancelada', 'Pagada')
            ORDER BY cd.margen_pct ASC
            LIMIT 30
        """)
        alertas_margen = [
            {
                "cot_id":   r[0],
                "folio":    r[1],
                "estado":   r[2],
                "cliente":  r[3] or "—",
                "producto": r[4],
                "precio":   round(_f(r[5]), 2),
                "costo":    round(_f(r[6]), 2),
                "margen":   round(_f(r[7]), 1),
            }
            for r in cur.fetchall()
        ]

        # ── Discriminación de precios por producto ────────────────────────────
        cur.execute("""
            SELECT p.nombre,
                   COUNT(DISTINCT cot.cliente_id)       AS num_clientes,
                   AVG(cd.precio_unitario)               AS precio_prom,
                   STDDEV(cd.precio_unitario)            AS desviacion,
                   MIN(cd.precio_unitario)               AS precio_min,
                   MAX(cd.precio_unitario)               AS precio_max
            FROM productos p
            JOIN cotizacion_detalle cd ON cd.producto_id = p.id
            JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
            WHERE cot.estado NOT IN ('Borrador','Cancelada')
              AND cd.precio_unitario > 0
            GROUP BY p.id, p.nombre
            HAVING COUNT(DISTINCT cot.cliente_id) > 1
               AND STDDEV(cd.precio_unitario) > 0
            ORDER BY STDDEV(cd.precio_unitario) / NULLIF(AVG(cd.precio_unitario), 0) DESC
            LIMIT 15
        """)
        discriminacion = [
            {
                "nombre":      r[0],
                "clientes":    r[1],
                "precio_prom": round(_f(r[2]), 2),
                "desviacion":  round(_f(r[3]), 2),
                "precio_min":  round(_f(r[4]), 2),
                "precio_max":  round(_f(r[5]), 2),
                "cv_pct":      round(_f(r[3]) / _f(r[2]) * 100, 1) if _f(r[2]) > 0 else 0,
            }
            for r in cur.fetchall()
        ]

    return JSONResponse({
        "kpis":            kpis,
        "meses":           meses,
        "por_estado":      por_estado,
        "top_clientes":    top_clientes,
        "top_productos":   top_productos,
        "por_tipo":        por_tipo,
        "conversion":      conversion,
        "motivos_perdida": motivos_perdida,
        "aging":           aging,
        "dso_clientes":    dso_clientes,
        "discriminacion":  discriminacion,
        "alertas_margen":  alertas_margen,
    })


# ── GET /api/analisis/pnl-mensual ─────────────────────────────────────────────

@router.get("/pnl-mensual")
async def pnl_mensual(user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT
                TO_CHAR(DATE_TRUNC('month', cot.fecha), 'YYYY-MM') AS periodo,
                TO_CHAR(DATE_TRUNC('month', cot.fecha), 'Mon YY')  AS mes_label,
                DATE_TRUNC('month', cot.fecha)                      AS mes_ord,
                COALESCE(SUM(cot.total), 0)                         AS revenue,
                COALESCE(SUM(COALESCE(cd.costo_snapshot, 0) * cd.cantidad), 0) AS cogs
            FROM cotizaciones cot
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = cot.id
            WHERE cot.estado IN %s
              AND cot.fecha >= NOW() - INTERVAL '12 months'
            GROUP BY periodo, mes_label, mes_ord
            ORDER BY mes_ord
        """, (ESTADOS_VENTA,))
        meses_raw = {}
        for r in cur.fetchall():
            meses_raw[r[0]] = {"periodo": r[0], "label": r[1], "revenue": _f(r[3]), "cogs": _f(r[4])}

        cur.execute("SELECT periodo, COALESCE(SUM(monto), 0) FROM costos_fijos GROUP BY periodo")
        fijos_por_periodo = {r[0]: _f(r[1]) for r in cur.fetchall()}

    result = []
    for periodo in sorted(meses_raw):
        mes   = meses_raw[periodo]
        fijos = fijos_por_periodo.get(periodo, 0.0)
        gp    = mes["revenue"] - mes["cogs"]
        np_   = gp - fijos
        result.append({
            "periodo":      periodo,
            "label":        mes["label"],
            "revenue":      round(mes["revenue"], 2),
            "cogs":         round(mes["cogs"], 2),
            "gp":           round(gp, 2),
            "gp_pct":       round(gp / mes["revenue"] * 100, 1) if mes["revenue"] else 0,
            "costos_fijos": round(fijos, 2),
            "np":           round(np_, 2),
            "np_pct":       round(np_ / mes["revenue"] * 100, 1) if mes["revenue"] else 0,
        })

    totales = {
        "revenue":      sum(m["revenue"]      for m in result),
        "cogs":         sum(m["cogs"]         for m in result),
        "gp":           sum(m["gp"]           for m in result),
        "costos_fijos": sum(m["costos_fijos"] for m in result),
        "np":           sum(m["np"]           for m in result),
    }
    return JSONResponse({"meses": result, "totales": totales})


# ── GET /api/analisis/forecast ────────────────────────────────────────────────

def _add_months(d, n):
    month = d.month - 1 + n
    year  = d.year + month // 12
    month = month % 12 + 1
    return d.replace(year=year, month=month, day=1)


@router.get("/forecast")
async def forecast(user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT
                DATE_TRUNC('month', fecha)                         AS mes_ord,
                TO_CHAR(DATE_TRUNC('month', fecha), 'Mon YY')      AS label,
                COALESCE(SUM(total), 0)                            AS monto
            FROM cotizaciones
            WHERE estado IN %s
              AND fecha >= NOW() - INTERVAL '6 months'
            GROUP BY mes_ord, label
            ORDER BY mes_ord
        """, (ESTADOS_VENTA,))
        historial = [{"label": r[1], "monto": _f(r[2])} for r in cur.fetchall()]

    if len(historial) < 2:
        return JSONResponse({"historial": historial, "proyeccion": [], "tendencia": None})

    n      = len(historial)
    xs     = list(range(1, n + 1))
    ys     = [m["monto"] for m in historial]
    sx     = sum(xs);  sy  = sum(ys)
    sxy    = sum(x * y for x, y in zip(xs, ys))
    sx2    = sum(x * x for x in xs)
    denom  = n * sx2 - sx * sx
    slope  = (n * sxy - sx * sy) / denom if denom else 0
    intercept = (sy - slope * sx) / n

    hoy = _date.today().replace(day=1)
    MES_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

    proyeccion = []
    for i in range(1, 4):
        val   = max(0.0, intercept + slope * (n + i))
        fecha = _add_months(hoy, i)
        label = f"{MES_ES[fecha.month - 1]} {str(fecha.year)[2:]}"
        proyeccion.append({"label": label, "monto": round(val, 2)})

    tendencia = "creciente" if slope > 0 else "decreciente" if slope < 0 else "estable"
    return JSONResponse({
        "historial":  historial,
        "proyeccion": proyeccion,
        "tendencia":  tendencia,
        "slope":      round(slope, 2),
    })


# ── GET /api/analisis/aging-export ────────────────────────────────────────────

@router.get("/aging-export")
async def aging_export(user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    hoy = _date.today().isoformat()

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT
                cot.folio,
                COALESCE(cl.nombre_comercial, '—') AS cliente,
                cot.estado,
                cot.fecha::text,
                COALESCE(cot.fecha_entrega::text, ''),
                ROUND(cot.total - COALESCE(cot.monto_pagado, 0), 2) AS pendiente,
                (%s::date - COALESCE(cot.fecha_entrega, cot.fecha)::date) AS dias
            FROM cotizaciones cot
            LEFT JOIN clientes cl ON cl.id = cot.cliente_id
            WHERE cot.estado IN ('Programada','Parcialmente Entregada','Entregada','Facturada')
              AND (cot.total - COALESCE(cot.monto_pagado, 0)) > 0.01
            ORDER BY dias DESC NULLS LAST
        """, (hoy,))
        rows = cur.fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Folio", "Cliente", "Estado", "Fecha cot.", "Fecha entrega", "Pendiente MXN", "Días"])
    for r in rows:
        writer.writerow([v if v is not None else '' for v in r])

    content = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="aging_{hoy}.csv"'},
    )
