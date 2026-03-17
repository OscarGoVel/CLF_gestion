#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de PDF Personalizado CLY
Sistema de ajuste automático a UNA página
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
import os

# Términos por default
TERMINOS_DEFAULT = {
    'vigencia': '30 DÍAS',
    'lugar_entrega': 'MÉRIDA',
    'tiempo_entrega': '15 DÍAS, A PARTIR DEL ANTICIPO DEL 60% Y SALDO CONTRAENTREGA',
    'moneda': 'TODOS LOS PRECIOS DE ESTA COTIZACIÓN SON EN MONEDA NACIONAL',
    'cambios': 'PRECIO SUJETO A CAMBIO SIN PREVIO AVISO'
}

class GeneradorPDFCLY:
    """Genera PDFs con formato CLY que se ajustan automáticamente a 1 página"""
    
    def __init__(self):
        self.color_oro = colors.HexColor('#D4AF37')
        self.color_negro = colors.HexColor('#1a1a1a')
        self.color_gris = colors.HexColor('#4a4a4a')
        self.logo_path = 'logo_clf.jpg'
        
        # Dimensiones de página
        self.ancho_pagina, self.alto_pagina = letter
        
        # Márgenes
        self.margen_izq = 0.5 * inch
        self.margen_der = 0.5 * inch
        self.margen_sup = 0.5 * inch
        self.margen_inf = 0.5 * inch
        
        # Área útil
        self.ancho_util = self.ancho_pagina - self.margen_izq - self.margen_der
    
    def calcular_parametros_tabla(self, num_productos):
        """
        Calcula el tamaño de fuente y alto de fila óptimo
        para que todos los productos quepan en una página
        """
        
        # Espacio real disponible para la tabla de productos:
        # Frame height = 792 - topMargin(36) - bottomMargin(133) = 623 pts
        # Consumido por: header_tbl(79) + spacer(9) + info_tbl(~80) + spacer(11) ≈ 179 pts
        # Disponible para tabla: ~444 pts — se usa 420 como margen de seguridad
        espacio_disponible = 420

        # Calcular alto por fila según cantidad
        if num_productos <= 10:
            fuente = 9
            alto_fila = 24
        elif num_productos <= 15:
            fuente = 8.5
            alto_fila = 20
        elif num_productos <= 20:
            fuente = 8
            alto_fila = 18
        elif num_productos <= 25:
            fuente = 7.5
            alto_fila = 15
        elif num_productos <= 30:
            fuente = 7
            alto_fila = 13
        elif num_productos <= 35:
            fuente = 6.5
            alto_fila = 12
        elif num_productos <= 40:
            fuente = 6.3
            alto_fila = 11
        elif num_productos <= 45:
            fuente = 6.1
            alto_fila = 10
        else:  # Hasta 50
            fuente = 6
            alto_fila = 9

        # Validar que cabe — contar: 1 header + productos + 3 filas de totales = +4
        alto_total_estimado = (num_productos + 4) * alto_fila

        if alto_total_estimado > espacio_disponible:
            # Ajustar más si es necesario
            factor_ajuste = espacio_disponible / alto_total_estimado
            alto_fila = alto_fila * factor_ajuste * 0.95  # 95% para margen de seguridad
            fuente = max(5.5, fuente * factor_ajuste)      # Mínimo 5.5pt

        return fuente, alto_fila

    def _ajustar_columnas(self, datos, ancho_total, min_col=0.4, max_col_texto=None):
        """
        Calcula anchos de columna ajustados al contenido, respetando ancho_total.

        Estrategia:
          1. Mide el texto más largo de cada columna (header + datos).
          2. Escala proporcionalmente para que la suma = ancho_total.
          3. Respeta un mínimo por columna (min_col en pulgadas).
          4. La(s) columna(s) de texto más ancha(s) absorben el espacio sobrante.

        Parámetros:
          datos       : lista de filas incluyendo el header como primera fila.
          ancho_total : ancho útil de página en puntos (doc.width).
          min_col     : ancho mínimo en pulgadas para columnas cortas.
          max_col_texto: índice de la columna que recibe espacio extra (None = auto).
        """
        from reportlab.pdfbase.pdfmetrics import stringWidth

        FUENTE      = 'Helvetica'
        FUENTE_BOLD = 'Helvetica-Bold'
        FONT_SIZE   = 8
        PADDING     = 10   # puntos de padding horizontal por celda

        if not datos:
            return []

        n_cols = max(len(fila) for fila in datos)

        # Medir ancho máximo de texto en cada columna
        anchos_texto = [0.0] * n_cols
        for fila_idx, fila in enumerate(datos):
            fuente = FUENTE_BOLD if fila_idx == 0 else FUENTE
            for col_idx, celda in enumerate(fila):
                texto = str(celda) if celda is not None else ''
                # Solo primera línea (por si hay saltos)
                linea = texto.split('\n')[0]
                w = stringWidth(linea, fuente, FONT_SIZE) + PADDING
                if w > anchos_texto[col_idx]:
                    anchos_texto[col_idx] = w

        # Mínimo absoluto
        min_pts = min_col * inch
        anchos_texto = [max(w, min_pts) for w in anchos_texto]

        # Escalar para que sumen exactamente ancho_total
        suma = sum(anchos_texto)
        if suma <= 0:
            return [ancho_total / n_cols] * n_cols

        factor = ancho_total / suma
        anchos = [w * factor for w in anchos_texto]

        # Si alguna quedó por debajo del mínimo, compensar con la más ancha
        for i in range(n_cols):
            if anchos[i] < min_pts:
                diferencia = min_pts - anchos[i]
                anchos[i] = min_pts
                # Quitar de la columna más ancha (texto principal)
                idx_max = max_col_texto if max_col_texto is not None else anchos.index(max(anchos))
                anchos[idx_max] -= diferencia

        return anchos

    def generar_cotizacion(self, conn, cotizacion_id, terminos_personalizados=None,
                             productos_override=None, totales_override=None):
        """
        Genera PDF de cotización en UNA página con ajuste automático.

        Args:
            conn: Conexión a BD
            cotizacion_id: ID de la cotización
            terminos_personalizados: Dict con términos o None para usar default
            productos_override: Lista de productos ya ajustados (impresión parcial)
            totales_override: Dict {subtotal, iva, total} recalculados (impresión parcial)
        """
        from datetime import datetime, timedelta

        cursor = conn.cursor()

        # Obtener datos de cotización
        cursor.execute("""
            SELECT c.folio, c.fecha, c.subtotal, c.iva, c.total, c.notas,
                   cl.nombre_comercial, cl.tipo, cl.contacto, cl.direccion
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cotizacion_id,))

        cotizacion = cursor.fetchone()
        if not cotizacion:
            return None

        folio, fecha, subtotal, iva, total, notas, cliente, tipo_cliente, contacto, direccion = cotizacion

        # Calcular VALIDO HASTA (30 días desde fecha)
        try:
            fecha_dt = datetime.strptime(fecha, '%Y-%m-%d')
        except:
            try:
                fecha_dt = datetime.strptime(fecha, '%d/%m/%Y')
            except:
                fecha_dt = datetime.now()
        valido_hasta = (fecha_dt + timedelta(days=30)).strftime('%d/%m/%Y')
        fecha_fmt = fecha_dt.strftime('%d/%m/%Y')

        # Obtener productos
        cursor.execute("""
            SELECT p.codigo, p.nombre, cd.cantidad, p.unidad_medida,
                   cd.precio_unitario, cd.subtotal, p.aplica_iva
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
            ORDER BY p.aplica_iva ASC
        """, (cotizacion_id,))

        productos_db = cursor.fetchall()

        # Impresión parcial: usar override si viene
        if productos_override is not None:
            productos = []
            for p in productos_override:
                productos.append((
                    '',
                    p['nombre'],
                    p['cantidad'],
                    p['unidad'],
                    p['precio_unitario'],
                    p['subtotal'],
                    1 if p['aplica_iva'] else 0
                ))
            if totales_override:
                subtotal = totales_override['subtotal']
                iva      = totales_override['iva']
                total    = totales_override['total']
        else:
            productos = productos_db

        # Calcular parámetros de tabla
        fuente_tabla, alto_fila = self.calcular_parametros_tabla(len(productos))

        # Rutas de salida
        CARPETA_COTIZACIONES = r'C:\Users\oscar\OneDrive\Documentos\CLF Sistema\cotizaciones'
        os.makedirs(CARPETA_COTIZACIONES, exist_ok=True)
        nombre_archivo = os.path.join(CARPETA_COTIZACIONES, f"Cotizacion_{folio}.pdf")

        # ── Documento con canvas para dibujar el footer ───────────────
        from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate
        from reportlab.lib.units import inch

        terminos = terminos_personalizados or TERMINOS_DEFAULT

        # Función que dibuja el footer en cada página
        def _footer(canvas, doc):
            canvas.saveState()
            W = doc.pagesize[0]
            H = doc.pagesize[1]
            margen = 0.5 * inch

            # ── Caja oscura footer ──
            box_h = 1.1 * inch
            box_y = margen - 4  # justo sobre el margen inferior
            canvas.setFillColor(colors.HexColor('#3d3d3d'))
            canvas.rect(margen, box_y, W - 2 * margen, box_h, fill=1, stroke=0)

            # Texto términos (izquierda)
            canvas.setFillColor(colors.white)
            canvas.setFont('Helvetica-Bold', 7)
            canvas.drawString(margen + 8, box_y + box_h - 14, 'TÉRMINOS Y CONDICIONES')
            canvas.setFont('Helvetica', 6.5)
            lineas = [
                f"1. VIGENCIA DE PRESUPUESTO: {terminos['vigencia']}.",
                f"2. LUGAR DE ENTREGA: {terminos['lugar_entrega']}",
                f"3. TIEMPO DE ENTREGA: {terminos['tiempo_entrega']}",
                terminos['moneda'],
                terminos['cambios'],
            ]
            y_txt = box_y + box_h - 26
            for linea in lineas:
                canvas.drawString(margen + 8, y_txt, linea)
                y_txt -= 9

            # Logo en el footer (derecha)
            logo_w = 0.75 * inch
            logo_x = W - margen - logo_w - 6
            logo_y = box_y + (box_h - logo_w) / 2
            if os.path.exists('logo_clf.jpg'):
                try:
                    canvas.drawImage('logo_clf.jpg', logo_x, logo_y,
                                     width=logo_w, height=logo_w,
                                     preserveAspectRatio=True, mask='auto')
                except:
                    pass

            # Nota inferior
            canvas.setFillColor(colors.HexColor('#555555'))
            canvas.setFont('Helvetica', 6.5)
            nota = 'Si usted tiene alguna duda, por favor, póngase en contacto con nosotros.'
            canvas.drawCentredString(W / 2, box_y - 12, nota)

            canvas.restoreState()

        # ── Configurar documento ──────────────────────────────────────
        footer_h = 1.35 * inch  # altura reservada para footer + nota
        doc = BaseDocTemplate(
            nombre_archivo,
            pagesize=letter,
            leftMargin=self.margen_izq,
            rightMargin=self.margen_der,
            topMargin=self.margen_sup,
            bottomMargin=self.margen_inf + footer_h,
        )
        frame = Frame(
            doc.leftMargin, doc.bottomMargin,
            doc.width, doc.height,
            id='main'
        )
        doc.addPageTemplates([PageTemplate(id='main', frames=frame, onPage=_footer)])

        elementos = []
        ancho = doc.width  # ancho útil real

        # ── 1. HEADER: Logo + Banner COTIZACIÓN ──────────────────────
        logo_cell = ''
        if os.path.exists(self.logo_path):
            try:
                logo_cell = Image(self.logo_path, width=1.1*inch, height=1.1*inch)
            except:
                logo_cell = ''

        style_banner = ParagraphStyle(
            'banner', fontSize=22, fontName='Helvetica-Bold',
            textColor=colors.white, alignment=TA_CENTER
        )
        banner_txt = Paragraph('COTIZACIÓN', style_banner)

        header_tbl = Table(
            [[logo_cell, banner_txt]],
            colWidths=[1.3*inch, ancho - 1.3*inch],
            rowHeights=[1.1*inch]
        )
        header_tbl.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, 0), self.color_oro),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (1, 0), (1, 0), 0),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(header_tbl)
        elementos.append(Spacer(1, 0.12*inch))

        # ── 2. INFO: Dirección empresa (izq) + Tabla cliente (der) ───
        style_addr = ParagraphStyle('addr', fontSize=8, leading=11,
                                    textColor=colors.HexColor('#333333'))
        addr_text = (
            'CALLE 17 NO. 56 DEPTO.74 ENTRE CALLE 12 Y CALLE 14.<br/>'
            'KANASÍN, YUCATÁN.<br/>'
            '<br/>'
            'C.P. 97370<br/>'
            'TELÉFONO: 9993633880'
        )
        addr_para = Paragraph(addr_text, style_addr)

        ubicacion = direccion or 'MÉRIDA'

        info_rows = [
            ['FECHA:',          fecha_fmt],
            ['CLIENTE:',        cliente or ''],
            ['UBICACIÓN:',      ubicacion],
            ['PRESUPUESTO NO.', folio],
            ['VALIDO HASTA',    valido_hasta],
        ]
        info_inner = Table(info_rows, colWidths=[1.3*inch, 1.7*inch])
        info_inner.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ]))

        izq_w = ancho - 3.1*inch
        info_tbl = Table([[addr_para, info_inner]], colWidths=[izq_w, 3.1*inch])
        info_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ]))
        elementos.append(info_tbl)
        elementos.append(Spacer(1, 0.15*inch))

        # ── 3. TABLA DE PRODUCTOS ─────────────────────────────────────
        datos_tabla = [['CONCEPTO', 'UNIDAD', 'CANTIDAD', 'P.U.', 'IMPORTE']]

        for prod in productos:
            _, nombre, cantidad, unidad, precio, subtotal_prod, aplica_iva = prod
            # Importe = subtotal_prod (sin IVA, la columna muestra precio sin IVA)
            datos_tabla.append([
                nombre,
                unidad or 'Pieza',
                f'{float(cantidad):g}',
                f'$ {float(precio):,.2f}',
                f'$ {float(subtotal_prod):,.2f}',
            ])

        # Filas vacías para llenar espacio visual (mínimo 8 filas de producto)
        while len(datos_tabla) < 9:
            datos_tabla.append(['', '', '', '', ''])

        # Filas de totales
        datos_tabla.append(['', '', '', 'SUBTOTAL', f'$ {subtotal:,.2f}'])
        datos_tabla.append(['', '', '', 'IVA',      f'$ {iva:,.2f}'])
        datos_tabla.append(['', '', '', 'TOTAL',    f'$ {total:,.2f}'])

        n_prod_rows = len(datos_tabla) - 1  # sin header
        col_w = self._ajustar_columnas(datos_tabla, ancho,
                                         min_col=0.5, max_col_texto=0)

        tabla_prods = Table(datos_tabla, colWidths=col_w, rowHeights=alto_fila)

        n = len(datos_tabla)
        estilo = TableStyle([
            # Header
            ('BACKGROUND',   (0, 0), (-1, 0),  self.color_negro),
            ('TEXTCOLOR',    (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',     (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0), (-1, 0),  fuente_tabla),
            ('ALIGN',        (0, 0), (-1, 0),  'CENTER'),
            # Contenido
            ('FONTNAME',     (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE',     (0, 1), (-1, -1), fuente_tabla),
            ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID',         (0, 0), (-1, n-4), 0.5, colors.HexColor('#cccccc')),
            # Alineaciones columnas
            ('ALIGN',        (1, 1), (1, -1),  'CENTER'),  # UNIDAD
            ('ALIGN',        (2, 1), (2, -1),  'CENTER'),  # CANTIDAD
            ('ALIGN',        (3, 1), (3, -1),  'RIGHT'),   # P.U.
            ('ALIGN',        (4, 1), (4, -1),  'RIGHT'),   # IMPORTE
            # Filas de totales (últimas 3)
            ('FONTNAME',     (3, n-3), (4, n-1), 'Helvetica-Bold'),
            ('ALIGN',        (3, n-3), (3, n-1), 'RIGHT'),
            ('ALIGN',        (4, n-3), (4, n-1), 'RIGHT'),
            ('LINEABOVE',    (3, n-3), (4, n-3), 0.5, colors.black),
            ('NOSPLIT',      (0, 0), (-1, -1)),
        ])
        tabla_prods.setStyle(estilo)
        elementos.append(tabla_prods)

        # ── Construir PDF ─────────────────────────────────────────────
        doc.build(elementos)
        return nombre_archivo

    def generar_nota_remision(self, conn, cotizacion_id,
                                productos_override=None, totales_override=None):
        """
        Genera PDF de nota de remisión en UNA página con ajuste automático.

        Args:
            conn: Conexión a BD
            cotizacion_id: ID de la cotización
            productos_override: Lista de productos ya ajustados (impresión parcial)
            totales_override: Dict {subtotal, iva, total} recalculados (impresión parcial)
        """
        cursor = conn.cursor()
        
        # Obtener datos de cotización
        cursor.execute("""
            SELECT c.folio, c.fecha, c.subtotal, c.iva, c.total, c.orden_compra, c.fecha_entrega,
                   cl.nombre_comercial, cl.tipo, cl.contacto, cl.direccion, cl.email
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cotizacion_id,))
        
        cotizacion = cursor.fetchone()
        if not cotizacion:
            return None
        
        folio, fecha, subtotal, iva, total, orden_compra, fecha_entrega, cliente, tipo_cliente, contacto, direccion, email = cotizacion
        
        # Obtener productos
        cursor.execute("""
            SELECT p.codigo, p.nombre, cd.cantidad, p.unidad_medida,
                   cd.precio_unitario, cd.total
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
        """, (cotizacion_id,))
        
        productos_db = cursor.fetchall()

        # Si hay impresión parcial, convertir override a formato compatible
        if productos_override is not None:
            # Override viene como lista de dicts del dialogo_impresion
            # Nota de remisión usa: (codigo, nombre, cantidad, unidad, precio_u, total)
            productos = []
            for p in productos_override:
                total_prod = p['subtotal'] + (p['subtotal'] * 0.16 if p['aplica_iva'] else 0)
                productos.append((
                    '',
                    p['nombre'],
                    p['cantidad'],
                    p['unidad'],
                    p['precio_unitario'],
                    total_prod
                ))
            if totales_override:
                subtotal = totales_override['subtotal']
                iva      = totales_override['iva']
                total    = totales_override['total']
        else:
            productos = productos_db

        # Calcular parámetros de tabla
        fuente_tabla, alto_fila = self.calcular_parametros_tabla(len(productos))
        
        # Generar número de nota (basado en folio)
        num_nota = folio.replace('COT-', 'REM-')
        
        # Crear PDF
        CARPETA_REMISIONES = r'C:\Users\oscar\OneDrive\Documentos\Gestion CLF\notas de remision'
        os.makedirs(CARPETA_REMISIONES, exist_ok=True)
        nombre_archivo = os.path.join(CARPETA_REMISIONES, f"NotaRemision_{num_nota}.pdf")
        doc = SimpleDocTemplate(
            nombre_archivo,
            pagesize=letter,
            leftMargin=self.margen_izq,
            rightMargin=self.margen_der,
            topMargin=self.margen_sup,
            bottomMargin=self.margen_inf
        )
        
        elementos = []
        
        # Logo y datos empresa
        if os.path.exists(self.logo_path):
            try:
                logo = Image(self.logo_path, width=1*inch, height=1*inch)
                elementos.append(logo)
                elementos.append(Spacer(1, 0.1*inch))
            except:
                pass
        
        # Datos empresa
        datos_empresa = [
            ['Comercializadora Logística Y Fuerza Yucateca'],
            ['Calle 17 No. 56 Depto.74 entre calle 12 y calle 14'],
            ['Kanasín, Yucatán'],
            ['C.P. 97370'],
            ['Teléfono: 9993633880']
        ]
        
        tabla_empresa = Table(datos_empresa, colWidths=[3*inch])
        tabla_empresa.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (0, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ]))
        elementos.append(tabla_empresa)
        elementos.append(Spacer(1, 0.1*inch))
        
        # Barra NOTA REMISIÓN + Cuadro info
        # Crear tabla combinada
        oc_display = orden_compra if orden_compra else "-"
        solicitante_display = contacto if tipo_cliente == "Gobierno" else "-"
        
        info_header = [
            ['NOTA REMISIÓN', 'No. Nota', num_nota],
            ['', 'OC', oc_display],
            ['', 'Solicitante', solicitante_display],
            ['', 'Fecha', fecha_entrega or fecha]
        ]
        
        tabla_header = Table(info_header, colWidths=[4*inch, 1.2*inch, 2*inch])
        tabla_header.setStyle(TableStyle([
            # Barra título
            ('BACKGROUND', (0, 0), (0, -1), self.color_oro),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (0, -1), 14),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('VALIGN', (0, 0), (0, -1), 'MIDDLE'),
            ('SPAN', (0, 0), (0, -1)),
            
            # Cuadro info
            ('GRID', (1, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (1, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ]))
        elementos.append(tabla_header)
        elementos.append(Spacer(1, 0.15*inch))
        
        # Cliente
        if tipo_cliente == "Gobierno":
            cliente_info = f"""<b>Cliente:</b> {cliente}<br/>
            <b>Dirección:</b> {direccion or '-'}<br/>
            <b>Contacto:</b> {contacto or '-'}<br/>
            <b>Email:</b> {email or '-'}"""
        else:
            cliente_info = f"""<b>Cliente:</b> {cliente}<br/>
            <b>Dirección:</b> {direccion or '-'}<br/>
            <b>Email:</b> {email or '-'}"""
        
        style_cliente = ParagraphStyle(
            'cliente',
            fontSize=8,
            leading=10
        )
        
        parrafo_cliente = Paragraph(cliente_info, style_cliente)
        elementos.append(parrafo_cliente)
        elementos.append(Spacer(1, 0.15*inch))
        
        # Tabla de productos (SIN separación por IVA)
        datos_tabla = [
            ['No.', 'Descripción', 'Unidad', 'Cantidad', 'P.U.', 'Importe']
        ]
        
        for idx, prod in enumerate(productos, 1):
            codigo, nombre, cantidad, unidad, precio, total_prod = prod
            datos_tabla.append([
                str(idx),
                f"{codigo} - {nombre}",
                unidad,
                f"{cantidad:.2f}",
                f"${precio:,.2f}",
                f"${total_prod:,.2f}"
            ])
        
        anchos_col = self._ajustar_columnas(datos_tabla, self.ancho_util,
                                              min_col=0.4, max_col_texto=1)

        tabla_productos = Table(datos_tabla, colWidths=anchos_col, rowHeights=alto_fila)
        tabla_productos.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), self.color_negro),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), fuente_tabla),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            
            # Contenido
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), fuente_tabla),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'CENTER'),
            ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
            ('ALIGN', (5, 1), (5, -1), 'RIGHT'),
        ]))
        elementos.append(tabla_productos)
        elementos.append(Spacer(1, 0.15*inch))
        
        # Totales
        datos_totales = [
            ['SUBTOTAL', f"${subtotal:,.2f}"],
            ['IVA', f"${iva:,.2f}"],
            ['TOTAL', f"${total:,.2f}"]
        ]
        
        tabla_totales = Table(datos_totales, colWidths=[1.5*inch, 1.5*inch])
        tabla_totales.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 1), 9),
            ('FONTSIZE', (0, 2), (-1, 2), 11),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ]))
        
        # Alinear a la derecha
        tabla_totales.hAlign = 'RIGHT'
        elementos.append(tabla_totales)
        elementos.append(Spacer(1, 0.2*inch))
        
        # Condiciones
        texto_condiciones = """
        <b>1.-</b> Este documento no es válido como comprobante fiscal<br/>
        <b>2.-</b> Favor de revisar la mercancía al momento de la entrega.<br/>
        <b>3.-</b> No se aceptan devoluciones ni reclamaciones después de la entrega.<br/>
        <b>4.-</b> Para cualquier aclaración o duda, favor de comunicarse a "clfyucateca@gmail.com"
        """
        
        style_condiciones = ParagraphStyle(
            'condiciones',
            fontSize=7,
            leading=9,
            leftIndent=10
        )
        
        parrafo_condiciones = Paragraph(texto_condiciones, style_condiciones)
        elementos.append(parrafo_condiciones)
        elementos.append(Spacer(1, 0.15*inch))
        
        # Lugar de entrega
        texto_lugar = "<b>Lugar de entrega:</b> Expenitenciaria"
        parrafo_lugar = Paragraph(texto_lugar, style_condiciones)
        elementos.append(parrafo_lugar)
        elementos.append(Spacer(1, 0.1*inch))
        
        # Observaciones
        texto_obs = "<b>Observaciones:</b> _____________________________________________"
        parrafo_obs = Paragraph(texto_obs, style_condiciones)
        elementos.append(parrafo_obs)
        elementos.append(Spacer(1, 0.3*inch))
        
        # Firma
        linea_firma = Table([['_' * 40]], colWidths=[3*inch])
        linea_firma.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        elementos.append(linea_firma)
        
        texto_firma = "Firma de recepción<br/>Nombre y Fecha"
        style_firma = ParagraphStyle('firma', fontSize=8, alignment=TA_CENTER)
        parrafo_firma = Paragraph(texto_firma, style_firma)
        elementos.append(parrafo_firma)
        
        # Construir PDF
        doc.build(elementos)
        
        return nombre_archivo

    # ── helpers internos de PDF ───────────────────────────────────────────────

    def _estilos_doc(self):
        """Devuelve estilos reutilizables para documentos internos."""
        style_titulo = ParagraphStyle(
            'Titulo', fontSize=13, alignment=TA_CENTER,
            textColor=self.color_oro, spaceAfter=4, fontName='Helvetica-Bold')
        style_sub = ParagraphStyle(
            'Sub', fontSize=8, alignment=TA_CENTER,
            textColor=self.color_gris, spaceAfter=10)
        style_celda = ParagraphStyle(
            'Celda', fontSize=7.5, leading=9, wordWrap='CJK')
        return style_titulo, style_sub, style_celda

    def _detectar_grupos(self, filas_datos, col_idx):
        """
        Detecta grupos de filas consecutivas con el mismo valor en col_idx.

        Retorna lista de (inicio, fin) en índices de fila de datos (base-0).
        Solo incluye grupos con más de 1 fila (los que hay que fusionar).
        """
        grupos = []
        i = 0
        while i < len(filas_datos):
            j = i + 1
            while j < len(filas_datos) and filas_datos[j][col_idx] == filas_datos[i][col_idx]:
                j += 1
            if j - i > 1:
                grupos.append((i, j - 1))
            i = j
        return grupos

    def _construir_doc_con_grupos(self, ruta, titulo, subtitulo,
                                   encabezado, filas_datos, col_grupo, idx_col_texto):
        """
        Construye el PDF fusionando celdas verticalmente en col_grupo
        cuando hay filas consecutivas con el mismo valor.

        Args:
            encabezado   : lista con los textos de cabecera
            filas_datos  : filas de datos sin encabezado ni fila de total
            col_grupo    : índice de columna sobre la que agrupar/fusionar
            idx_col_texto: columna más ancha (para ajuste de anchos)
        """
        from datetime import datetime as dt

        # ── 1. Calcular grupos y subtotales de grupo ─────────────────────
        grupos = self._detectar_grupos(filas_datos, col_grupo)
        # Convertir a set para lookup rápido: qué filas son inicio de grupo
        inicio_grupo = {g[0] for g in grupos}
        rango_grupos = {}   # fila_inicio → fila_fin
        for g0, g1 in grupos:
            for k in range(g0, g1 + 1):
                rango_grupos[k] = (g0, g1)

        # ── 2. Construir filas para la tabla (copiar y blanquear dups) ────
        filas_tabla = [encabezado]
        for idx, fila in enumerate(filas_datos):
            fila_copia = list(fila)
            # Si esta fila está dentro de un grupo y NO es la primera → limpiar col_grupo
            if idx in rango_grupos and idx != rango_grupos[idx][0]:
                fila_copia[col_grupo] = ''
            filas_tabla.append(fila_copia)

        # Calcular total global (última columna numérica)
        total = 0.0
        for fila in filas_datos:
            txt = str(fila[-1]).replace('$', '').replace(',', '').strip()
            try:
                total += float(txt)
            except ValueError:
                pass

        filas_tabla.append([''] * (len(encabezado) - 2) + ['TOTAL:', f"${total:,.2f}"])

        # ── 3. Ajustar anchos de columna ──────────────────────────────────
        _ancho = self.ancho_pagina - self.margen_izq - self.margen_der
        col_widths = self._ajustar_columnas(filas_tabla, _ancho,
                                            min_col=0.4, max_col_texto=idx_col_texto)

        # ── 4. Construir TableStyle ───────────────────────────────────────
        n_total = len(filas_tabla)   # incluyendo encabezado y total
        # Offset: fila 0 = encabezado, filas 1..n-2 = datos, fila n-1 = total

        style_cmds = [
            # Encabezado
            ('BACKGROUND',   (0, 0),  (-1, 0),       self.color_negro),
            ('TEXTCOLOR',    (0, 0),  (-1, 0),       colors.white),
            ('FONTNAME',     (0, 0),  (-1, 0),       'Helvetica-Bold'),
            ('FONTSIZE',     (0, 0),  (-1, 0),       8),
            ('LINEBELOW',    (0, 0),  (-1, 0),       1.2, self.color_oro),
            # Datos (base)
            ('FONTNAME',     (0, 1),  (-1, n_total-2), 'Helvetica'),
            ('FONTSIZE',     (0, 1),  (-1, n_total-2), 7.5),
            # Fila total
            ('BACKGROUND',   (0, n_total-1), (-1, n_total-1), self.color_negro),
            ('TEXTCOLOR',    (0, n_total-1), (-1, n_total-1), colors.white),
            ('FONTNAME',     (0, n_total-1), (-1, n_total-1), 'Helvetica-Bold'),
            ('FONTSIZE',     (0, n_total-1), (-1, n_total-1), 8.5),
            ('TEXTCOLOR',    (-1, n_total-1), (-1, n_total-1), self.color_oro),
            # Alineación numérica (últimas 3 cols)
            ('ALIGN',        (-3, 0), (-1, -1), 'RIGHT'),
            # Grid
            ('GRID',         (0, 0),  (-1, -1), 0.3, colors.HexColor('#d0d0d0')),
            # Padding
            ('TOPPADDING',   (0, 0),  (-1, -1), 5),
            ('BOTTOMPADDING',(0, 0),  (-1, -1), 5),
            ('LEFTPADDING',  (0, 0),  (-1, -1), 5),
            ('RIGHTPADDING', (0, 0),  (-1, -1), 5),
        ]

        # Fondos alternantes por GRUPO (no por fila)
        BLAN = colors.white
        GRIS = colors.HexColor('#f2f2f2')
        grupo_color = {}   # fila_inicio_datos → color
        color_toggle = True
        i = 0
        while i < len(filas_datos):
            if i in rango_grupos and rango_grupos[i][0] == i:
                g0, g1 = rango_grupos[i]
                grupo_color[g0] = BLAN if color_toggle else GRIS
                color_toggle = not color_toggle
                i = g1 + 1
            else:
                grupo_color[i] = BLAN if color_toggle else GRIS
                color_toggle = not color_toggle
                i += 1

        for fila_datos_idx, col in grupo_color.items():
            r = fila_datos_idx + 1   # offset por encabezado
            style_cmds.append(('BACKGROUND', (0, r), (-1, r), col))

        # Si hay grupo multi-fila → también pintar las filas siguientes con mismo color
        for g0, g1 in grupos:
            r0 = g0 + 1
            r1 = g1 + 1
            col = grupo_color.get(g0, BLAN)
            for r in range(r0 + 1, r1 + 1):
                style_cmds.append(('BACKGROUND', (0, r), (-1, r), col))

        # SPAN y alineación vertical para celdas agrupadas
        for g0, g1 in grupos:
            r0 = g0 + 1   # offset por encabezado
            r1 = g1 + 1
            style_cmds.append(('SPAN',       (col_grupo, r0), (col_grupo, r1)))
            style_cmds.append(('VALIGN',     (col_grupo, r0), (col_grupo, r1), 'MIDDLE'))
            style_cmds.append(('FONTNAME',   (col_grupo, r0), (col_grupo, r0), 'Helvetica-Bold'))
            # Línea separadora debajo del grupo
            if r1 < n_total - 1:
                style_cmds.append(('LINEBELOW', (0, r1), (-1, r1), 0.8, colors.HexColor('#aaaaaa')))

        # ── 5. Construir y guardar ────────────────────────────────────────
        doc = SimpleDocTemplate(
            ruta, pagesize=letter,
            leftMargin=self.margen_izq, rightMargin=self.margen_der,
            topMargin=self.margen_sup,  bottomMargin=self.margen_inf
        )
        style_titulo, style_sub, _ = self._estilos_doc()
        tabla = Table(filas_tabla, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(TableStyle(style_cmds))

        doc.build([
            Paragraph(titulo,    style_titulo),
            Paragraph(subtitulo, style_sub),
            tabla,
        ])

    # ─────────────────────────────────────────────────────────────────────────

    def generar_presupuesto_compra(self, productos, ruta_salida):
        """
        Genera PDF de Presupuesto de Compra.
        Columnas: Cotización | Producto | Unidad | A Comprar | Costo | Subtotal
        Las filas de la misma cotización se agrupan fusionando la primera celda.

        Args:
            productos : lista de dicts con keys:
                        folio, oc, nombre, unidad, a_comprar, costo_max
        """
        from datetime import datetime as dt
        try:
            encabezado = ['Cotización', 'Producto', 'Unidad', 'A Comprar', 'Costo', 'Subtotal']

            # Ordenar por folio para que las mismas cotizaciones queden juntas
            prods_ord = sorted(productos, key=lambda p: p.get('folio', ''))

            filas_datos = []
            for p in prods_ord:
                subtotal = p.get('a_comprar', 0) * p.get('costo_max', 0)
                oc       = p.get('oc', '') or ''
                # La clave de agrupación es folio+oc (para que el SPAN sea exacto)
                cot_key  = f"{p.get('folio', '')}\n{'OC: ' + oc if oc else 'Sin OC'}"
                filas_datos.append([
                    cot_key,
                    p.get('nombre', ''),
                    p.get('unidad', 'Pza'),
                    f"{p.get('a_comprar', 0):g}",
                    f"${p.get('costo_max', 0):,.2f}",
                    f"${subtotal:,.2f}",
                ])

            self._construir_doc_con_grupos(
                ruta_salida,
                "PRESUPUESTO DE COMPRA",
                f"Comercializadora, Logistica y Fuerza Yucateca  |  {dt.now().strftime('%d/%m/%Y')}",
                encabezado, filas_datos,
                col_grupo=0,
                idx_col_texto=1,
            )
            return True

        except Exception as e:
            print(f"Error generando presupuesto: {e}")
            return False

    def generar_lista_compras(self, productos, ruta_salida):
        """
        Genera PDF de Lista de Compras agrupada por proveedor principal.
        Columnas: Proveedor | Producto | Unidad | A Comprar | Costo | Subtotal
        Las filas del mismo proveedor se agrupan fusionando la primera celda.

        Args:
            productos : lista de dicts con keys:
                        proveedor, nombre, unidad, a_comprar, costo_max
        """
        from datetime import datetime as dt
        try:
            encabezado = ['Proveedor', 'Producto', 'Unidad', 'A Comprar', 'Costo', 'Subtotal']

            # Ordenar por proveedor
            prods_ord = sorted(
                productos,
                key=lambda p: (p.get('proveedor') or 'Sin proveedor').lower()
            )

            filas_datos = []
            for p in prods_ord:
                subtotal = p.get('a_comprar', 0) * p.get('costo_max', 0)
                prov     = p.get('proveedor', '') or 'Sin proveedor'
                filas_datos.append([
                    prov,
                    p.get('nombre', ''),
                    p.get('unidad', 'Pza'),
                    f"{p.get('a_comprar', 0):g}",
                    f"${p.get('costo_max', 0):,.2f}",
                    f"${subtotal:,.2f}",
                ])

            self._construir_doc_con_grupos(
                ruta_salida,
                "LISTA DE COMPRAS",
                f"Comercializadora, Logistica y Fuerza Yucateca  |  {dt.now().strftime('%d/%m/%Y')}",
                encabezado, filas_datos,
                col_grupo=0,
                idx_col_texto=1,
            )
            return True

        except Exception as e:
            print(f"Error generando lista de compras: {e}")
            return False


# Función de prueba
if __name__ == '__main__':
    print("Generador PDF CLY - Sistema de ajuste automático a 1 página")
    print("Este módulo debe ser importado desde main.py")
