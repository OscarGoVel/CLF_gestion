# -*- coding: utf-8 -*-
"""
web_app/routers/api_dashboard.py
GET /api/dashboard — KPIs y bloques por rol para el SPA React.
"""

from decimal import Decimal
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/dashboard", tags=["api"])


def _serial(v):
    if isinstance(v, Decimal):
        return float(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _serial(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


@router.get("")
async def get_dashboard(user: dict = Depends(get_usuario_api)):
    rol = user.get("rol", "")
    empresa_db = user["empresa_db"]

    kpis: dict = {}
    bloques: dict = {}

    with get_pool_empresa(empresa_db).conexion() as (_, cur):

        if rol in ("Administrador", "Operador"):
            cur.execute("""
                SELECT
                    COALESCE(SUM(total) FILTER (WHERE estado IN (
                        'Programada','Parcialmente Entregada',
                        'Entregada','Facturada','Pagada'
                    )), 0)                                                AS monto_vendido,
                    COALESCE(SUM(total - COALESCE(monto_pagado, 0)) FILTER (
                        WHERE estado IN (
                            'Programada','Parcialmente Entregada',
                            'Entregada','Facturada'
                        ) AND (total - COALESCE(monto_pagado, 0)) > 0.01
                    ), 0)                                                 AS pendiente_cobrar,
                    COUNT(*) FILTER (WHERE estado = 'Pendiente')         AS num_pendientes,
                    COUNT(*) FILTER (WHERE estado = 'Programada')        AS num_programadas
                FROM cotizaciones
            """)
            r = cur.fetchone()
            kpis = {
                "monto_vendido":    _serial(r[0]),
                "pendiente_cobrar": _serial(r[1]),
                "num_pendientes":   r[2],
                "num_programadas":  r[3],
            }

            # Comercial: sin respuesta + sin OC
            cur.execute("""
                SELECT c.id, c.folio, c.fecha,
                       COALESCE(cl.nombre_comercial,'—') AS cliente, c.total
                FROM cotizaciones c
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.estado = 'Pendiente'
                  AND c.fecha < CURRENT_DATE - INTERVAL '15 days'
                ORDER BY c.fecha ASC
                LIMIT 20
            """)
            sin_respuesta = _rows(cur)

            cur.execute("""
                SELECT c.id, c.folio, c.fecha,
                       COALESCE(cl.nombre_comercial,'—') AS cliente, c.total
                FROM cotizaciones c
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.estado = 'Programada'
                  AND (c.orden_compra IS NULL OR c.orden_compra = '')
                ORDER BY c.fecha ASC
                LIMIT 20
            """)
            sin_oc = _rows(cur)
            bloques["comercial"] = {"sin_respuesta": sin_respuesta, "sin_oc": sin_oc}

        if rol in ("Administrador", "Operador", "Almacenista"):
            cur.execute("""
                SELECT DISTINCT c.id, c.folio, c.fecha_entrega,
                       COALESCE(cl.nombre_comercial,'—') AS cliente, c.total
                FROM cotizaciones c
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
                JOIN productos p ON p.id = cd.producto_id
                WHERE c.estado = 'Programada'
                  AND cd.cantidad > COALESCE(p.stock_actual, 0)
                ORDER BY c.fecha_entrega ASC NULLS LAST
                LIMIT 20
            """)
            sin_stock = _rows(cur)

            cur.execute("""
                SELECT c.id, c.folio, c.fecha_entrega,
                       COALESCE(cl.nombre_comercial,'—') AS cliente,
                       c.total, c.estado
                FROM cotizaciones c
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.estado IN ('Programada','Parcialmente Entregada')
                ORDER BY c.fecha_entrega ASC NULLS LAST
                LIMIT 20
            """)
            entregas_pendientes = _rows(cur)
            bloques["logistico"] = {
                "sin_stock": sin_stock,
                "entregas_pendientes": entregas_pendientes,
            }

        if rol == "Administrador":
            cur.execute("""
                SELECT c.id, c.folio, c.fecha,
                       COALESCE(cl.nombre_comercial,'—') AS cliente,
                       c.total, COALESCE(c.monto_pagado, 0) AS monto_pagado
                FROM cotizaciones c
                LEFT JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.estado = 'Entregada'
                  AND (c.monto_pagado IS NULL OR c.monto_pagado < c.total)
                  AND EXISTS (
                      SELECT 1 FROM facturas f WHERE f.cotizacion_id = c.id
                  )
                ORDER BY c.fecha ASC
                LIMIT 20
            """)
            facturas_sin_pago = _rows(cur)
            bloques["administrativo"] = {"facturas_sin_pago": facturas_sin_pago}

        # Embudo comercial: conteo y monto por estado (excluye Cancelada)
        cur.execute("""
            SELECT estado, COUNT(*) AS cnt,
                   COALESCE(SUM(total), 0) AS monto
            FROM cotizaciones
            WHERE estado != 'Cancelada'
            GROUP BY estado
        """)
        _ORDEN = ['Borrador','Pendiente','Programada','Parcialmente Entregada',
                  'Entregada','Facturada','Pagada']
        _por_estado = {r[0]: {"count": r[1], "monto": _serial(r[2])} for r in cur.fetchall()}
        embudo = [
            {"estado": e, "count": _por_estado.get(e, {}).get("count", 0),
             "monto": _por_estado.get(e, {}).get("monto", 0)}
            for e in _ORDEN if e in _por_estado
        ]
        _max = max((e["count"] for e in embudo), default=1)
        for e in embudo:
            e["pct"] = round(e["count"] / _max * 100)

        # Stock bajo reorden (stock_actual < stock_minimo, si existe columna)
        try:
            cur.execute("""
                SELECT codigo, nombre, COALESCE(stock_actual,0) AS stock,
                       COALESCE(stock_minimo, 0) AS minimo
                FROM productos
                WHERE stock_minimo IS NOT NULL
                  AND COALESCE(stock_actual,0) < stock_minimo
                ORDER BY (COALESCE(stock_actual,0) - stock_minimo) ASC
                LIMIT 10
            """)
            stock_bajo = _rows(cur)
        except Exception:
            stock_bajo = []

    return JSONResponse({
        "kpis": kpis,
        "bloques": bloques,
        "embudo": embudo,
        "stock_bajo": stock_bajo,
        "rol": rol,
    })
