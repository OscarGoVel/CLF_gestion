# -*- coding: utf-8 -*-
"""
web_app/pdf_cotizacion.py
Generador de PDF de cotización para la web app.

Produce el mismo formato visual que ui/generador_pdf_cly.py pero:
  - Usa el pool de PostgreSQL de la web (sin depender de sesion.py)
  - Devuelve bytes en lugar de guardar un archivo
  - Compatible con FastAPI Response(media_type="application/pdf")
"""

import io
import os
from datetime import datetime, timedelta
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

import app_config
from web_app.database import get_pool_empresa

# ── Colores corporativos ──────────────────────────────────────────────────────
_ORO   = colors.HexColor('#D4AF37')
_NEGRO = colors.HexColor('#1a1a1a')
_GRIS  = colors.HexColor('#4a4a4a')
_GRIS_GRID = colors.HexColor('#cccccc')
_FOOTER_BG = colors.HexColor('#3d3d3d')

# Márgenes
_M = 0.5 * inch


def _resolver_logo(nombre_base: str) -> str:
    """Devuelve la ruta completa del logo probando extensiones comunes.
    nombre_base puede ser relativo a BASE_DIR (ej. 'assets/logo_clf_header').
    """
    base = os.path.join(app_config.BASE_DIR, nombre_base)
    if os.path.exists(base):
        return base
    for ext in ('.jpg', '.jpeg', '.png', '.gif'):
        ruta = base + ext
        if os.path.exists(ruta):
            return ruta
    return base  # devuelve igual aunque no exista (el caller verifica)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(v) -> float:
    """Convierte Decimal o cualquier numérico a float."""
    if isinstance(v, Decimal):
        return float(v)
    return float(v) if v is not None else 0.0


def _ajustar_columnas(datos: list, ancho_total: float, min_col: float = 0.4,
                      col_texto: int = 0) -> list:
    """Calcula anchos de columna proporcionales al contenido."""
    FUENTE, FUENTE_B, FS, PAD = 'Helvetica', 'Helvetica-Bold', 8, 10

    if not datos:
        return []
    n = max(len(f) for f in datos)
    anchos = [0.0] * n

    for ri, fila in enumerate(datos):
        fn = FUENTE_B if ri == 0 else FUENTE
        for ci, celda in enumerate(fila):
            txt = str(celda).split('\n')[0] if celda else ''
            w = stringWidth(txt, fn, FS) + PAD
            if w > anchos[ci]:
                anchos[ci] = w

    min_pts = min_col * inch
    anchos = [max(a, min_pts) for a in anchos]

    factor = ancho_total / sum(anchos)
    anchos = [a * factor for a in anchos]

    # Compensar columnas que quedaron debajo del mínimo
    for i in range(n):
        if anchos[i] < min_pts:
            diff = min_pts - anchos[i]
            anchos[i] = min_pts
            anchos[col_texto] -= diff

    return anchos


def _params_tabla(n: int) -> tuple[float, float]:
    """Devuelve (tamaño_fuente, alto_fila) según número de productos."""
    tabla = [
        (10, 9, 22), (15, 8.5, 18), (20, 8, 16),
        (25, 7.5, 14), (30, 7, 12), (35, 6.5, 11),
        (40, 6.3, 10), (45, 6.1, 9.5),
    ]
    fuente, alto = 6.0, 9.0
    for limite, f, a in tabla:
        if n <= limite:
            fuente, alto = f, a
            break

    espacio = 370
    estimado = (n + 4) * alto
    if estimado > espacio:
        factor = espacio / estimado * 0.95
        alto   = alto * factor
        fuente = max(5.5, fuente * factor)

    return fuente, alto


# ── Generador principal ───────────────────────────────────────────────────────

