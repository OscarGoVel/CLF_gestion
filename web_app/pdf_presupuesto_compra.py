# -*- coding: utf-8 -*-
"""
web_app/pdf_presupuesto_compra.py
Genera el PDF de Presupuesto de Compra para el departamento de control presupuestal.

Sección A — Compras para ventas: productos con faltante por cotización.
Sección B — Consumo interno: insumos sin cotización de origen (opcional).
"""

import io
import os
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

import app_config
from web_app.database import get_pool_empresa

_ORO       = colors.HexColor('#D4AF37')
_NEGRO     = colors.HexColor('#1a1a1a')
_GRIS      = colors.HexColor('#4a4a4a')
_GRIS_GRID = colors.HexColor('#cccccc')
_FOOTER_BG = colors.HexColor('#3d3d3d')
_AZUL_HDR  = colors.HexColor('#1e3a5f')
_VERDE_HDR = colors.HexColor('#1a5f3a')

_M = 0.5 * inch


def _resolver_logo(nombre_base: str) -> str:
    base = os.path.join(app_config.BASE_DIR, nombre_base)
    if os.path.exists(base):
        return base
    for ext in ('.jpg', '.jpeg', '.png', '.gif'):
        ruta = base + ext
        if os.path.exists(ruta):
            return ruta
    return base


def _f(v) -> float:
    if isinstance(v, Decimal):
        return float(v)
    return float(v) if v is not None else 0.0


