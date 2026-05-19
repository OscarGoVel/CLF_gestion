# -*- coding: utf-8 -*-
"""
web_app/routers/api_estado_cuenta.py
/api/estado-cuenta — endpoints JSON para el SPA React.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/estado-cuenta", tags=["api"])

_ESTADOS_ACTIVOS = ('Programada', 'Parcialmente Entregada', 'Entregada', 'Facturada', 'Pagada')


def _s(v):
    if isinstance(v, Decimal): return float(v)
    if hasattr(v, "isoformat"): return v.isoformat()
    return v


def _rows(cur):
    cols = [d[0] for d in cur.description]
    return [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ── GET /api/estado-cuenta ────────────────────────────────────────────────────

@router.get("")
async def listar(
    corporativo_id: int = Query(0),
    tipo: str = Query(""),
    desde: str = Query(""),
    hasta: str = Query(""),
    user: dict = Depends(get_usuario_api),
):
    _ph = ", ".join(["%s"] * len(_ESTADOS_ACTIVOS))
    where = [f"c.estado IN ({_ph})"]
    params: list = list(_ESTADOS_ACTIVOS)

    if corporativo_id:
        where.append("cl.corporativo_id = %s")
        params.append(corporativo_id)
    if tipo:
        where.append("cl.tipo = %s")
        params.append(tipo)
    if desde:
        where.append("c.fecha_entrega >= %s")
        params.append(desde)
    if hasta:
        where.append("c.fecha_entrega <= %s")
        params.append(hasta)

    w = " AND ".join(where)

    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute(f"""
            SELECT
                cl.id                                               AS cliente_id,
                cl.nombre_comercial                                 AS nombre,
                cl.tipo,
                cl.rfc,
                corp.nombre                                         AS corporativo,
                SUM(c.total)                                        AS cartera,
                SUM(COALESCE(c.monto_pagado, 0))                    AS cobrado,
                SUM(c.total - COALESCE(c.monto_pagado, 0))          AS pendiente,
                AVG(
                    EXTRACT(EPOCH FROM (c.fecha_pago - c.fecha_entrega)) / 86400.0
                ) FILTER (
                    WHERE c.estado = 'Pagada'
                      AND c.fecha_pago IS NOT NULL
                      AND c.fecha_entrega IS NOT NULL
                )                                                   AS dso
            FROM clientes cl
            JOIN cotizaciones c ON c.cliente_id = cl.id
            LEFT JOIN corporativos corp ON corp.id = cl.corporativo_id
            WHERE {w}
            GROUP BY cl.id, cl.nombre_comercial, cl.tipo, cl.rfc, corp.nombre
            HAVING SUM(c.total - COALESCE(c.monto_pagado, 0)) > 0.01
            ORDER BY pendiente DESC
        """, params)
        clientes = _rows(cur)

        # KPIs globales
        cur.execute(f"""
            SELECT
                SUM(c.total)                                    AS cartera_total,
                SUM(COALESCE(c.monto_pagado, 0))                AS cobrado_total,
                SUM(c.total - COALESCE(c.monto_pagado, 0))      AS pendiente_total,
                AVG(
                    EXTRACT(EPOCH FROM (c.fecha_pago - c.fecha_entrega)) / 86400.0
                ) FILTER (
                    WHERE c.estado = 'Pagada'
                      AND c.fecha_pago IS NOT NULL
                      AND c.fecha_entrega IS NOT NULL
                )                                               AS dso_global
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE {w}
        """, params)
        r = cur.fetchone()
        kpis = {
            "cartera_total":   _s(r[0]) or 0,
            "cobrado_total":   _s(r[1]) or 0,
            "pendiente_total": _s(r[2]) or 0,
            "dso_global":      round(_s(r[3]), 1) if r[3] else None,
        }

    return {"clientes": clientes, "kpis": kpis}


# ── GET /api/estado-cuenta/corporativos ──────────────────────────────────────

@router.get("/corporativos")
async def listar_corporativos(user: dict = Depends(get_usuario_api)):
    with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
        cur.execute("SELECT id, nombre FROM corporativos ORDER BY nombre")
        corps = _rows(cur)
    return {"corporativos": corps}


# ── GET /api/estado-cuenta/{cliente_id} ──────────────────────────────────────

@router.get("/{cliente_id}")
async def detalle(
    cliente_id: int,
    user: dict = Depends(get_usuario_api),
):
    hoy = date.today()
    empresa_db = user["empresa_db"]

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        # Datos del cliente
        cur.execute("""
            SELECT cl.id, cl.nombre_comercial, cl.razon_social, cl.tipo,
                   cl.rfc, cl.contacto, cl.telefono, cl.email,
                   corp.nombre AS corporativo
            FROM clientes cl
            LEFT JOIN corporativos corp ON corp.id = cl.corporativo_id
            WHERE cl.id = %s
        """, (cliente_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        cols = ["id", "nombre_comercial", "razon_social", "tipo",
                "rfc", "contacto", "telefono", "email", "corporativo"]
        cliente = {k: _s(v) for k, v in zip(cols, row)}

        # Cotizaciones activas del cliente
        cur.execute("""
            SELECT
                c.id, c.folio,
                c.fecha_entrega,
                c.total,
                COALESCE(c.monto_pagado, 0)                      AS pagado,
                c.total - COALESCE(c.monto_pagado, 0)            AS pendiente,
                c.estado,
                c.fecha_pago,
                CASE
                    WHEN c.fecha_entrega IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (%s::date - c.fecha_entrega::date)) / 86400.0
                    ELSE NULL
                END                                               AS dias_desde_entrega
            FROM cotizaciones c
            WHERE c.cliente_id = %s
              AND c.estado IN ({})
            ORDER BY c.fecha_entrega DESC NULLS LAST
        """.format(", ".join(["%s"] * len(_ESTADOS_ACTIVOS))),
        (hoy.isoformat(), cliente_id, *_ESTADOS_ACTIVOS))
        cotizaciones = _rows(cur)

        # KPIs del cliente
        cur.execute("""
            SELECT
                SUM(c.total)                        AS cartera,
                SUM(COALESCE(c.monto_pagado, 0))    AS cobrado,
                AVG(
                    EXTRACT(EPOCH FROM (c.fecha_pago - c.fecha_entrega)) / 86400.0
                ) FILTER (
                    WHERE c.estado = 'Pagada'
                      AND c.fecha_pago IS NOT NULL
                      AND c.fecha_entrega IS NOT NULL
                )                                   AS dso
            FROM cotizaciones c
            WHERE c.cliente_id = %s AND c.estado IN ({})
        """.format(", ".join(["%s"] * len(_ESTADOS_ACTIVOS))),
        (cliente_id, *_ESTADOS_ACTIVOS))
        kr = cur.fetchone()
        cartera = _s(kr[0]) or 0
        cobrado = _s(kr[1]) or 0

    # Aging: bucket por días_desde_entrega de cada cotización pendiente
    aging = {"dias_0_30": 0.0, "dias_30_60": 0.0, "dias_60_90": 0.0, "dias_mas_90": 0.0}
    for c in cotizaciones:
        p = c.get("pendiente") or 0
        if p <= 0:
            continue
        d = c.get("dias_desde_entrega")
        if d is None:
            aging["dias_0_30"] += p
        elif d <= 30:
            aging["dias_0_30"] += p
        elif d <= 60:
            aging["dias_30_60"] += p
        elif d <= 90:
            aging["dias_60_90"] += p
        else:
            aging["dias_mas_90"] += p

    aging = {k: round(v, 2) for k, v in aging.items()}

    return {
        "cliente": cliente,
        "kpis": {
            "cartera":  round(cartera, 2),
            "cobrado":  round(cobrado, 2),
            "pendiente": round(cartera - cobrado, 2),
            "dso":      round(_s(kr[2]), 1) if kr[2] else None,
        },
        "aging": aging,
        "cotizaciones": cotizaciones,
    }


# ── POST /api/estado-cuenta/pdf ───────────────────────────────────────────────

@router.post("/pdf")
async def exportar_pdf(
    body: dict,
    user: dict = Depends(get_usuario_api),
):
    cliente_id = body.get("cliente_id")
    if not cliente_id:
        raise HTTPException(status_code=422, detail="cliente_id requerido")

    filtros = {
        "cliente_id": cliente_id,
        "desde": body.get("desde", ""),
        "hasta": body.get("hasta", ""),
    }

    try:
        from web_app.pdf_estado_cuenta import generar_pdf_estado_cuenta

        # Adaptar filtros al formato que espera el generador legacy
        with get_pool_empresa(user["empresa_db"]).conexion() as (_, cur):
            cur.execute("SELECT nombre_comercial FROM clientes WHERE id = %s", (cliente_id,))
            row = cur.fetchone()
            nombre = row[0] if row else str(cliente_id)

        filtros_pdf = {
            "cliente_nombre": nombre,
            "desde": filtros["desde"] or f"{date.today().year}-01-01",
            "hasta": filtros["hasta"] or date.today().isoformat(),
            "estado": "Todos",
        }
        pdf_bytes = generar_pdf_estado_cuenta(user["empresa_db"], filtros_pdf)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"EstadoCuenta_{nombre}_{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
