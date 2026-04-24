# -*- coding: utf-8 -*-
"""
web_app/pdf_estado_cuenta.py
Genera el PDF de Estado de Cuenta de Pedidos.

Secciones:
  1. Header: logo + banner
  2. Info cliente/corporativo
  3. Resumen del período (saldos)
  4. Detalle de pedidos con saldo pendiente
"""

import io
import os
from datetime import datetime, date
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

# ── Colores ───────────────────────────────────────────────────────────────────
_ORO       = colors.HexColor('#D4AF37')
_NEGRO     = colors.HexColor('#1a1a1a')
_GRIS_GRID = colors.HexColor('#cccccc')
_FOOTER_BG = colors.HexColor('#3d3d3d')
_AZUL_HDR  = colors.HexColor('#1e3a5f')
_AMARILLO  = colors.HexColor('#fffbe6')

_COLORES_ESTADO = {
    "Pendiente":              colors.HexColor('#fff9c4'),
    "Programada":             colors.HexColor('#dbeafe'),
    "Parcialmente Entregada": colors.HexColor('#ede9fe'),
    "Entregada":              colors.HexColor('#dcfce7'),
    "Facturada":              colors.HexColor('#cffafe'),
    "Pagada":                 colors.HexColor('#bbf7d0'),
    "Cancelada":              colors.HexColor('#f1f5f9'),
}

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


