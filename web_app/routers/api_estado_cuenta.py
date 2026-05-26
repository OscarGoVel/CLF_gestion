# -*- coding: utf-8 -*-
"""
web_app/routers/api_estado_cuenta.py
/api/estado-cuenta — endpoints JSON para el SPA React.
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from web_app.database import get_pool_empresa
from web_app.dependencies import get_usuario_api

router = APIRouter(prefix="/api/finanzas/cobranza", tags=["api"])

_ESTADOS_ACTIVOS = ('Programada', 'Parcialmente Entregada', 'Entregada', 'Facturada')


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
                AVG(CURRENT_DATE - c.fecha_entrega) FILTER (
                    WHERE c.fecha_entrega IS NOT NULL
                      AND c.total - COALESCE(c.monto_pagado, 0) > 0
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
                AVG(CURRENT_DATE - c.fecha_entrega) FILTER (
                    WHERE c.fecha_entrega IS NOT NULL
                      AND c.total - COALESCE(c.monto_pagado, 0) > 0
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


# ── GET /api/estado-cuenta/export-pdf ────────────────────────────────────────

@router.get("/export-pdf")
async def exportar_aging_pdf(
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
                cl.nombre_comercial,
                cl.tipo,
                COALESCE(corp.nombre, '—')                          AS corporativo,
                SUM(c.total)                                        AS cartera,
                SUM(COALESCE(c.monto_pagado, 0))                    AS cobrado,
                SUM(c.total - COALESCE(c.monto_pagado, 0))          AS pendiente,
                AVG(CURRENT_DATE - c.fecha_entrega) FILTER (
                    WHERE c.fecha_entrega IS NOT NULL
                      AND c.total - COALESCE(c.monto_pagado, 0) > 0
                )                                                   AS dso
            FROM clientes cl
            JOIN cotizaciones c ON c.cliente_id = cl.id
            LEFT JOIN corporativos corp ON corp.id = cl.corporativo_id
            WHERE {w}
            GROUP BY cl.id, cl.nombre_comercial, cl.tipo, corp.nombre
            HAVING SUM(c.total - COALESCE(c.monto_pagado, 0)) > 0.01
            ORDER BY pendiente DESC
        """, params)
        clientes = _rows(cur)

        cur.execute(f"""
            SELECT
                SUM(c.total)                                    AS cartera_total,
                SUM(COALESCE(c.monto_pagado, 0))                AS cobrado_total,
                SUM(c.total - COALESCE(c.monto_pagado, 0))      AS pendiente_total,
                AVG(CURRENT_DATE - c.fecha_entrega) FILTER (
                    WHERE c.fecha_entrega IS NOT NULL
                      AND c.total - COALESCE(c.monto_pagado, 0) > 0
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

    pdf_bytes = _generar_pdf_aging(clientes, kpis, desde, hasta)
    fecha_str = date.today().isoformat()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="aging_cartera_{fecha_str}.pdf"'},
    )


def _generar_pdf_aging(clientes: list, kpis: dict, desde: str, hasta: str) -> bytes:
    import io
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
        topMargin=0.6 * inch, bottomMargin=0.5 * inch,
    )

    _AZUL   = colors.HexColor('#1e3a5f')
    _ROJO   = colors.HexColor('#dc2626')
    _GRIS   = colors.HexColor('#f1f5f9')
    _LINEA  = colors.HexColor('#cbd5e1')
    _BLANCO = colors.white

    def _mxn(v):
        return f"${float(v or 0):,.0f}"

    def _dso(v):
        return f"{int(round(float(v)))} d" if v else "—"

    title_style = ParagraphStyle("title", fontSize=16, textColor=_AZUL,
                                  fontName="Helvetica-Bold", spaceAfter=4)
    sub_style   = ParagraphStyle("sub",   fontSize=9,  textColor=colors.HexColor('#64748b'),
                                  fontName="Helvetica",  spaceAfter=12)

    elements = []

    elements.append(Paragraph("Estado de Cuenta — Cartera Global", title_style))
    subtitulo = f"Generado el {date.today().strftime('%d/%m/%Y')}"
    if desde or hasta:
        rango = []
        if desde: rango.append(f"desde {desde}")
        if hasta: rango.append(f"hasta {hasta}")
        subtitulo += "   |   Entrega " + " ".join(rango)
    elements.append(Paragraph(subtitulo, sub_style))

    # KPIs
    kpi_data = [[
        Paragraph("Cartera total", ParagraphStyle("k", fontSize=8, textColor=colors.HexColor('#64748b'), fontName="Helvetica")),
        Paragraph("Cobrado", ParagraphStyle("k", fontSize=8, textColor=colors.HexColor('#64748b'), fontName="Helvetica")),
        Paragraph("Pendiente", ParagraphStyle("k", fontSize=8, textColor=colors.HexColor('#64748b'), fontName="Helvetica")),
        Paragraph("DSO promedio", ParagraphStyle("k", fontSize=8, textColor=colors.HexColor('#64748b'), fontName="Helvetica")),
    ], [
        Paragraph(_mxn(kpis["cartera_total"]),   ParagraphStyle("v", fontSize=14, fontName="Helvetica-Bold")),
        Paragraph(_mxn(kpis["cobrado_total"]),   ParagraphStyle("v", fontSize=14, fontName="Helvetica-Bold")),
        Paragraph(_mxn(kpis["pendiente_total"]), ParagraphStyle("v", fontSize=14, fontName="Helvetica-Bold", textColor=_ROJO)),
        Paragraph(_dso(kpis["dso_global"]),      ParagraphStyle("v", fontSize=14, fontName="Helvetica-Bold")),
    ]]
    w = (letter[0] - inch) / 4
    kpi_tbl = Table(kpi_data, colWidths=[w, w, w, w])
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _GRIS),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [_GRIS, _GRIS]),
        ("BOX", (0, 0), (-1, -1), 0.5, _LINEA),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, _LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(kpi_tbl)
    elements.append(Spacer(1, 14))

    # Tabla de clientes
    hdr_style = ParagraphStyle("hdr", fontSize=8, fontName="Helvetica-Bold",
                                textColor=_BLANCO, alignment=TA_CENTER)
    cell_r = ParagraphStyle("cr", fontSize=8, fontName="Helvetica", alignment=TA_RIGHT)
    cell_l = ParagraphStyle("cl", fontSize=8, fontName="Helvetica")

    col_w = [2.2 * inch, 0.7 * inch, 1.3 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 0.7 * inch]
    headers = [
        Paragraph(h, hdr_style) for h in
        ["Cliente", "Tipo", "Corporativo", "Cartera", "Cobrado", "Pendiente", "DSO"]
    ]
    tbl_data = [headers]

    for cl in clientes:
        tbl_data.append([
            Paragraph(cl.get("nombre") or "—", cell_l),
            Paragraph(cl.get("tipo") or "—",   cell_l),
            Paragraph(cl.get("corporativo") or "—", cell_l),
            Paragraph(_mxn(cl.get("cartera")),   cell_r),
            Paragraph(_mxn(cl.get("cobrado")),   cell_r),
            Paragraph(_mxn(cl.get("pendiente")), cell_r),
            Paragraph(_dso(cl.get("dso")),       cell_r),
        ])

    tbl = Table(tbl_data, colWidths=col_w, repeatRows=1)
    row_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), _AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), _BLANCO),
        ("GRID", (0, 0), (-1, -1), 0.4, _LINEA),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(tbl_data), 2):
        row_styles.append(("BACKGROUND", (0, i), (-1, i), _GRIS))
    tbl.setStyle(TableStyle(row_styles))
    elements.append(tbl)

    doc.build(elements)
    return buf.getvalue()


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
                    THEN (%s::date - c.fecha_entrega)
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
                AVG(CURRENT_DATE - c.fecha_entrega) FILTER (
                    WHERE c.fecha_entrega IS NOT NULL
                      AND c.total - COALESCE(c.monto_pagado, 0) > 0
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


# ── POST /api/estado-cuenta/{cotizacion_id}/pago ─────────────────────────────

class PagoIn(BaseModel):
    monto: float
    fecha_pago: str
    metodo: Optional[str] = None
    referencia: Optional[str] = None


@router.post("/{cotizacion_id}/pago")
async def registrar_pago(cotizacion_id: int, body: PagoIn, user: dict = Depends(get_usuario_api)):
    if user.get("rol") not in ("Administrador", "Operador"):
        raise HTTPException(status_code=403, detail="Sin permiso")
    if body.monto <= 0:
        raise HTTPException(status_code=422, detail="El monto debe ser mayor a 0")

    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("SELECT total, estado FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cotización no encontrada")
        total_cot, estado_cot = float(row[0] or 0), row[1]

        if estado_cot in ("Cancelada", "Pagada"):
            raise HTTPException(status_code=422, detail=f"No se puede registrar pago en cotización {estado_cot}")

        cur.execute("""
            INSERT INTO pagos (cotizacion_id, monto, fecha_pago, metodo, referencia, registrado_por)
            VALUES (%s, %s, %s::date, %s, %s, %s)
        """, (cotizacion_id, body.monto, body.fecha_pago,
              body.metodo or None, body.referencia or None, user.get("id")))

        cur.execute("""
            UPDATE cotizaciones
               SET monto_pagado = (SELECT COALESCE(SUM(monto), 0) FROM pagos WHERE cotizacion_id = %s)
             WHERE id = %s
        """, (cotizacion_id, cotizacion_id))

        cur.execute("SELECT monto_pagado FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        nuevo_monto = float(cur.fetchone()[0] or 0)
        pagada = nuevo_monto >= total_cot

        if pagada:
            cur.execute("""
                UPDATE cotizaciones SET estado = 'Pagada', fecha_pago = %s::date WHERE id = %s
            """, (body.fecha_pago, cotizacion_id))
            cur.execute("""
                INSERT INTO seguimiento_etapas (cotizacion_id, etapa, completada, fecha_etapa)
                VALUES (%s, 'Pagada', 1, %s::date)
                ON CONFLICT (cotizacion_id, etapa) DO UPDATE SET
                    completada  = 1,
                    fecha_etapa = COALESCE(EXCLUDED.fecha_etapa, seguimiento_etapas.fecha_etapa)
            """, (cotizacion_id, body.fecha_pago))
            from web_app.cache import cache as _cache
            _cache.invalidar(f"dashboard:{empresa_db}")

    return JSONResponse({"ok": True, "monto_pagado": nuevo_monto, "pagada": pagada})


# ── GET /api/estado-cuenta/{cotizacion_id}/pagos ──────────────────────────────

@router.get("/{cotizacion_id}/pagos")
async def listar_pagos(cotizacion_id: int, user: dict = Depends(get_usuario_api)):
    empresa_db = user["empresa_db"]
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute("""
            SELECT p.id, p.monto, p.fecha_pago, p.metodo, p.referencia, p.created_at,
                   u.nombre AS registrado_por
            FROM pagos p
            LEFT JOIN usuarios u ON u.id = p.registrado_por
            WHERE p.cotizacion_id = %s
            ORDER BY p.fecha_pago, p.id
        """, (cotizacion_id,))
        cols = [d[0] for d in cur.description]
        pagos = [{k: _s(v) for k, v in zip(cols, r)} for r in cur.fetchall()]
    return JSONResponse({"pagos": pagos})


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
