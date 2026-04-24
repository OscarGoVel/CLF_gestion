# -*- coding: utf-8 -*-
"""
web_app/pdf_presupuesto_compra.py
Genera el PDF de Presupuesto de Compra para el departamento de control presupuestal.
Identifica faltantes de stock en pedidos programados y calcula el monto requerido
usando el precio mínimo histórico de cada producto.
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

# ── Colores corporativos (iguales al PDF de cotización) ───────────────────────
_ORO       = colors.HexColor('#D4AF37')
_NEGRO     = colors.HexColor('#1a1a1a')
_GRIS      = colors.HexColor('#4a4a4a')
_GRIS_GRID = colors.HexColor('#cccccc')
_FOOTER_BG = colors.HexColor('#3d3d3d')
_AZUL_HDR  = colors.HexColor('#1e3a5f')

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
) -> bytes:
    """
    Genera el PDF de presupuesto de compra y devuelve los bytes del archivo.

    Parámetros:
        empresa_db      -- pg_database de la empresa (del JWT)
        cotizacion_ids  -- lista de IDs de cotizaciones seleccionadas

    Retorna:
        bytes del PDF.
    """
    if not cotizacion_ids:
        raise ValueError("Debe seleccionar al menos un pedido")

    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        # ── Datos de cotizaciones seleccionadas ──────────────────────────────
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

        # ── Productos con faltante (agrupados por producto) ──────────────────
        cur.execute(
            """
            SELECT
                p.id,
                p.nombre,
                p.unidad_medida,
                SUM(cd.cantidad)                              AS cantidad_pedida,
                COALESCE(MAX(p.stock_actual), 0)              AS stock_actual,
                GREATEST(
                    SUM(cd.cantidad) - COALESCE(MAX(p.stock_actual), 0),
                    0
                )                                             AS cantidad_faltante,
                COALESCE(min_h.precio, MAX(p.precio_base))    AS precio_min,
                COALESCE(prov.nombre, '— sin historial —')   AS proveedor_nombre
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            LEFT JOIN LATERAL (
                SELECT h.precio, h.proveedor_id
                FROM producto_precio_historial h
                WHERE h.producto_id = p.id
                ORDER BY h.precio ASC
                LIMIT 1
            ) min_h ON TRUE
            LEFT JOIN proveedores prov ON prov.id = min_h.proveedor_id
            WHERE cd.cotizacion_id = ANY(%s)
            GROUP BY p.id, p.nombre, p.unidad_medida, min_h.precio, prov.nombre
            HAVING SUM(cd.cantidad) > COALESCE(MAX(p.stock_actual), 0)
            ORDER BY p.nombre
            """,
            (cotizacion_ids,),
        )
        cols = [d[0] for d in cur.description]
        productos = [
            {k: _f(v) if isinstance(v, Decimal) else v
             for k, v in dict(zip(cols, r)).items()}
            for r in cur.fetchall()
        ]

    if not productos:
        raise ValueError("No hay productos con faltante de stock en los pedidos seleccionados")

    # ── Calcular subtotales y total general ───────────────────────────────────
    for p in productos:
        precio = p["precio_min"] or 0.0
        p["subtotal"] = round(p["cantidad_faltante"] * precio, 2)

    total_general = round(sum(p["subtotal"] for p in productos), 2)

    # ── Folio y fecha ─────────────────────────────────────────────────────────
    ahora    = datetime.now()
    folio    = f"PC-{ahora.year}-{ahora.strftime('%m%d%H%M')}"
    fecha_fmt = ahora.strftime('%d/%m/%Y %H:%M')

    logo_header = _resolver_logo('assets/logo_clf_header')
    logo_footer = _resolver_logo('assets/logo_clf_footer')

    buf = io.BytesIO()
    ancho_pagina, _ = letter

    # ── Footer ────────────────────────────────────────────────────────────────
    def _footer(canvas, doc):
        canvas.saveState()
        W = doc.pagesize[0]

        box_h = 0.85 * inch
        box_y = _M - 4
        canvas.setFillColor(_FOOTER_BG)
        canvas.rect(_M, box_y, W - 2 * _M, box_h, fill=1, stroke=0)

        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 7)
        canvas.drawString(_M + 8, box_y + box_h - 14, 'GENERADO PARA: DEPARTAMENTO DE CONTROL PRESUPUESTAL')
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(_M + 8, box_y + box_h - 28,
                          'Documento de solicitud de presupuesto — uso interno. No es una orden de compra.')
        canvas.drawString(_M + 8, box_y + box_h - 40, f'Folio: {folio}   |   Fecha: {fecha_fmt}')

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

    # ── Documento ─────────────────────────────────────────────────────────────
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

    # ── 2. INFO: Fecha + Folio ────────────────────────────────────────────────
    info_rows = [
        ['FOLIO:',         folio],
        ['FECHA:',         fecha_fmt],
        ['PEDIDOS INCL.:', str(len(cotizaciones))],
        ['PRODUCTOS:',     str(len(productos))],
        ['TOTAL EST.:',    f'$ {total_general:,.2f}'],
    ]
    info_inner = Table(info_rows, colWidths=[1.3 * inch, 1.7 * inch])
    info_inner.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
        ('BACKGROUND',    (0, 4), (1, 4), colors.HexColor('#fffbe6')),
        ('FONTNAME',      (0, 4), (1, 4), 'Helvetica-Bold'),
    ]))

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

    # ── 4. TABLA PRINCIPAL DE PRODUCTOS ──────────────────────────────────────
    elementos.append(Paragraph(
        'PRODUCTOS CON FALTANTE DE STOCK',
        ParagraphStyle('sec_hdr2', fontSize=8, fontName='Helvetica-Bold',
                       textColor=colors.white, backColor=_AZUL_HDR,
                       leftIndent=5, spaceAfter=0),
    ))

    # Escala fuente según cantidad de productos para intentar caber en una hoja
    n_prod = len(productos)
    if n_prod <= 15:
        fs = 7.5
    elif n_prod <= 25:
        fs = 7.0
    elif n_prod <= 35:
        fs = 6.5
    else:
        fs = 6.0

    # Columnas: PRODUCTO, UNIDAD, A COMPRAR, PROVEEDOR SGER., P.U. EST., SUBTOTAL
    col_widths = [
        ancho * 0.30,   # PRODUCTO  — ancho generoso para evitar desbordamiento
        ancho * 0.07,   # UNIDAD
        ancho * 0.09,   # A COMPRAR
        ancho * 0.26,   # PROVEEDOR SGER.
        ancho * 0.13,   # P.U. EST.
        ancho * 0.15,   # SUBTOTAL
    ]

    # Estilo de párrafo para la celda de nombre de producto (permite word-wrap)
    estilo_prod = ParagraphStyle(
        'prod_cell',
        fontName='Helvetica',
        fontSize=fs,
        leading=fs + 2,
        wordWrap='CJK',
    )
    estilo_hdr = ParagraphStyle(
        'hdr_cell',
        fontName='Helvetica-Bold',
        fontSize=fs,
        leading=fs + 2,
        textColor=colors.white,
        wordWrap='CJK',
    )

    col_names = [
        Paragraph('PRODUCTO', estilo_hdr),
        'UNIDAD', 'A COMPRAR', 'PROVEEDOR SGER.', 'P.U. EST.', 'SUBTOTAL',
    ]
    prod_data = [col_names]

    for p in productos:
        precio = p["precio_min"] or 0.0
        prod_data.append([
            Paragraph(p['nombre'], estilo_prod),
            p['unidad_medida'] or 'Pza',
            f"{p['cantidad_faltante']:g}",
            p['proveedor_nombre'],
            f"$ {precio:,.2f}" if precio else "— sin precio —",
            f"$ {p['subtotal']:,.2f}",
        ])

    # Fila de total  (6 columnas: 0-3 vacías, 4=etiqueta, 5=monto)
    prod_data.append(['', '', '', '', 'TOTAL ESTIMADO', f"$ {total_general:,.2f}"])

    n_filas = len(prod_data)
    prod_tbl = Table(prod_data, colWidths=col_widths, rowHeights=None)
    prod_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), _NEGRO),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, 0), fs),
        ('FONTNAME',      (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE',      (0, 1), (-1, -1), fs),
        ('GRID',          (0, 0), (-1, n_filas - 2), 0.5, _GRIS_GRID),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f7f7f7')]),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('ALIGN',         (1, 0), (2, -1), 'CENTER'),
        ('ALIGN',         (4, 0), (5, -1), 'RIGHT'),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        # Fila total
        ('BACKGROUND',    (0, -1), (-1, -1), colors.HexColor('#fffbe6')),
        ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE',     (0, -1), (-1, -1), 1.0, _NEGRO),
        ('SPAN',          (0, -1), (3, -1)),
        ('ALIGN',         (4, -1), (5, -1), 'RIGHT'),
    ]))
    elementos.append(prod_tbl)

    doc.build(elementos)
    return buf.getvalue()