def _fmt_fecha(v) -> str:
    if v is None:
        return "—"
    if hasattr(v, 'strftime'):
        return v.strftime('%d/%m/%Y')
    s = str(v)[:10]
    try:
        return datetime.strptime(s, '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        return s


def _fmt_money(v) -> str:
    return f"$ {_f(v):,.2f}"


def _cols(cur):
    return [d[0] for d in cur.description]


def generar_pdf_estado_cuenta(empresa_db: str, filtros: dict) -> bytes:
    """
    Genera el PDF de Estado de Cuenta y devuelve bytes.

    filtros keys: corporativo_id, cliente_nombre, desde, hasta, estado
    """
    hoy = date.today()
    desde_str = filtros.get("desde") or f"{hoy.year}-01-01"
    hasta_str  = filtros.get("hasta") or hoy.isoformat()
    corp_id    = filtros.get("corporativo_id")
    cli_nombre = filtros.get("cliente_nombre", "")
    fil_estado = filtros.get("estado", "Todos")

    with get_pool_empresa(empresa_db).conexion() as (_, cur):

        # ── Info corporativo o cliente ────────────────────────────────────────
        corp_nombre = None
        clientes_info = []

        if corp_id:
            cur.execute("SELECT nombre FROM corporativos WHERE id = %s", (corp_id,))
            row = cur.fetchone()
            corp_nombre = row[0] if row else "Corporativo"
            cur.execute(
                """
                SELECT nombre_comercial, rfc, contacto, telefono, email
                FROM clientes
                WHERE corporativo_id = %s AND activo = TRUE
                ORDER BY nombre_comercial
                """,
                (corp_id,),
            )
            clientes_info = [dict(zip(_cols(cur), r)) for r in cur.fetchall()]
        elif cli_nombre:
            cur.execute(
                """
                SELECT nombre_comercial, rfc, contacto, telefono, email,
                       regimen_fiscal
                FROM clientes
                WHERE nombre_comercial = %s AND activo = TRUE
                LIMIT 1
                """,
                (cli_nombre,),
            )
            row = cur.fetchone()
            if row:
                clientes_info = [dict(zip(_cols(cur), row))]

        # ── Construir WHERE ───────────────────────────────────────────────────
        where_parts = ["c.estado != 'Cancelada'", "c.fecha >= %s", "c.fecha <= %s"]
        params = [desde_str, hasta_str]

        if corp_id:
            where_parts.append("cl.corporativo_id = %s")
            params.append(int(corp_id))
        elif cli_nombre:
            where_parts.append("cl.nombre_comercial = %s")
            params.append(cli_nombre)

        if fil_estado and fil_estado != "Todos":
            where_parts.append("c.estado = %s")
            params.append(fil_estado)

        where = " AND ".join(where_parts)

        # ── Resumen ───────────────────────────────────────────────────────────
        cur.execute(
            f"""
            SELECT
                COUNT(*)                                              AS n_total,
                COALESCE(SUM(c.total), 0)                            AS monto_total,
                SUM(CASE WHEN c.estado IN ('Entregada','Facturada','Pagada')
                    THEN 1 ELSE 0 END)                               AS n_entregadas,
                COALESCE(SUM(CASE WHEN c.estado IN ('Entregada','Facturada','Pagada')
                    THEN c.total ELSE 0 END), 0)                     AS monto_entregadas,
                COALESCE(SUM(CASE WHEN c.estado IN
                    ('Programada','Parcialmente Entregada')
                    THEN c.total ELSE 0 END), 0)                     AS monto_transito,
                COALESCE(SUM(CASE WHEN c.estado IN
                    ('Programada','Parcialmente Entregada','Entregada','Facturada','Pagada')
                    THEN COALESCE(c.monto_pagado, 0) ELSE 0 END), 0)  AS monto_cobrado,
                COALESCE(SUM(CASE WHEN c.estado IN
                    ('Programada','Parcialmente Entregada','Entregada','Facturada')
                    AND (c.total - COALESCE(c.monto_pagado,0)) > 0.01
                    THEN c.total - COALESCE(c.monto_pagado,0) ELSE 0 END), 0) AS saldo_pend
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE {where}
            """,
            params,
        )
        res = cur.fetchone()
        resumen = dict(zip(_cols(cur), res)) if res else {}

        # ── Detalle de pedidos con saldo ──────────────────────────────────────
        cur.execute(
            f"""
            SELECT c.folio, c.fecha, cl.nombre_comercial,
                   c.total, c.monto_pagado,
                   c.total - COALESCE(c.monto_pagado,0) AS saldo,
                   c.estado, c.orden_compra
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE {where}
              AND c.estado IN
                  ('Programada','Parcialmente Entregada','Entregada','Facturada')
              AND (c.total - COALESCE(c.monto_pagado,0)) > 0.01
            ORDER BY cl.nombre_comercial, c.fecha, c.folio
            """,
            params,
        )
        detalle = [dict(zip(_cols(cur), r)) for r in cur.fetchall()]

    if not resumen.get("n_total"):
        raise ValueError("No hay datos para el período y filtros seleccionados")

    # ── Construir PDF ─────────────────────────────────────────────────────────
    logo_header = _resolver_logo('assets/logo_clf_header')
    logo_footer = _resolver_logo('assets/logo_clf_footer')
    buf = io.BytesIO()

    fecha_gen = datetime.now().strftime('%d/%m/%Y %H:%M')
    titulo_nombre = corp_nombre or cli_nombre or "Todos los clientes"

    def _footer(canvas, doc):
        canvas.saveState()
        W = doc.pagesize[0]
        box_h, box_y = 0.75 * inch, _M - 4
        canvas.setFillColor(_FOOTER_BG)
        canvas.rect(_M, box_y, W - 2 * _M, box_h, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 7)
        canvas.drawString(_M + 8, box_y + box_h - 14, 'ESTADO DE CUENTA DE PEDIDOS — DOCUMENTO INTERNO')
        canvas.setFont('Helvetica', 6.5)
        canvas.drawString(_M + 8, box_y + box_h - 26, f'Período: {_fmt_fecha(desde_str)} al {_fmt_fecha(hasta_str)}')
        canvas.drawString(_M + 8, box_y + box_h - 38, f'Generado: {fecha_gen}')
        if os.path.exists(logo_footer):
            try:
                lw = 0.5 * inch
                canvas.drawImage(logo_footer, W - _M - lw - 6,
                                 box_y + (box_h - lw) / 2, width=lw, height=lw,
                                 preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        canvas.setFillColor(colors.HexColor('#555555'))
        canvas.setFont('Helvetica', 6)
        canvas.drawCentredString(W / 2, box_y - 10,
                                 f'Pág. {doc.page}  ·  CLF Gestión')
        canvas.restoreState()

    footer_h = 1.0 * inch
    doc = BaseDocTemplate(buf, pagesize=letter,
                          leftMargin=_M, rightMargin=_M,
                          topMargin=_M, bottomMargin=_M + footer_h)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')
    doc.addPageTemplates([PageTemplate(id='main', frames=frame, onPage=_footer)])

    elem = []
    ancho = doc.width

    # ── 1. HEADER ─────────────────────────────────────────────────────────────
    logo_cell = ''
    if os.path.exists(logo_header):
        try:
            logo_cell = Image(logo_header, width=1.1 * inch, height=1.1 * inch)
        except Exception:
            pass

    banner = Paragraph(
        'ESTADO DE CUENTA',
        ParagraphStyle('banner', fontSize=17, fontName='Helvetica-Bold',
                       textColor=colors.white, alignment=TA_CENTER),
    )
    hdr = Table([[logo_cell, banner]],
                colWidths=[1.3 * inch, ancho - 1.3 * inch],
                rowHeights=[1.1 * inch])
    hdr.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, 0), _ORO),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',  (0, 0), (0, 0), 'CENTER'),
        ('LEFTPADDING', (1, 0), (1, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elem.append(hdr)
    elem.append(Spacer(1, 0.08 * inch))

    # ── 2. INFO CLIENTE/CORPORATIVO ───────────────────────────────────────────
    st8 = ParagraphStyle('info8', fontSize=8, leading=11)
    st8b = ParagraphStyle('info8b', fontSize=8, leading=11, fontName='Helvetica-Bold')

    info_rows = [
        ['PERÍODO:', f'{_fmt_fecha(desde_str)} al {_fmt_fecha(hasta_str)}'],
        ['FILTRO ESTADO:', fil_estado if fil_estado != "Todos" else "Todos"],
    ]
    if corp_nombre:
        info_rows.insert(0, ['CORPORATIVO:', corp_nombre])
    elif cli_nombre:
        info_rows.insert(0, ['CLIENTE:', cli_nombre])
        if clientes_info:
            c = clientes_info[0]
            if c.get('rfc'):
                info_rows.insert(1, ['RFC:', c['rfc']])
            if c.get('contacto'):
                info_rows.append(['CONTACTO:', c['contacto']])
            if c.get('telefono'):
                info_rows.append(['TEL:', c['telefono']])

    info_tbl = Table(info_rows, colWidths=[1.3 * inch, 3.0 * inch])
    info_tbl.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
    ]))

    # Si es corporativo, tabla de clientes al lado
    if corp_nombre and clientes_info:
        corp_data = [['CLIENTES DEL GRUPO']]
        for c in clientes_info:
            corp_data.append([f"{c['nombre_comercial']}  {c.get('rfc','') or ''}"])
        corp_tbl = Table(corp_data, colWidths=[ancho - 4.5 * inch])
        corp_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), _AZUL_HDR),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME',   (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',   (0, 0), (-1, -1), 7.5),
            ('GRID',       (0, 0), (-1, -1), 0.5, _GRIS_GRID),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ]))
        lado_izq = Table([[info_tbl, corp_tbl]],
                          colWidths=[4.5 * inch, ancho - 4.5 * inch])
        lado_izq.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elem.append(lado_izq)
    else:
        elem.append(info_tbl)

    elem.append(Spacer(1, 0.1 * inch))

    # ── 3. RESUMEN DEL PERÍODO ────────────────────────────────────────────────
    elem.append(Paragraph(
        'RESUMEN DEL PERÍODO',
        ParagraphStyle('sec_hdr', fontSize=8, fontName='Helvetica-Bold',
                       textColor=colors.white, backColor=_AZUL_HDR,
                       leftIndent=5, spaceAfter=0),
    ))

    n_tot   = int(resumen.get('n_total', 0))
    n_entr  = int(resumen.get('n_entregadas', 0))
    res_data = [
        ['CONCEPTO', 'CANTIDAD', 'MONTO'],
        ['Pedidos en el período',       str(n_tot),   _fmt_money(resumen.get('monto_total', 0))],
        ['Pedidos entregados',          str(n_entr),  _fmt_money(resumen.get('monto_entregadas', 0))],
        ['Pedidos en tránsito',         '—',          _fmt_money(resumen.get('monto_transito', 0))],
        ['Total cobrado',               '—',          _fmt_money(resumen.get('monto_cobrado', 0))],
        ['SALDO PENDIENTE DE COBRO',    '—',          _fmt_money(resumen.get('saldo_pend', 0))],
    ]
    res_widths = [ancho * 0.55, ancho * 0.15, ancho * 0.30]
    res_tbl = Table(res_data, colWidths=res_widths)
    res_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), _NEGRO),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('FONTNAME',      (0, 1), (-1, -2), 'Helvetica'),
        ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND',    (0, -1), (-1, -1), _AMARILLO),
        ('GRID',          (0, 0), (-1, -1), 0.5, _GRIS_GRID),
        ('ALIGN',         (1, 0), (2, -1), 'RIGHT'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('LINEABOVE',     (0, -1), (-1, -1), 1.0, _NEGRO),
    ]))
    elem.append(res_tbl)
    elem.append(Spacer(1, 0.12 * inch))

    # ── 4. DETALLE DE PEDIDOS CON SALDO ──────────────────────────────────────
    if detalle:
        elem.append(Paragraph(
            'PEDIDOS CON SALDO PENDIENTE',
            ParagraphStyle('sec_hdr2', fontSize=8, fontName='Helvetica-Bold',
                           textColor=colors.white, backColor=_AZUL_HDR,
                           leftIndent=5, spaceAfter=0),
        ))

        det_data = [['FOLIO', 'FECHA', 'CLIENTE', 'TOTAL', 'SALDO', 'ESTADO', 'O.C.']]
        for d in detalle:
            det_data.append([
                d['folio'],
                _fmt_fecha(d['fecha']),
                d['nombre_comercial'],
                _fmt_money(d['total']),
                _fmt_money(d['saldo']),
                d['estado'],
                d.get('orden_compra') or '—',
            ])
        # Totales
        tot_total = sum(_f(d['total']) for d in detalle)
        tot_saldo  = sum(_f(d['saldo'])  for d in detalle)
        det_data.append(['TOTAL', '', '', _fmt_money(tot_total), _fmt_money(tot_saldo), '', ''])

        det_widths = [
            ancho * 0.12,  # folio
            ancho * 0.09,  # fecha
            ancho * 0.26,  # cliente
            ancho * 0.12,  # total
            ancho * 0.12,  # saldo
            ancho * 0.17,  # estado
            ancho * 0.12,  # OC
        ]

        n_det = len(det_data)
        # Calcular font size
        fs = 7.5 if n_det <= 20 else (7.0 if n_det <= 35 else 6.5)

        det_tbl = Table(det_data, colWidths=det_widths, rowHeights=None)

        # Estilos base
        style_cmds = [
            ('BACKGROUND',    (0, 0), (-1, 0), _NEGRO),
            ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
            ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, -1), fs),
            ('FONTNAME',      (0, 1), (-1, -2), 'Helvetica'),
            ('GRID',          (0, 0), (-1, n_det - 2), 0.5, _GRIS_GRID),
            ('TOPPADDING',    (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('ALIGN',         (3, 0), (4, -1), 'RIGHT'),
            ('ALIGN',         (5, 0), (5, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            # Fila total
            ('BACKGROUND',    (0, -1), (-1, -1), _AMARILLO),
            ('FONTNAME',      (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE',     (0, -1), (-1, -1), 1.0, _NEGRO),
        ]

        # Color por estado en filas de datos
        for i, d in enumerate(detalle, start=1):
            color = _COLORES_ESTADO.get(d['estado'])
            if color:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), color))

        det_tbl.setStyle(TableStyle(style_cmds))
        elem.append(det_tbl)

    doc.build(elem)
    return buf.getvalue()