def generar_pdf_presupuesto_compra(
    empresa_db: str,
    cotizacion_ids: list[int],
    insumos: list[dict] | None = None,
) -> bytes:
    """
    Genera el PDF de presupuesto de compra y devuelve los bytes del archivo.

    Parámetros:
        empresa_db      -- pg_database de la empresa (del JWT)
        cotizacion_ids  -- lista de IDs de cotizaciones seleccionadas
        insumos         -- lista de dicts {nombre, unidad, cantidad, costo} para Sección B
    """
    if not cotizacion_ids:
        raise ValueError("Debe seleccionar al menos un pedido")

    if insumos is None:
        insumos = []

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.id, c.folio,
                   COALESCE(cl.nombre_comercial, '— sin cliente —') AS cliente,
                   c.fecha_entrega
            FROM cotizaciones c
            LEFT JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = ANY(%s)
            ORDER BY c.fecha_entrega ASC NULLS LAST
            """,
            (cotizacion_ids,),
        )
        cotizaciones = [
            dict(zip([d[0] for d in cur.description], r))
            for r in cur.fetchall()
        ]

        # Per-cotización rows — one row per (cotización, product) with faltante
        # Usa MAX(costo_historial) como estimación conservadora para el presupuesto
        cur.execute(
            """
            SELECT c.folio,
                   p.nombre,
                   p.unidad_medida,
                   GREATEST(cd.cantidad - COALESCE(p.stock_actual, 0), 0) AS cantidad_faltante,
                   COALESCE(max_h.costo_max, p.precio_base)               AS costo_max,
                   COALESCE(p.costo_promedio, p.precio_base)              AS costo_promedio
            FROM cotizacion_detalle cd
            JOIN cotizaciones c  ON c.id  = cd.cotizacion_id
            JOIN productos    p  ON p.id  = cd.producto_id
            LEFT JOIN LATERAL (
                SELECT MAX(h.precio) AS costo_max
                FROM producto_precio_historial h
                WHERE h.producto_id = p.id
            ) max_h ON TRUE
            WHERE cd.cotizacion_id = ANY(%s)
              AND GREATEST(cd.cantidad - COALESCE(p.stock_actual, 0), 0) > 0
            ORDER BY c.folio, p.nombre
            """,
            (cotizacion_ids,),
        )
        cols = [d[0] for d in cur.description]
        productos = [
            {k: _f(v) if isinstance(v, Decimal) else v
             for k, v in dict(zip(cols, r)).items()}
            for r in cur.fetchall()
        ]

    if not productos and not insumos:
        raise ValueError(
            "No hay productos con faltante de stock ni insumos para generar el presupuesto"
        )

    # Calcular subtotales
    for p in productos:
        p["subtotal"] = round(p["cantidad_faltante"] * (p["costo_max"] or 0.0), 2)

    subtotal_a = round(sum(p["subtotal"] for p in productos), 2)

    insumos_norm = []
    for ins in insumos:
        cant  = float(ins.get("cantidad", 0) or 0)
        costo = float(ins.get("costo", 0) or 0)
        insumos_norm.append({
            "nombre":   str(ins.get("nombre", "")),
            "unidad":   str(ins.get("unidad", "pza") or "pza"),
            "cantidad": cant,
            "costo":    costo,
            "subtotal": round(cant * costo, 2),
        })

    subtotal_b    = round(sum(i["subtotal"] for i in insumos_norm), 2)
    total_general = round(subtotal_a + subtotal_b, 2)

    ahora     = datetime.now()
    folio     = f"PC-{ahora.year}-{ahora.strftime('%m%d%H%M')}"
    fecha_fmt = ahora.strftime('%d/%m/%Y %H:%M')

    logo_header = _resolver_logo('assets/logo_clf_header')
    logo_footer = _resolver_logo('assets/logo_clf_footer')

    buf = io.BytesIO()

    def _footer(canvas, doc):
        canvas.saveState()
        W = doc.pagesize[0]
        box_h = 0.85 * inch
        box_y = _M - 4
        canvas.setFillColor(_FOOTER_BG)
        canvas.rect(_M, box_y, W - 2 * _M, box_h, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 7)
        canvas.drawString(_M + 8, box_y + box_h - 14,
                          'GENERADO PARA: DEPARTAMENTO DE CONTROL PRESUPUESTAL')
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(_M + 8, box_y + box_h - 28,
                          'Documento de solicitud de presupuesto — uso interno. No es una orden de compra.')
        canvas.drawString(_M + 8, box_y + box_h - 40,
                          f'Folio: {folio}   |   Fecha: {fecha_fmt}')
        if os.path.exists(logo_footer):
            try:
                logo_w = 0.55 * inch
                canvas.drawImage(
                    logo_footer,
                    W - _M - logo_w - 6,
                    box_y + (box_h - logo_w) / 2,
                    width=logo_w, height=logo_w,
                    preserveAspectRatio=True, mask='auto',
                )
            except Exception:
                pass
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.setFont('Helvetica', 6)
        canvas.drawCentredString(
            W / 2, box_y - 10,
            'Si tiene alguna duda sobre este presupuesto, comuníquese con el área de compras.',
        )
        canvas.restoreState()

    footer_h = 1.1 * inch
    doc = BaseDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=_M, rightMargin=_M,
        topMargin=_M,  bottomMargin=_M + footer_h,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')
    doc.addPageTemplates([PageTemplate(id='main', frames=frame, onPage=_footer)])

    elementos = []
    ancho = doc.width

    # ── 1. HEADER ─────────────────────────────────────────────────────────────
    logo_cell = ''
    if os.path.exists(logo_header):
        try:
            logo_cell = Image(logo_header, width=1.1 * inch, height=1.1 * inch)
        except Exception:
            pass

    banner_txt = Paragraph(
        'PRESUPUESTO DE COMPRA',
        ParagraphStyle('banner', fontSize=16, fontName='Helvetica-Bold',
                       textColor=colors.white, alignment=TA_CENTER),
    )
    header_tbl = Table([[logo_cell, banner_txt]],
                       colWidths=[1.3 * inch, ancho - 1.3 * inch],
                       rowHeights=[1.1 * inch])
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (1, 0), (1, 0), _ORO),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (0, 0), 'CENTER'),
        ('LEFTPADDING',   (1, 0), (1, 0), 0),
        ('RIGHTPADDING',  (1, 0), (1, 0), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elementos.append(header_tbl)
    elementos.append(Spacer(1, 0.08 * inch))

    # ── 2. INFO ───────────────────────────────────────────────────────────────
    if insumos_norm:
        totales_rows = [
            ['SUBTOTAL A (ventas):', f'$ {subtotal_a:,.2f}'],
            ['SUBTOTAL B (internos):',  f'$ {subtotal_b:,.2f}'],
            ['TOTAL GENERAL:',          f'$ {total_general:,.2f}'],
        ]
        highlight_row = 2
    else:
        totales_rows = [
            ['TOTAL EST.:', f'$ {total_general:,.2f}'],
        ]
        highlight_row = 0

    info_rows = [
        ['FOLIO:',         folio],
        ['FECHA:',         fecha_fmt],
        ['PEDIDOS INCL.:', str(len(cotizaciones))],
        ['PRODUCTOS:',     str(len(productos))],
    ] + totales_rows

    info_inner = Table(info_rows, colWidths=[1.5 * inch, 1.5 * inch])
    info_styles = [
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('BACKGROUND',    (0, -1), (1, -1), colors.HexColor('#fffbe6')),
        ('FONTNAME',      (0, -1), (1, -1), 'Helvetica-Bold'),
    ]
    info_inner.setStyle(TableStyle(info_styles))

    titulo_para = Paragraph(
        'SOLICITUD DE PRESUPUESTO<br/><font size="8" color="#555555">Productos con faltante de stock en pedidos programados</font>',
        ParagraphStyle('titulo_izq', fontSize=12, fontName='Helvetica-Bold',
                       leading=18, textColor=_NEGRO),
    )
    izq_w = ancho - 3.1 * inch
    info_tbl = Table([[titulo_para, info_inner]], colWidths=[izq_w, 3.1 * inch])
    info_tbl.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    elementos.append(info_tbl)
    elementos.append(Spacer(1, 0.1 * inch))

    # ── 3. TABLA DE PEDIDOS INCLUIDOS ─────────────────────────────────────────
    elementos.append(Paragraph(
        'PEDIDOS PROGRAMADOS INCLUIDOS',
        ParagraphStyle('sec_hdr', fontSize=8, fontName='Helvetica-Bold',
                       textColor=colors.white, backColor=_AZUL_HDR,
                       leftIndent=5, spaceAfter=0),
    ))

    cot_data = [['FOLIO', 'CLIENTE', 'FECHA ENTREGA']]
    for c in cotizaciones:
        fe = c['fecha_entrega']
        if hasattr(fe, 'strftime'):
            fe_str = fe.strftime('%d/%m/%Y')
        elif fe:
            fe_str = str(fe)[:10]
        else:
            fe_str = '— sin fecha —'
        cot_data.append([c['folio'], c['cliente'], fe_str])

    cot_tbl = Table(cot_data, colWidths=[1.5 * inch, ancho - 3.0 * inch, 1.5 * inch])
    cot_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), _NEGRO),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 7.5),
        ('FONTNAME',      (0, 1), (-1, -1), 'Helvetica'),
        ('GRID',          (0, 0), (-1, -1), 0.5, _GRIS_GRID),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f7f7')]),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('ALIGN',         (2, 0), (2, -1), 'CENTER'),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elementos.append(cot_tbl)
    elementos.append(Spacer(1, 0.12 * inch))

    # ── 4. SECCIÓN A — COMPRAS PARA VENTAS ───────────────────────────────────
    if productos:
        elementos.append(Paragraph(
            'A · COMPRAS PARA VENTAS — Productos con faltante de stock',
            ParagraphStyle('sec_a', fontSize=8, fontName='Helvetica-Bold',
                           textColor=colors.white, backColor=_AZUL_HDR,
                           leftIndent=5, spaceAfter=0),
        ))

        n_prod = len(productos)
        fs = 7.5 if n_prod <= 20 else (7.0 if n_prod <= 35 else 6.5)

        estilo_prod = ParagraphStyle('prod_cell', fontName='Helvetica',
                                     fontSize=fs, leading=fs + 2, wordWrap='CJK')
        estilo_hdr  = ParagraphStyle('hdr_cell',  fontName='Helvetica-Bold',
                                     fontSize=fs, leading=fs + 2,
                                     textColor=colors.white, wordWrap='CJK')

        col_w_a = [
            ancho * 0.13,  # COT
            ancho * 0.27,  # PRODUCTO
            ancho * 0.07,  # UNIDAD
            ancho * 0.09,  # A COMPRAR
            ancho * 0.14,  # COSTO PROM
            ancho * 0.14,  # COSTO MAX
            ancho * 0.16,  # SUBTOTAL
        ]

        prod_data = [[
            Paragraph('COT', estilo_hdr),
            Paragraph('PRODUCTO', estilo_hdr),
            'UNIDAD', 'A COMPRAR', 'COSTO PROM', 'COSTO MAX', 'SUBTOTAL',
        ]]
        for p in productos:
            costo_max  = p["costo_max"] or 0.0
            costo_prom = p["costo_promedio"] or 0.0
            prod_data.append([
                p['folio'],
                Paragraph(p['nombre'], estilo_prod),
                p['unidad_medida'] or 'Pza',
                f"{p['cantidad_faltante']:g}",
                f"$ {costo_prom:,.2f}" if costo_prom else "—",
                f"$ {costo_max:,.2f}" if costo_max else "— sin costo —",
                f"$ {p['subtotal']:,.2f}",
            ])

        # Subtotal A row (5 celdas vacías + label + valor para 7 columnas)
        prod_data.append(['', '', '', '', '', 'SUBTOTAL A', f"$ {subtotal_a:,.2f}"])

        n_filas_a = len(prod_data)
        prod_tbl = Table(prod_data, colWidths=col_w_a)
        prod_tbl.setStyle(TableStyle([
            ('BACKGROUND',     (0, 0), (-1, 0),  _NEGRO),
            ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',       (0, 0), (-1, 0),  fs),
            ('FONTNAME',       (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE',       (0, 1), (-1, -1), fs),
            ('GRID',           (0, 0), (-1, n_filas_a - 2), 0.5, _GRIS_GRID),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f7f7f7')]),
            ('TOPPADDING',     (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 3),
            ('LEFTPADDING',    (0, 0), (-1, -1), 4),
            ('ALIGN',          (2, 0), (3, -1),  'CENTER'),
            ('ALIGN',          (4, 0), (6, -1),  'RIGHT'),
            ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND',     (0, -1), (-1, -1), colors.HexColor('#fffbe6')),
            ('FONTNAME',       (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE',      (0, -1), (-1, -1), 1.0, _NEGRO),
            ('SPAN',           (0, -1), (4, -1)),
            ('ALIGN',          (5, -1), (6, -1), 'RIGHT'),
        ]))
        elementos.append(prod_tbl)

    # ── 5. SECCIÓN B — CONSUMO INTERNO ────────────────────────────────────────
    if insumos_norm:
        elementos.append(Spacer(1, 0.12 * inch))
        elementos.append(Paragraph(
            'B · CONSUMO INTERNO — Insumos sin cotización de origen',
            ParagraphStyle('sec_b', fontSize=8, fontName='Helvetica-Bold',
                           textColor=colors.white, backColor=_VERDE_HDR,
                           leftIndent=5, spaceAfter=0),
        ))

        n_ins = len(insumos_norm)
        fs_b = 7.5 if n_ins <= 20 else 7.0

        estilo_ins = ParagraphStyle('ins_cell', fontName='Helvetica',
                                    fontSize=fs_b, leading=fs_b + 2, wordWrap='CJK')
        estilo_ins_hdr = ParagraphStyle('ins_hdr', fontName='Helvetica-Bold',
                                        fontSize=fs_b, leading=fs_b + 2,
                                        textColor=colors.white, wordWrap='CJK')

        col_w_b = [
            ancho * 0.38,  # PRODUCTO
            ancho * 0.10,  # UNIDAD
            ancho * 0.12,  # CANTIDAD
            ancho * 0.20,  # COSTO UNIT.
            ancho * 0.20,  # SUBTOTAL
        ]

        ins_data = [[
            Paragraph('PRODUCTO / DESCRIPCIÓN', estilo_ins_hdr),
            'UNIDAD', 'CANTIDAD', 'COSTO UNIT.', 'SUBTOTAL',
        ]]
        for ins in insumos_norm:
            ins_data.append([
                Paragraph(ins['nombre'], estilo_ins),
                ins['unidad'],
                f"{ins['cantidad']:g}",
                f"$ {ins['costo']:,.2f}" if ins['costo'] else "—",
                f"$ {ins['subtotal']:,.2f}",
            ])

        ins_data.append(['', '', '', 'SUBTOTAL B', f"$ {subtotal_b:,.2f}"])

        n_filas_b = len(ins_data)
        ins_tbl = Table(ins_data, colWidths=col_w_b)
        ins_tbl.setStyle(TableStyle([
            ('BACKGROUND',     (0, 0), (-1, 0),  _NEGRO),
            ('TEXTCOLOR',      (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',       (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',       (0, 0), (-1, 0),  fs_b),
            ('FONTNAME',       (0, 1), (-1, -2), 'Helvetica'),
            ('FONTSIZE',       (0, 1), (-1, -1), fs_b),
            ('GRID',           (0, 0), (-1, n_filas_b - 2), 0.5, _GRIS_GRID),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0fff4')]),
            ('TOPPADDING',     (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 3),
            ('LEFTPADDING',    (0, 0), (-1, -1), 4),
            ('ALIGN',          (1, 0), (2, -1),  'CENTER'),
            ('ALIGN',          (3, 0), (4, -1),  'RIGHT'),
            ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND',     (0, -1), (-1, -1), colors.HexColor('#f0fff4')),
            ('FONTNAME',       (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE',      (0, -1), (-1, -1), 1.0, _NEGRO),
            ('SPAN',           (0, -1), (2, -1)),
            ('ALIGN',          (3, -1), (4, -1), 'RIGHT'),
        ]))
        elementos.append(ins_tbl)

    # ── 6. TOTAL GENERAL (si hay ambas secciones) ─────────────────────────────
    if productos and insumos_norm:
        elementos.append(Spacer(1, 0.06 * inch))
        total_tbl = Table(
            [['', 'TOTAL GENERAL', f"$ {total_general:,.2f}"]],
            colWidths=[ancho * 0.60, ancho * 0.20, ancho * 0.20],
        )
        total_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), colors.HexColor('#fffbe6')),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0), 9),
            ('LINEABOVE',     (0, 0), (-1, 0), 1.5, _NEGRO),
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, _NEGRO),
            ('TOPPADDING',    (0, 0), (-1, 0), 5),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('LEFTPADDING',   (0, 0), (-1, 0), 4),
            ('ALIGN',         (1, 0), (2, 0), 'RIGHT'),
            ('VALIGN',        (0, 0), (-1, 0), 'MIDDLE'),
        ]))
        elementos.append(total_tbl)

    doc.build(elementos)
    return buf.getvalue()