def generar_pdf_cotizacion(empresa_db: str, cotizacion_id: int) -> bytes:
    """
    Genera el PDF de una cotización y devuelve los bytes del archivo.

    Parámetros:
        empresa_db      -- pg_database de la empresa (del JWT)
        cotizacion_id   -- ID de la cotización

    Retorna:
        bytes del PDF, o lanza ValueError si la cotización no existe.
    """
    # ── Obtener datos de la BD ────────────────────────────────────────────────
    with get_pool_empresa(empresa_db).conexion() as (_, cur):
        cur.execute(
            """
            SELECT c.folio, c.fecha, c.subtotal, c.iva, c.total, c.notas,
                   cl.nombre_comercial, cl.tipo, cl.contacto, cl.direccion
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = %s
            """,
            (cotizacion_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Cotización {cotizacion_id} no encontrada")

        folio, fecha, subtotal, iva, total, notas, cliente, tipo_cliente, contacto, direccion = row
        subtotal, iva, total = _f(subtotal), _f(iva), _f(total)

        cur.execute(
            """
            SELECT COALESCE(p.codigo, '') AS codigo,
                   COALESCE(p.nombre, cd.descripcion_libre, '') AS nombre,
                   cd.cantidad,
                   COALESCE(p.unidad_medida, '') AS unidad_medida,
                   cd.precio_unitario, cd.subtotal,
                   COALESCE(p.aplica_iva, 0) AS aplica_iva
            FROM cotizacion_detalle cd
            LEFT JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = %s
            ORDER BY cd.id
            """,
            (cotizacion_id,),
        )
        productos = [(r[0], r[1], _f(r[2]), r[3], _f(r[4]), _f(r[5]), r[6])
                     for r in cur.fetchall()]

    # ── Calcular fechas ───────────────────────────────────────────────────────
    try:
        if hasattr(fecha, 'strftime'):
            fecha_dt = datetime(fecha.year, fecha.month, fecha.day)
        else:
            fecha_dt = datetime.strptime(str(fecha)[:10], '%Y-%m-%d')
    except Exception:
        fecha_dt = datetime.now()

    fecha_fmt   = fecha_dt.strftime('%d/%m/%Y')
    valido_hasta = (fecha_dt + timedelta(days=30)).strftime('%d/%m/%Y')

    # ── Configuración ─────────────────────────────────────────────────────────
    terminos    = app_config.PDF_CONFIG
    logo_header = _resolver_logo('assets/logo_clf_header')
    logo_footer = _resolver_logo('assets/logo_clf_footer')

    # ── Parámetros de tabla ───────────────────────────────────────────────────
    fuente_tabla, alto_fila = _params_tabla(len(productos))

    # ── Preparar buffer ───────────────────────────────────────────────────────
    buf  = io.BytesIO()
    ancho_pagina, _ = letter

    # ── Footer dibujado sobre el canvas ──────────────────────────────────────
    def _footer(canvas, doc):
        canvas.saveState()
        W = doc.pagesize[0]

        box_h = 1.1 * inch
        box_y = _M - 4
        canvas.setFillColor(_FOOTER_BG)
        canvas.rect(_M, box_y, W - 2 * _M, box_h, fill=1, stroke=0)

        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 7)
        canvas.drawString(_M + 8, box_y + box_h - 14, 'TÉRMINOS Y CONDICIONES')
        canvas.setFont('Helvetica', 6.5)
        lineas = [
            f"1. VIGENCIA DE PRESUPUESTO: {terminos.get('vigencia', '30 DÍAS')}.",
            f"2. LUGAR DE ENTREGA: {terminos.get('lugar_entrega', 'MÉRIDA')}",
            f"3. TIEMPO DE ENTREGA: {terminos.get('tiempo_entrega', '')}",
            terminos.get('moneda', ''),
            terminos.get('cambios', ''),
        ]
        y_txt = box_y + box_h - 26
        for linea in lineas:
            canvas.drawString(_M + 8, y_txt, linea)
            y_txt -= 9

        if os.path.exists(logo_footer):
            try:
                logo_w = 0.75 * inch
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
        canvas.setFont('Helvetica', 6.5)
        canvas.drawCentredString(
            W / 2, box_y - 12,
            'Si usted tiene alguna duda, por favor, póngase en contacto con nosotros.',
        )
        canvas.restoreState()

    # ── Configurar documento ──────────────────────────────────────────────────
    footer_h = 1.35 * inch
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

    # ── 1. HEADER: Logo + Banner ──────────────────────────────────────────────
    logo_cell = ''
    if os.path.exists(logo_header):
        try:
            logo_cell = Image(logo_header, width=1.1 * inch, height=1.1 * inch)
        except Exception:
            pass

    banner_txt = Paragraph(
        'COTIZACIÓN',
        ParagraphStyle('banner', fontSize=18, fontName='Helvetica-Bold',
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
    elementos.append(Spacer(1, 0.07 * inch))

    # ── 2. INFO: Dirección empresa + Datos cliente ────────────────────────────
    addr_para = Paragraph(
        ('CALLE 17 NO. 56 DEPTO.74 ENTRE CALLE 12 Y CALLE 14.<br/>'
         'KANASÍN, YUCATÁN.<br/><br/>'
         'C.P. 97370<br/>TELÉFONO: 9993633880'),
        ParagraphStyle('addr', fontSize=8, leading=11,
                       textColor=colors.HexColor('#333333')),
    )

    info_rows = [
        ['FECHA:',          fecha_fmt],
        ['CLIENTE:',        cliente or ''],
        ['UBICACIÓN:',      direccion or 'MÉRIDA'],
        ['PRESUPUESTO NO.', folio],
        ['VÁLIDO HASTA',    valido_hasta],
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
    ]))

    izq_w = ancho - 3.1 * inch
    info_tbl = Table([[addr_para, info_inner]], colWidths=[izq_w, 3.1 * inch])
    info_tbl.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',  (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    elementos.append(info_tbl)
    elementos.append(Spacer(1, 0.09 * inch))

    # ── 3. TABLA DE PRODUCTOS ─────────────────────────────────────────────────
    datos_tabla = [['CONCEPTO', 'UNIDAD', 'CANTIDAD', 'P.U.', 'IMPORTE']]
    for _, nombre, cantidad, unidad, precio, sub_prod, _ in productos:
        datos_tabla.append([
            nombre,
            unidad or 'Pieza',
            f'{cantidad:g}',
            f'$ {precio:,.2f}',
            f'$ {sub_prod:,.2f}',
        ])

    while len(datos_tabla) < 9:
        datos_tabla.append(['', '', '', '', ''])

    datos_tabla.append(['', '', '', 'SUBTOTAL', f'$ {subtotal:,.2f}'])
    datos_tabla.append(['', '', '', 'IVA',      f'$ {iva:,.2f}'])
    datos_tabla.append(['', '', '', 'TOTAL',    f'$ {total:,.2f}'])

    col_w = _ajustar_columnas(datos_tabla, ancho, min_col=0.5, col_texto=0)
    tabla_prods = Table(datos_tabla, colWidths=col_w, rowHeights=alto_fila)

    n = len(datos_tabla)
    tabla_prods.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0),  (-1, 0),  _NEGRO),
        ('TEXTCOLOR',   (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',    (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0),  (-1, 0),  fuente_tabla),
        ('ALIGN',       (0, 0),  (-1, 0),  'CENTER'),
        ('FONTNAME',    (0, 1),  (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 1),  (-1, -1), fuente_tabla),
        ('VALIGN',      (0, 0),  (-1, -1), 'MIDDLE'),
        ('GRID',        (0, 0),  (-1, n - 4), 0.5, _GRIS_GRID),
        ('ALIGN',       (1, 1),  (1, -1),  'CENTER'),
        ('ALIGN',       (2, 1),  (2, -1),  'CENTER'),
        ('ALIGN',       (3, 1),  (3, -1),  'RIGHT'),
        ('ALIGN',       (4, 1),  (4, -1),  'RIGHT'),
        ('FONTNAME',    (3, n - 3), (4, n - 1), 'Helvetica-Bold'),
        ('ALIGN',       (3, n - 3), (3, n - 1), 'RIGHT'),
        ('ALIGN',       (4, n - 3), (4, n - 1), 'RIGHT'),
        ('LINEABOVE',   (3, n - 3), (4, n - 3), 0.5, colors.black),
        ('NOSPLIT',     (0, 0),  (-1, -1)),
    ]))
    elementos.append(tabla_prods)

    # ── Construir PDF en memoria ──────────────────────────────────────────────
    doc.build(elementos)
    return buf.getvalue()
