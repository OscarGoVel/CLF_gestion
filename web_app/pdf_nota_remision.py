# -*- coding: utf-8 -*-
"""
Generador de nota de remision para cotizaciones.

La nota de remision documenta la entrega fisica: cliente, folio de cotizacion,
fecha y partidas entregadas. No incluye precios.
"""

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

import app_config
from web_app.database import get_pool_empresa

_M = 0.5 * inch
_ORO = colors.HexColor("#D4AF37")
_NEGRO = colors.HexColor("#1a1a1a")
_GRIS = colors.HexColor("#555555")
_GRID = colors.HexColor("#cccccc")


def _resolver_logo(nombre_base: str) -> str:
    base = os.path.join(app_config.BASE_DIR, nombre_base)
    if os.path.exists(base):
        return base
    for ext in (".jpg", ".jpeg", ".png"):
        ruta = base + ext
        if os.path.exists(ruta):
            return ruta
    return base


def _f(v) -> float:
    return float(v) if v is not None else 0.0


def generar_pdf_nota_remision(empresa_db: str, cotizacion_id: int) -> bytes:
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.id, c.folio, c.fecha, c.fecha_entrega, c.orden_compra,
                   COALESCE(cl.nombre_comercial, '') AS cliente,
                   COALESCE(cl.rfc, '') AS rfc,
                   COALESCE(cl.direccion, '') AS direccion,
                   COALESCE(comp.nombre, cl.contacto, '') AS recibe
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            LEFT JOIN compradores comp ON comp.id = c.comprador_id
            WHERE c.id = %s
            """,
            (cotizacion_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Cotizacion {cotizacion_id} no encontrada")

        (
            _, folio, fecha, fecha_entrega, orden_compra,
            cliente, rfc, direccion, recibe,
        ) = row

        cur.execute(
            """
            SELECT COALESCE(p.codigo, '') AS codigo,
                   COALESCE(p.nombre, cd.descripcion_libre, '') AS nombre,
                   COALESCE(p.unidad_medida, '') AS unidad,
                   cd.cantidad AS solicitada,
                   COALESCE(SUM(ep.cantidad_entregada), 0) AS entregada
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON p.id = cd.producto_id
            LEFT JOIN entregas_parciales ep
                   ON ep.cotizacion_id = cd.cotizacion_id
                  AND ep.producto_id = cd.producto_id
            WHERE cd.cotizacion_id = %s
            GROUP BY cd.id, p.codigo, p.nombre, cd.descripcion_libre,
                     p.unidad_medida, cd.cantidad
            ORDER BY cd.id
            """,
            (cotizacion_id,),
        )
        partidas = []
        for codigo, nombre, unidad, solicitada, entregada in cur.fetchall():
            cantidad = _f(entregada) if _f(entregada) > 0 else _f(solicitada)
            partidas.append((codigo, nombre, unidad or "Pieza", cantidad))

    fecha_doc = fecha_entrega or date.today()
    if hasattr(fecha_doc, "strftime"):
        fecha_fmt = fecha_doc.strftime("%d/%m/%Y")
    else:
        fecha_fmt = str(fecha_doc)[:10]

    buf = io.BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=_M,
        rightMargin=_M,
        topMargin=_M,
        bottomMargin=_M,
    )

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_GRIS)
        canvas.drawCentredString(
            _doc.pagesize[0] / 2,
            0.28 * inch,
            "Recibi de conformidad los productos descritos en esta nota de remision.",
        )
        canvas.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=footer)])

    logo = _resolver_logo("assets/logo_clf_header")
    logo_cell = ""
    if os.path.exists(logo):
        try:
            logo_cell = Image(logo, width=1.0 * inch, height=1.0 * inch)
        except Exception:
            logo_cell = ""

    banner = Paragraph(
        "NOTA DE REMISION",
        ParagraphStyle("banner", fontName="Helvetica-Bold", fontSize=18,
                       textColor=colors.white, alignment=TA_CENTER),
    )

    story = []
    header = Table([[logo_cell, banner]], colWidths=[1.25 * inch, doc.width - 1.25 * inch])
    header.setStyle(TableStyle([
        ("BACKGROUND", (1, 0), (1, 0), _ORO),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.12 * inch))

    info = Table([
        ["FECHA", fecha_fmt, "COTIZACION", folio],
        ["CLIENTE", cliente, "RFC", rfc],
        ["DIRECCION", direccion, "OC", orden_compra or ""],
        ["RECIBE", recibe or "", "", ""],
    ], colWidths=[0.9 * inch, 2.75 * inch, 1.0 * inch, 1.85 * inch])
    info.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (1, 3), (3, 3)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(info)
    story.append(Spacer(1, 0.18 * inch))

    rows = [["CODIGO", "CONCEPTO", "UNIDAD", "CANTIDAD"]]
    for codigo, nombre, unidad, cantidad in partidas:
        rows.append([codigo, nombre, unidad, f"{cantidad:g}"])
    while len(rows) < 9:
        rows.append(["", "", "", ""])

    items = Table(rows, colWidths=[1.0 * inch, 3.9 * inch, 0.9 * inch, 0.7 * inch])
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _NEGRO),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, _GRID),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
    ]))
    story.append(items)
    story.append(Spacer(1, 0.55 * inch))

    firma = Table([
        ["ENTREGA", "RECIBE"],
        ["", ""],
        ["Nombre y firma", "Nombre y firma"],
    ], colWidths=[3.0 * inch, 3.0 * inch], rowHeights=[0.22 * inch, 0.55 * inch, 0.2 * inch])
    firma.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LINEBELOW", (0, 1), (-1, 1), 0.8, colors.black),
    ]))
    story.append(firma)

    doc.build(story)
    return buf.getvalue()
