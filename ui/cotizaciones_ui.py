#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/cotizaciones_ui.py
Componente CotizacionesUI — sección cotizaciones, acciones, seguimiento, documentos.

Uso:
    from ui.cotizaciones_ui import CotizacionesUI
    self.cotizaciones_ui = CotizacionesUI(self)
    self.cotizaciones_ui.crear_seccion()
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import os
import shutil
import subprocess
import platform
from datetime import datetime

from modules.cotizaciones import VentanaCotizacion
from ui.generador_pdf_cly import GeneradorPDFCLY
from ui.dialogo_impresion import DialogoImpresion
from modules.estado_de_cuenta import VentanaEstadoCuenta
from modules.entregas import VentanaEntregaParcial
from modules.vinculacion import PanelVinculacion, detectar_pendientes


class CotizacionesUI:
    """
    Componente de UI que encapsula toda la sección Cotizaciones.
    Recibe `sistema` (instancia de SistemaGestion) como única dependencia.
    """

    _ETAPAS_SEG = [
        ('Orden de Compra',     '📋', '#1a4b8c', '#dbeafe'),
        ('Entregada',           '🚚', '#166534', '#dcfce7'),
        ('Facturada',           '🧾', '#0e7490', '#cffafe'),
        ('Complemento de Pago', '💳', '#92400e', '#fef3c7'),
        ('Pagada',              '✅', '#6b21a8', '#f3e8ff'),
    ]

    UTILIDAD = {
        'Gobierno': 40,
        'Hotel': 35
    }

    def __init__(self, sistema):
        self.sistema = sistema
        self.conn    = sistema.conn
        self.cursor  = sistema.cursor
        self.root    = sistema.root
        self.C       = sistema.C

        # Widgets internos
        self.tree_cotizaciones      = None
        self.entry_buscar_cotizacion = None
        self._filtro_estado_cot     = None
        self._preview_cot_frame     = None
        self._badge_vinc            = None

    def crear_seccion(self):
        sec = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['cotizaciones'] = sec

        # Toolbar principal
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], relief='flat', bd=0)
        tb.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        self.sistema._toolbar_btn(tb, '➕ Nueva', self.nueva_cotizacion, color=self.C['accent'])
        self.sistema._toolbar_btn(tb, '✏️ Editar', self.editar_cotizacion)
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_menu(tb, '📄 PDF ▾', [
            ('Cotización PDF', self.generar_pdf_cotizacion_nueva),
            ('Nota de Remisión', self.generar_nota_remision),
        ])
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_menu(tb, '📋 Estado ▾', [
            ('Pendiente',               lambda: self.cambiar_estado_rapido('Pendiente')),
            ('Programada',              lambda: self.cambiar_estado_rapido('Programada')),
            ('Entregada (completa)',     self.marcar_entregada_completa),
            ('Entrega parcial',          self.marcar_entregada_parcial),
            None,
            ('Cancelar',                self.cancelar_cotizacion),
        ])
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '📋 Seguimiento', self.ver_seguimiento_cotizacion, color='#7c3aed')
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '📊 Estado de Cuenta', self.ver_estado_cuenta, color='#0e7490')
        self.sistema._toolbar_sep(tb)
        self._btn_vincular = self.sistema._toolbar_btn(tb, '🔗 Vincular', self._abrir_centro_vinculacion, color='#7c3aed')
        self._actualizar_badge_vinculacion()
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '📊 Exportar CSV', self.exportar_csv, color='#065f46')

        # Barra de filtros
        ff = tk.Frame(sec, bg=self.C['toolbar_bg'], pady=4)
        ff.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        tk.Label(ff, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=(8, 2))
        self.entry_buscar_cotizacion = tk.Entry(ff, font=('Arial', 9), width=25)
        self.entry_buscar_cotizacion.pack(side='left', padx=4)
        self.entry_buscar_cotizacion.bind('<Return>', lambda e: self.cargar_cotizaciones())

        tk.Label(ff, text='Estado:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=(10, 2))
        self._filtro_estado_cot = ttk.Combobox(ff, values=[
            'Todos', 'Pendiente', 'Programada', 'Parcialmente Entregada',
            'Entregada', 'Cancelada'
        ], state='readonly', width=22, font=('Arial', 9))
        self._filtro_estado_cot.set('Todos')
        self._filtro_estado_cot.pack(side='left', padx=4)
        self._filtro_estado_cot.bind('<<ComboboxSelected>>', lambda e: self.cargar_cotizaciones())
        self.sistema._toolbar_btn(ff, '🔄', self.cargar_cotizaciones)

        # ── Layout principal: tabla izquierda | preview derecho ──────────
        paned = tk.PanedWindow(sec, orient='horizontal',
                               bg=self.C['content_bg'],
                               sashwidth=5, sashrelief='flat',
                               bd=0)
        paned.pack(fill='both', expand=True, padx=0, pady=0)

        # ── Panel izquierdo: tabla ─────────────────────────────────────────
        ft = tk.Frame(paned, bg=self.C['content_bg'])
        paned.add(ft, minsize=520, stretch='always')

        # Cols: ID oculto | datos | _oc_doc y _fac_doc = columnas ícono clicables
        cols = ('ID', 'Folio', 'Fecha', 'Cliente', 'Total', 'Estado',
                'Entregado', 'O.C.', '_oc_doc', 'Ref. Factura', '_fac_doc', 'Pagado',
                'Observaciones')
        self.tree_cotizaciones = ttk.Treeview(
            ft, columns=cols, show='headings', selectmode='browse')

        wcfg = {
            'ID': 0, 'Folio': 115, 'Fecha': 88, 'Cliente': 185,
            'Total': 88, 'Estado': 138,
            'Entregado': 86, 'O.C.': 120, '_oc_doc': 36,
            'Ref. Factura': 120, '_fac_doc': 36, 'Pagado': 86,
            'Observaciones': 200,
        }
        for col in cols:
            if col == 'Observaciones':
                lbl = '📝 Observaciones'
            elif col.startswith('_'):
                lbl = ''
            else:
                lbl = col
            self.tree_cotizaciones.heading(col, text=lbl)
            self.tree_cotizaciones.column(col, width=wcfg[col], minwidth=wcfg[col],
                                          stretch=(col not in ('ID','_oc_doc','_fac_doc')))
        self.tree_cotizaciones.column('ID', stretch=False)
        self.tree_cotizaciones.column('_oc_doc',  stretch=False, anchor='center')
        self.tree_cotizaciones.column('_fac_doc', stretch=False, anchor='center')

        # Filas alternadas homogeneas — color solo en emoji de columna Estado
        self.tree_cotizaciones.tag_configure('fila_par',   background='#ffffff')
        self.tree_cotizaciones.tag_configure('fila_impar', background='#f4f6f9')

        sc_y = ttk.Scrollbar(ft, orient='vertical',   command=self.tree_cotizaciones.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal', command=self.tree_cotizaciones.xview)
        self.tree_cotizaciones.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        self.tree_cotizaciones.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        self.tree_cotizaciones.bind('<Double-1>', self._doble_clic_cotizacion)
        self.tree_cotizaciones.bind('<Button-1>',
                                   self._click_icono_documento_cotizacion)
        self.tree_cotizaciones.bind('<Motion>',
                                   self._hover_icono_cotizacion)
        self.tree_cotizaciones.bind('<<TreeviewSelect>>',
                                   lambda e: self._on_select_cotizacion())
        self.sistema._configurar_sorting_treeview(
            self.tree_cotizaciones,
            columnas_numericas=['Total', 'Entregado', 'Pagado'])

        # ── Panel derecho: preview de productos ────────────────────────────
        self._preview_frame = tk.Frame(paned, bg='#f8fafc',
                                       relief='flat', bd=0)
        paned.add(self._preview_frame, minsize=280, stretch='never')
        self._build_cotizacion_preview_panel(self._preview_frame)

        self.cargar_cotizaciones()

    # ── Preview panel de cotización ───────────────────────────────────────────
    def _build_cotizacion_preview_panel(self, parent):
        """Construye el panel de preview de productos de una cotización."""

        # Usamos grid en el parent para control total del layout
        parent.grid_rowconfigure(2, weight=1)   # fila del treeview se expande
        parent.grid_columnconfigure(0, weight=1)

        # ── Fila 0: Cabecera azul ──────────────────────────────────────────
        hdr = tk.Frame(parent, bg='#1e3a5f', pady=6)
        hdr.grid(row=0, column=0, columnspan=2, sticky='ew')
        tk.Label(hdr, text='📋  Detalle de Cotización',
                 font=('Arial', 9, 'bold'), bg='#1e3a5f', fg='white').pack(side='left', padx=8)

        # ── Fila 1: Info rápida ────────────────────────────────────────────
        info = tk.Frame(parent, bg='#f0f4f8', pady=5, padx=10)
        info.grid(row=1, column=0, columnspan=2, sticky='ew')

        self._pv_folio = tk.Label(info, text='—',
                                   font=('Arial', 10, 'bold'), bg='#f0f4f8',
                                   fg='#1e3a5f', anchor='w')
        self._pv_folio.pack(fill='x')
        self._pv_cliente = tk.Label(info, text='Selecciona una cotización',
                                     font=('Arial', 8), bg='#f0f4f8',
                                     fg='#6b7280', anchor='w')
        self._pv_cliente.pack(fill='x')

        sub_row = tk.Frame(info, bg='#f0f4f8')
        sub_row.pack(fill='x')
        self._pv_estado = tk.Label(sub_row, text='', font=('Arial', 8, 'bold'),
                                    bg='#f0f4f8', fg='#374151', anchor='w')
        self._pv_estado.pack(side='left')
        self._pv_fecha = tk.Label(sub_row, text='', font=('Arial', 8),
                                   bg='#f0f4f8', fg='#9ca3af', anchor='e')
        self._pv_fecha.pack(side='right')

        tk.Frame(parent, bg='#e2e8f0', height=1).grid(row=2, column=0,
                                                        columnspan=2, sticky='ew', pady=(0, 0))

        # ── Fila 2: Tabla de productos (se expande) ────────────────────────
        cols_pv = ('Descripción', 'Cant.', 'P.Unit.', 'Subtotal')
        self._pv_tree = ttk.Treeview(parent, columns=cols_pv, show='headings',
                                      selectmode='none')
        wcfg_pv = {'Descripción': 155, 'Cant.': 42, 'P.Unit.': 72, 'Subtotal': 78}
        for col in cols_pv:
            self._pv_tree.heading(col, text=col,
                                  anchor='e' if col != 'Descripción' else 'w')
            self._pv_tree.column(col, width=wcfg_pv[col], minwidth=wcfg_pv[col],
                                 stretch=(col == 'Descripción'),
                                 anchor='e' if col != 'Descripción' else 'w')
        self._pv_tree.tag_configure('par',   background='#f8fafc')
        self._pv_tree.tag_configure('impar', background='#ffffff')

        sc_pv = ttk.Scrollbar(parent, orient='vertical', command=self._pv_tree.yview)
        self._pv_tree.configure(yscrollcommand=sc_pv.set)

        self._pv_tree.grid(row=2, column=0, sticky='nsew', padx=(4, 0), pady=0)
        sc_pv.grid(row=2, column=1, sticky='ns', pady=0)

        # ── Fila 3: Separador ─────────────────────────────────────────────
        tk.Frame(parent, bg='#e2e8f0', height=1).grid(row=3, column=0,
                                                        columnspan=2, sticky='ew')

        # ── Fila 4: Totales ────────────────────────────────────────────────
        tot = tk.Frame(parent, bg='#f0f4f8', pady=7, padx=10)
        tot.grid(row=4, column=0, columnspan=2, sticky='ew')
        tot.grid_columnconfigure(1, weight=1)

        def _tot_row(label, var_name, bold=False, color='#374151', sep=False):
            if sep:
                tk.Frame(tot, bg='#e2e8f0', height=1).pack(fill='x', pady=3)
                return
            row = tk.Frame(tot, bg='#f0f4f8')
            row.pack(fill='x', pady=1)
            tk.Label(row, text=label, font=('Arial', 8, 'bold' if bold else 'normal'),
                     bg='#f0f4f8', fg='#9ca3af', anchor='w').pack(side='left')
            lbl = tk.Label(row, text='—', font=('Arial', 8, 'bold' if bold else 'normal'),
                           bg='#f0f4f8', fg=color, anchor='e')
            lbl.pack(side='right')
            setattr(self, var_name, lbl)

        _tot_row('Subtotal:',  '_pv_subtotal')
        _tot_row('IVA:',       '_pv_iva')
        _tot_row('Total:',     '_pv_total',    bold=True, color='#0f7b5e')
        _tot_row(None, None, sep=True)
        _tot_row('Entregado:', '_pv_entregado', color='#1d4ed8')
        _tot_row('Pagado:',    '_pv_pagado',    color='#166534')

    def _abrir_centro_vinculacion(self):
        """Abre el panel de vinculación inteligente."""
        if not hasattr(self, '_panel_vinculacion'):
            self._panel_vinculacion = PanelVinculacion(self.sistema)
        self._panel_vinculacion.abrir()

    def _actualizar_badge_vinculacion(self):
        """Actualiza el texto del botón con conteo de pendientes."""
        try:
            if not hasattr(self, '_btn_vincular'):
                return
            pendientes = detectar_pendientes(self.cursor)
            total = sum(len(v) for v in pendientes.values())
            if total > 0:
                self._btn_vincular.configure(
                    text=f'🔗 Vincular  [{total}]',
                    bg='#dc2626')
            else:
                self._btn_vincular.configure(
                    text='🔗 Vincular  ✅',
                    bg='#16a34a')
        except Exception:
            pass

    def exportar_csv(self):
        """Exporta la vista actual de cotizaciones a CSV respetando filtros activos."""
        import csv as _csv
        from tkinter import filedialog as _fd
        from datetime import datetime as _dt

        buscar = self.entry_buscar_cotizacion.get().strip()
        filtro = self._filtro_estado_cot.get() if self._filtro_estado_cot else 'Todos'

        params, where_parts = [], []
        if filtro and filtro != 'Todos':
            where_parts.append('c.estado = ?')
            params.append(filtro)
        if buscar:
            where_parts.append(
                '(c.folio LIKE ? OR cl.nombre_comercial LIKE ? OR c.orden_compra LIKE ?)')
            params += [f'%{buscar}%'] * 3
        where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

        self.cursor.execute(f"""
            SELECT c.folio, c.fecha, cl.nombre_comercial,
                   c.total, c.estado, c.orden_compra,
                   c.monto_entregado, c.monto_pagado,
                   c.numero_factura, c.observaciones
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            {where_sql}
            ORDER BY c.folio DESC
        """, params)
        filas = self.cursor.fetchall()

        if not filas:
            messagebox.showinfo('Sin datos', 'No hay cotizaciones con los filtros activos.')
            return

        ruta = _fd.asksaveasfilename(
            title='Exportar cotizaciones',
            defaultextension='.csv',
            initialfile=f'cotizaciones_{_dt.now().strftime("%Y-%m-%d")}.csv',
            filetypes=[('CSV', '*.csv')], parent=self.root)
        if not ruta:
            return

        with open(ruta, 'w', newline='', encoding='utf-8-sig') as f:
            w = _csv.writer(f)
            w.writerow(['Folio', 'Fecha', 'Cliente', 'Total', 'Estado',
                        'OC', 'Entregado', 'Pagado', 'No. Factura', 'Observaciones'])
            for row in filas:
                folio, fecha, cliente, total, estado, oc, entregado, pagado, fac, obs = row
                w.writerow([folio, (fecha or '')[:10], cliente,
                            f'{total:,.2f}' if total else '0.00',
                            estado, oc or '', 
                            f'{entregado:,.2f}' if entregado else '0.00',
                            f'{pagado:,.2f}' if pagado else '0.00',
                            fac or '', obs or ''])

        n = len(filas)
        messagebox.showinfo('✅ Exportación completa',
            f'{n} cotización{"es" if n!=1 else ""} exportada{"s" if n!=1 else ""}\n{ruta}',
            parent=self.root)

    def cargar_cotizaciones(self):
        """Carga la lista de cotizaciones en la tabla.
        Columnas: ID, Folio, Fecha, Cliente, Total, Estado,
                  Entregado, O.C., _oc_doc, Ref. Factura, _fac_doc, Pagado, Observaciones
        """
        for item in self.tree_cotizaciones.get_children():
            self.tree_cotizaciones.delete(item)

        buscar = self.entry_buscar_cotizacion.get().strip()
        filtro  = getattr(self, '_filtro_estado_cot', None)
        estado_filtro = filtro.get() if filtro else 'Todos'

        params = []
        where_parts = []

        if estado_filtro and estado_filtro != 'Todos':
            where_parts.append('c.estado = ?')
            params.append(estado_filtro)

        if buscar:
            where_parts.append(
                '(c.folio LIKE ? OR cl.nombre_comercial LIKE ? OR c.orden_compra LIKE ? OR c.observaciones LIKE ?)')
            params += [f'%{buscar}%', f'%{buscar}%', f'%{buscar}%', f'%{buscar}%']

        where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

        self.cursor.execute(f"""
            SELECT c.id, c.folio, c.fecha, cl.nombre_comercial,
                   c.total, c.estado, c.monto_entregado,
                   c.orden_compra, c.monto_facturado, c.monto_pagado,
                   c.observaciones
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            {where_sql}
            ORDER BY c.folio DESC
        """, params)

        rows = self.cursor.fetchall()

        # Pre-cargar documentos de OC por cotización
        if rows:
            ids = [r[0] for r in rows]
            placeholders = ','.join('?' * len(ids))

            self.cursor.execute(f"""
                SELECT cotizacion_id, tipo
                FROM documentos_cotizacion
                WHERE cotizacion_id IN ({placeholders})
                  AND tipo = 'Orden de Compra'
            """, ids)
            docs_oc_set = set()
            for cot_id, _ in self.cursor.fetchall():
                docs_oc_set.add(cot_id)

            # Referencia de OC desde seguimiento_etapas
            self.cursor.execute(f"""
                SELECT cotizacion_id, referencia
                FROM seguimiento_etapas
                WHERE cotizacion_id IN ({placeholders})
                  AND etapa = 'Orden de Compra'
                  AND referencia IS NOT NULL AND referencia != ''
            """, ids)
            seg_oc_refs = {row[0]: row[1] for row in self.cursor.fetchall()}

            # Facturas vinculadas desde factura_cotizaciones (junction table, múltiples por cotización)
            try:
                self.cursor.execute(f"""
                    SELECT fc.cotizacion_id, f.id, f.uuid, f.serie, f.folio_factura, f.fecha, f.total
                    FROM factura_cotizaciones fc
                    JOIN facturas f ON f.id = fc.factura_id
                    WHERE fc.cotizacion_id IN ({placeholders})
                    ORDER BY f.fecha DESC
                """, ids)
            except Exception:
                # Fallback a columna legacy si la tabla aún no existe
                self.cursor.execute(f"""
                    SELECT cotizacion_id, id, uuid, serie, folio_factura, fecha, total
                    FROM facturas
                    WHERE cotizacion_id IN ({placeholders})
                """, ids)
            facturas_por_cot = {}  # cot_id -> lista de facturas
            for cot_id, fid, uuid, serie, folio_f, fecha_f, total_f in self.cursor.fetchall():
                if cot_id not in facturas_por_cot:
                    facturas_por_cot[cot_id] = []
                facturas_por_cot[cot_id].append({
                    'id': fid, 'uuid': uuid, 'serie': serie,
                    'folio': folio_f, 'fecha': fecha_f, 'total': total_f,
                })
        else:
            docs_oc_set     = set()
            seg_oc_refs     = {}
            facturas_por_cot = {}

        # Estados activos (programada o más avanzado en entrega)
        ESTADOS_ACTIVOS = {'Programada', 'Parcialmente Entregada', 'Entregada',
                           'Facturada', 'Pagada'}

        for row in rows:
            cot_id, folio, fecha, cliente, total, estado, entregado, oc, facturado, pagado, obs = row
            tiene_oc  = cot_id in docs_oc_set
            fac_lista = facturas_por_cot.get(cot_id, [])
            tiene_fac = len(fac_lista) > 0
            oc_icon   = '📋' if tiene_oc  else '·'
            fac_icon  = '🧾' if tiene_fac else '·'

            # Referencia de OC desde seguimiento o campo directo
            ref_oc = seg_oc_refs.get(cot_id, '') or (oc or '')

            # Referencia de factura: serie-folio del XML (puede haber varias)
            if fac_lista:
                folios = []
                for fd in fac_lista:
                    if fd['serie'] and fd['folio']:
                        folios.append(f"{fd['serie']}-{fd['folio']}")
                    elif fd['folio']:
                        folios.append(fd['folio'])
                    else:
                        folios.append((fd['uuid'] or '')[:12] + '…')
                ref_fac = ', '.join(folios)
            else:
                ref_fac = ''

            # Lógica de visualización de O.C. y Factura en tabla
            if estado in ('Pendiente', 'Cancelada'):
                oc_txt  = 'N/A'
                fac_txt = 'N/A'
            else:
                oc_txt  = ref_oc  if ref_oc  else '✗'
                fac_txt = ref_fac if ref_fac else '✗'

            # Tags: estado de fondo + marcadores de documento
            tags = [estado]
            if tiene_oc:  tags.append('_has_oc')
            if tiene_fac: tags.append('_has_fac')

            obs_txt = (obs or '').strip()
            _emoji_estado = {
                'Pendiente':              '🟡',
                'Programada':             '🔵',
                'Parcialmente Entregada': '🟣',
                'Entregada':              '🟢',
                'Cancelada':              '⛔',
            }
            estado_display = f"{_emoji_estado.get(estado, '⚪')} {estado}"
            idx_fila = len(self.tree_cotizaciones.get_children())
            fila_tag = 'fila_par' if idx_fila % 2 == 0 else 'fila_impar'
            tags_finales = (fila_tag,) + tuple(t for t in tags if t not in (
                'Pendiente','Programada','Parcialmente Entregada',
                'Entregada','Facturada','Pagada','Cancelada'))
            # Pagado: N/A si el estado no lo aplica aún
            if estado in ('Pendiente', 'Cancelada'):
                pagado_txt = 'N/A'
            elif pagado and pagado > 0:
                pagado_txt = f'${pagado:,.2f}'
            else:
                pagado_txt = '—'

            values = (
                cot_id, folio, fecha, cliente,
                f'${total:,.2f}', estado_display,
                f'${entregado:,.2f}', oc_txt, oc_icon,
                fac_txt, fac_icon,
                pagado_txt, obs_txt,
            )
            self.tree_cotizaciones.insert('', 'end', values=values, tags=tags_finales)

        # Reaplicar ordenamiento si el usuario había seleccionado uno
        if hasattr(self.tree_cotizaciones, 'reaplicar_sort'):
            self.tree_cotizaciones.reaplicar_sort()
    
    def nueva_cotizacion(self):
        """Abre ventana para crear nueva cotización"""
        def _ir_catalogo_nueva():
            self.sistema._navegar('catalogos')
            try:
                nb = self.sistema.catalogos._notebook
                for i in range(nb.index('end')):
                    if 'roducto' in nb.tab(i, 'text'):
                        nb.select(i)
                        break
            except Exception:
                pass

        ventana_cot = VentanaCotizacion(self.root, self.conn, self.cursor, self.UTILIDAD,
                                        modo='nueva', on_ir_catalogo=_ir_catalogo_nueva)
        self.root.wait_window(ventana_cot.ventana)
        # Recargar cotizaciones y dashboard
        self.cargar_cotizaciones()
        self.sistema.actualizar_dashboard()
    
    def editar_cotizacion(self):
        """Edita la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        estado = item['values'][5]
        
        # No permitir editar si ya está entregada, facturada o pagada
        if estado in ['Entregada', 'Facturada', 'Pagada']:
            messagebox.showwarning(
                "Advertencia",
                f"No se puede editar una cotización en estado '{estado}'.\n\n" +
                "Solo se pueden editar cotizaciones en estado 'Pendiente' o 'Programada'."
            )
            return
        
        # Abrir ventana en modo edición
        def _ir_catalogo_editar():
            self.sistema._navegar('catalogos')
            try:
                nb = self.sistema.catalogos._notebook
                for i in range(nb.index('end')):
                    if 'roducto' in nb.tab(i, 'text'):
                        nb.select(i)
                        break
            except Exception:
                pass

        ventana_cot = VentanaCotizacion(
            self.root, self.conn, self.cursor, self.UTILIDAD,
            modo='editar', cotizacion_id=cotizacion_id,
            on_ir_catalogo=_ir_catalogo_editar
        )
        self.root.wait_window(ventana_cot.ventana)
        self.cargar_cotizaciones()
        self.sistema.actualizar_dashboard()
    
    def ver_cotizacion(self):
        """Ver detalle de cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        messagebox.showinfo("Info", "Vista de detalle se implementará próximamente")
    
    def generar_pdf_cotizacion(self):
        """Genera el PDF de la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        
        # Preguntar dónde guardar
        ruta_salida = filedialog.asksaveasfilename(
            title="Guardar cotización como...",
            defaultextension=".pdf",
            initialfile=f"Cotizacion_{folio}.pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        
        if ruta_salida:
            try:
                generador = GeneradorPDFCLY()
                arquivo = generador.generar_cotizacion(self.conn, cotizacion_id)
                if arquivo:
                    messagebox.showinfo("Éxito", f"PDF generado correctamente:\n{arquivo}")
                    
                    # Preguntar si desea abrir el PDF
                    respuesta = messagebox.askyesno("Abrir PDF", "¿Deseas abrir el PDF generado?")
                    if respuesta:
                        os.startfile(arquivo) if os.name == 'nt' else os.system(f'open "{arquivo}"')
                else:
                    messagebox.showerror("Error", "No se pudo generar el PDF")
            except Exception as e:
                messagebox.showerror("Error", f"Error al generar PDF:\n{str(e)}")
    
    def marcar_entregada(self):
        """Marca la cotización como entregada y descuenta del stock"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        # No permitir marcar como entregada si está cancelada
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede entregar una cotización cancelada")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar entrega",
            f"¿Marcar como entregada la cotización {folio}?\n\nSe descontará del inventario."
        )
        
        if respuesta:
            try:
                # Obtener detalle de cotización
                self.cursor.execute("""
                    SELECT producto_id, cantidad
                    FROM cotizacion_detalle
                    WHERE cotizacion_id = ?
                """, (cotizacion_id,))
                
                productos = self.cursor.fetchall()
                
                # Descontar stock y registrar movimiento
                for producto_id, cantidad in productos:
                    self.cursor.execute(
                        "SELECT stock_actual FROM productos WHERE id = ?",
                        (producto_id,))
                    _row = self.cursor.fetchone()
                    _stock_antes = _row[0] if _row else 0

                    self.cursor.execute("""
                        UPDATE productos
                        SET stock_actual = stock_actual - ?
                        WHERE id = ?
                    """, (cantidad, producto_id))

                    self.cursor.execute("""
                        INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad,
                         stock_antes, stock_despues, referencia)
                        VALUES (?, 'salida', 'Entrega de cotización', ?,
                                ?, ?, ?)
                    """, (producto_id, cantidad,
                          _stock_antes, _stock_antes - cantidad, folio))

                # Actualizar estado y fecha de entrega
                fecha_entrega = datetime.now().strftime('%Y-%m-%d')
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Entregada',
                        fecha_entrega = ?,
                        monto_entregado = total
                    WHERE id = ?
                """, (fecha_entrega, cotizacion_id))

                self.conn.commit()
                messagebox.showinfo("Éxito", "Cotización marcada como entregada y stock actualizado")
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo actualizar:\n{str(e)}")
    
    def cancelar_cotizacion(self):
        """Cancela una cotización sin afectar el stock"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        # No permitir cancelar si ya está entregada o pagada
        if estado_actual in ['Entregada', 'Pagada']:
            messagebox.showwarning(
                "Advertencia", 
                f"No se puede cancelar una cotización que ya está {estado_actual.lower()}"
            )
            return
        
        # Si ya está cancelada
        if estado_actual == 'Cancelada':
            messagebox.showinfo("Info", "Esta cotización ya está cancelada")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar cancelación",
            f"¿Cancelar la cotización {folio}?\n\n" +
            "La cotización se marcará como cancelada pero permanecerá en el registro.\n" +
            "No se afectará el inventario."
        )
        
        if respuesta:
            try:
                # Actualizar estado a Cancelada
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Cancelada'
                    WHERE id = ?
                """, (cotizacion_id,))
                
                self.conn.commit()
                messagebox.showinfo("Éxito", "Cotización cancelada correctamente")
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo cancelar:\n{str(e)}")
    
    def ver_detalle_cotizacion(self):
        """Muestra el detalle completo de la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        
        # Obtener datos completos de la cotización
        self.cursor.execute("""
            SELECT 
                c.folio, c.fecha, c.orden_compra, c.fecha_orden_compra,
                cl.nombre_comercial, cl.tipo, cl.contacto, cl.telefono, cl.email,
                c.subtotal, c.iva, c.total, c.notas, c.estado,
                c.fecha_entrega, c.monto_entregado, c.monto_facturado, c.monto_pagado
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cotizacion_id,))
        
        cot = self.cursor.fetchone()
        if not cot:
            return
        
        (folio, fecha, oc, fecha_oc, cliente, tipo_cliente, contacto, telefono, email,
         subtotal, iva, total, notas, estado, fecha_entrega, monto_entregado, monto_facturado, monto_pagado) = cot
        
        # Obtener productos
        self.cursor.execute("""
            SELECT 
                p.codigo, p.nombre, cd.cantidad, cd.precio_unitario,
                cd.subtotal, cd.iva, cd.total, cd.tiene_stock
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
        """, (cotizacion_id,))
        
        productos = self.cursor.fetchall()
        
        # Ventana de detalle
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle - {folio}")
        ventana.geometry("900x700")
        ventana.configure(bg='#ecf0f1')
        
        # Frame principal con scroll
        main_canvas = tk.Canvas(ventana, bg='#ecf0f1', highlightthickness=0)
        scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas, bg='#ecf0f1')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        # Contenido
        frame = tk.Frame(scrollable_frame, bg='#ecf0f1', padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        # === ENCABEZADO ===
        header_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        header_frame.pack(fill='x', pady=(0, 15))
        
        header_content = tk.Frame(header_frame, bg='white', padx=20, pady=15)
        header_content.pack(fill='x')
        
        tk.Label(
            header_content,
            text=folio,
            font=('Arial', 18, 'bold'),
            bg='white',
            fg='#2c3e50'
        ).pack(side='left')
        
        # Estado con color
        estado_colors = {
            'Pendiente': '#f39c12',
            'Programada': '#3498db',
            'Entregada': '#27ae60',
            'Facturada': '#9b59b6',
            'Pagada': '#16a085',
            'Cancelada': '#e74c3c'
        }
        
        estado_label = tk.Label(
            header_content,
            text=estado,
            font=('Arial', 12, 'bold'),
            bg=estado_colors.get(estado, '#95a5a6'),
            fg='white',
            padx=15,
            pady=5
        )
        estado_label.pack(side='right')
        
        # === INFORMACIÓN DEL CLIENTE ===
        cliente_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        cliente_frame.pack(fill='x', pady=(0, 15))
        
        cliente_content = tk.Frame(cliente_frame, bg='white', padx=20, pady=15)
        cliente_content.pack(fill='both')
        
        tk.Label(
            cliente_content,
            text="📋 INFORMACIÓN DEL CLIENTE",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        
        info_cliente = [
            ("Cliente:", cliente),
            ("Tipo:", tipo_cliente),
            ("Contacto:", contacto or "N/A"),
            ("Teléfono:", telefono or "N/A"),
            ("Email:", email or "N/A")
        ]
        
        for i, (label, value) in enumerate(info_cliente, start=1):
            tk.Label(
                cliente_content,
                text=label,
                font=('Arial', 10, 'bold'),
                bg='white',
                fg='#7f8c8d'
            ).grid(row=i, column=0, sticky='w', pady=3, padx=(0, 10))
            
            tk.Label(
                cliente_content,
                text=value,
                font=('Arial', 10),
                bg='white',
                fg='#2c3e50'
            ).grid(row=i, column=1, sticky='w', pady=3)
        
        # === FECHAS Y O.C. ===
        fechas_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        fechas_frame.pack(fill='x', pady=(0, 15))
        
        fechas_content = tk.Frame(fechas_frame, bg='white', padx=20, pady=15)
        fechas_content.pack(fill='both')
        
        tk.Label(
            fechas_content,
            text="📅 FECHAS Y ORDEN DE COMPRA",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))
        
        info_fechas = [
            ("Fecha Cotización:", fecha),
            ("Orden de Compra:", oc or "Sin O.C."),
            ("Fecha O.C.:", fecha_oc or "N/A"),
            ("Fecha Entrega:", fecha_entrega or "Pendiente")
        ]
        
        for i, (label, value) in enumerate(info_fechas):
            col = (i % 2) * 2
            row = i // 2 + 1
            
            tk.Label(
                fechas_content,
                text=label,
                font=('Arial', 9, 'bold'),
                bg='white',
                fg='#7f8c8d'
            ).grid(row=row, column=col, sticky='w', pady=3, padx=(0, 5))
            
            tk.Label(
                fechas_content,
                text=value,
                font=('Arial', 9),
                bg='white',
                fg='#2c3e50'
            ).grid(row=row, column=col+1, sticky='w', pady=3, padx=(0, 20))
        
        # Calcular días transcurridos si hay O.C.
        if fecha_oc and estado not in ['Pagada', 'Cancelada']:
            try:
                fecha_oc_dt = datetime.strptime(fecha_oc, '%Y-%m-%d')
                dias_transcurridos = (datetime.now() - fecha_oc_dt).days
                dias_limite = 30
                dias_restantes = dias_limite - dias_transcurridos
                
                # Alerta de días
                if dias_restantes < 0:
                    color_dias = '#e74c3c'
                    texto_dias = f"⚠️ VENCIDA hace {abs(dias_restantes)} días"
                elif dias_restantes <= 5:
                    color_dias = '#f39c12'
                    texto_dias = f"⚠️ Quedan {dias_restantes} días para vencer"
                else:
                    color_dias = '#27ae60'
                    texto_dias = f"✓ Quedan {dias_restantes} días"
                
                tk.Label(
                    fechas_content,
                    text="Límite de pago (30 días):",
                    font=('Arial', 9, 'bold'),
                    bg='white',
                    fg='#7f8c8d'
                ).grid(row=3, column=0, sticky='w', pady=(10, 3), padx=(0, 5))
                
                tk.Label(
                    fechas_content,
                    text=texto_dias,
                    font=('Arial', 9, 'bold'),
                    bg='white',
                    fg=color_dias
                ).grid(row=3, column=1, columnspan=3, sticky='w', pady=(10, 3))
                
            except:
                pass
        
        # === PRODUCTOS ===
        productos_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        productos_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        productos_content = tk.Frame(productos_frame, bg='white', padx=20, pady=15)
        productos_content.pack(fill='both', expand=True)
        
        tk.Label(
            productos_content,
            text="📦 PRODUCTOS",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).pack(anchor='w', pady=(0, 10))
        
        # Tabla de productos
        tree_frame = tk.Frame(productos_content, bg='white')
        tree_frame.pack(fill='both', expand=True)
        
        tree = ttk.Treeview(
            tree_frame,
            columns=('Código', 'Producto', 'Cant.', 'P.Unit.', 'Subtotal', 'IVA', 'Total', 'Stock'),
            show='headings',
            height=8
        )
        
        tree.heading('Código', text='Código')
        tree.heading('Producto', text='Producto')
        tree.heading('Cant.', text='Cant.')
        tree.heading('P.Unit.', text='P.Unit.')
        tree.heading('Subtotal', text='Subtotal')
        tree.heading('IVA', text='IVA')
        tree.heading('Total', text='Total')
        tree.heading('Stock', text='Stock')
        
        tree.column('Código', width=80)
        tree.column('Producto', width=250)
        tree.column('Cant.', width=60)
        tree.column('P.Unit.', width=90)
        tree.column('Subtotal', width=90)
        tree.column('IVA', width=70)
        tree.column('Total', width=90)
        tree.column('Stock', width=60)
        
        for prod in productos:
            stock_text = "✓" if prod[7] else "✗"
            tree.insert('', 'end', values=(
                prod[0], prod[1], f"{prod[2]:.2f}",
                f"${prod[3]:,.2f}", f"${prod[4]:,.2f}",
                f"${prod[5]:,.2f}", f"${prod[6]:,.2f}", stock_text
            ))
        
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # === TOTALES ===
        totales_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        totales_frame.pack(fill='x', pady=(0, 15))
        
        totales_content = tk.Frame(totales_frame, bg='white', padx=20, pady=15)
        totales_content.pack(fill='x')
        
        totales_info = [
            ("Subtotal:", subtotal, '#34495e'),
            ("IVA:", iva, '#7f8c8d'),
            ("TOTAL:", total, '#e74c3c')
        ]
        
        for label, monto, color in totales_info:
            row = tk.Frame(totales_content, bg='white')
            row.pack(fill='x', pady=2)
            
            size = 14 if label == "TOTAL:" else 11
            weight = 'bold' if label == "TOTAL:" else 'normal'
            
            tk.Label(
                row,
                text=label,
                font=('Arial', size, weight),
                bg='white',
                fg=color
            ).pack(side='right', padx=5)
            
            tk.Label(
                row,
                text=f"${monto:,.2f}",
                font=('Arial', size, weight),
                bg='white',
                fg=color
            ).pack(side='right')
        
        # === MONTOS ===
        montos_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        montos_frame.pack(fill='x', pady=(0, 15))
        
        montos_content = tk.Frame(montos_frame, bg='white', padx=20, pady=15)
        montos_content.pack(fill='x')
        
        tk.Label(
            montos_content,
            text="💰 SEGUIMIENTO DE MONTOS",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).pack(anchor='w', pady=(0, 10))
        
        montos_info = [
            ("Monto Entregado:", monto_entregado),
            ("Monto Facturado:", monto_facturado),
            ("Monto Pagado:", monto_pagado),
            ("Pendiente de Pago:", total - monto_pagado)
        ]
        
        for label, monto in montos_info:
            row = tk.Frame(montos_content, bg='white')
            row.pack(fill='x', pady=3)
            
            tk.Label(
                row,
                text=label,
                font=('Arial', 10),
                bg='white',
                fg='#7f8c8d'
            ).pack(side='left')
            
            color = '#27ae60' if monto == total and label == "Monto Pagado:" else '#2c3e50'
            tk.Label(
                row,
                text=f"${monto:,.2f}",
                font=('Arial', 10, 'bold'),
                bg='white',
                fg=color
            ).pack(side='right')
        
        # === NOTAS ===
        if notas:
            notas_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
            notas_frame.pack(fill='x')
            
            notas_content = tk.Frame(notas_frame, bg='white', padx=20, pady=15)
            notas_content.pack(fill='both')
            
            tk.Label(
                notas_content,
                text="📝 NOTAS",
                font=('Arial', 12, 'bold'),
                bg='white',
                fg='#34495e'
            ).pack(anchor='w', pady=(0, 5))
            
            tk.Label(
                notas_content,
                text=notas,
                font=('Arial', 10),
                bg='white',
                fg='#2c3e50',
                wraplength=800,
                justify='left'
            ).pack(anchor='w')
        
        # Botón cerrar
        btn_frame = tk.Frame(frame, bg='#ecf0f1')
        btn_frame.pack(pady=15)
        
        tk.Button(
            btn_frame,
            text="Cerrar",
            command=ventana.destroy,
            bg='#95a5a6',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=40,
            pady=12,
            relief='flat'
        ).pack()
        
        ventana.transient(self.root)
    
    def vincular_orden_compra(self):
        """Vincula una orden de compra a la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        oc_actual = item['values'][4]
        
        # Ventana para ingresar OC
        ventana = tk.Toplevel(self.root)
        ventana.title(f"🔗 Vincular Orden de Compra - {folio}")
        ventana.geometry("600x500")
        ventana.resizable(False, False)
        ventana.configure(bg='#ecf0f1')
        
        # Frame principal con padding
        frame_main = tk.Frame(ventana, bg='#ecf0f1', padx=20, pady=20)
        frame_main.pack(fill='both', expand=True)
        
        # Frame contenedor blanco
        frame = tk.Frame(frame_main, bg='white', relief='raised', bd=2)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Frame interno con padding
        frame_content = tk.Frame(frame, bg='white', padx=30, pady=25)
        frame_content.pack(fill='both', expand=True)
        
        # Título
        tk.Label(
            frame_content,
            text=f"Cotización: {folio}",
            font=('Arial', 14, 'bold'),
            bg='white',
            fg='#2c3e50'
        ).pack(pady=(0, 10))
        
        if oc_actual != 'Sin O.C.':
            tk.Label(
                frame_content,
                text=f"O.C. actual: {oc_actual}",
                font=('Arial', 10),
                fg='#7f8c8d',
                bg='white'
            ).pack(pady=(0, 15))
        
        # Separador
        ttk.Separator(frame_content, orient='horizontal').pack(fill='x', pady=15)
        
        # Campo de O.C.
        label_oc = tk.Label(
            frame_content,
            text="Número de Orden de Compra *",
            font=('Arial', 10, 'bold'),
            bg='white',
            fg='#34495e'
        )
        label_oc.pack(anchor='w', pady=(5, 5))
        
        entry_oc = tk.Entry(
            frame_content,
            font=('Arial', 11),
            relief='solid',
            bd=1,
            highlightthickness=1,
            highlightbackground='#bdc3c7',
            highlightcolor='#3498db'
        )
        entry_oc.pack(fill='x', ipady=8, pady=(0, 15))
        
        if oc_actual != 'Sin O.C.':
            entry_oc.insert(0, oc_actual)
        
        entry_oc.focus()
        
        # Campo de fecha
        label_fecha = tk.Label(
            frame_content,
            text="Fecha de O.C. (opcional)",
            font=('Arial', 10, 'bold'),
            bg='white',
            fg='#34495e'
        )
        label_fecha.pack(anchor='w', pady=(5, 5))
        
        entry_fecha = tk.Entry(
            frame_content,
            font=('Arial', 11),
            relief='solid',
            bd=1,
            highlightthickness=1,
            highlightbackground='#bdc3c7',
            highlightcolor='#3498db'
        )
        entry_fecha.pack(fill='x', ipady=8)
        entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Ayuda
        tk.Label(
            frame_content,
            text="📅 Formato: AAAA-MM-DD (ejemplo: 2026-02-12)",
            font=('Arial', 8, 'italic'),
            fg='#95a5a6',
            bg='white'
        ).pack(anchor='w', pady=(3, 0))
        
        # Frame de botones
        frame_btn = tk.Frame(frame_content, bg='white')
        frame_btn.pack(pady=(25, 10))
        
        def guardar():
            numero_oc = entry_oc.get().strip()
            fecha_oc = entry_fecha.get().strip()
            
            if not numero_oc:
                messagebox.showwarning("Advertencia", "Ingresa el número de O.C.", parent=ventana)
                entry_oc.focus()
                return
            
            try:
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET orden_compra = ?,
                        fecha_orden_compra = ?
                    WHERE id = ?
                """, (numero_oc, fecha_oc if fecha_oc else None, cotizacion_id))

                # Sincronizar referencia de OC con seguimiento_etapas
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas (cotizacion_id, etapa, completada, referencia, fecha_etapa)
                    VALUES (?, 'Orden de Compra', 1, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada = 1,
                        referencia = excluded.referencia,
                        fecha_etapa = excluded.fecha_etapa
                """, (cotizacion_id, numero_oc, fecha_oc if fecha_oc else None))
                
                self.conn.commit()
                messagebox.showinfo("Éxito", f"✓ O.C. {numero_oc} vinculada correctamente", parent=ventana)
                self.cargar_cotizaciones()
                ventana.destroy()
                
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo vincular:\n{str(e)}", parent=ventana)
        
        # Vincular Enter a guardar
        entry_oc.bind('<Return>', lambda e: guardar())
        entry_fecha.bind('<Return>', lambda e: guardar())
        
        tk.Button(
            frame_btn,
            text="💾 Guardar",
            command=guardar,
            bg='#27ae60',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=30,
            pady=12,
            relief='flat',
            activebackground='#229954'
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_btn,
            text="❌ Cancelar",
            command=ventana.destroy,
            bg='#95a5a6',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=30,
            pady=12,
            relief='flat',
            activebackground='#7f8c8d'
        ).pack(side='left', padx=5)
        
        ventana.transient(self.root)
        ventana.grab_set()
    
        ventana.transient(self.root)
        ventana.grab_set()
    
    def ver_detalle_cotizacion(self):
        """Muestra el detalle completo de la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        
        # Obtener datos completos
        self.cursor.execute("""
            SELECT c.folio, c.fecha, cl.nombre_comercial, cl.tipo, c.orden_compra, 
                   c.fecha_orden_compra, c.subtotal, c.iva, c.total, c.estado,
                   c.notas, c.fecha_entrega, c.monto_entregado, c.monto_facturado, 
                   c.monto_pagado, cl.contacto, cl.telefono, cl.email
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cotizacion_id,))
        
        cotizacion = self.cursor.fetchone()
        if not cotizacion:
            return
        
        (folio, fecha, cliente, tipo_cliente, orden_compra, fecha_oc, 
         subtotal, iva, total, estado, notas, fecha_entrega, 
         monto_entregado, monto_facturado, monto_pagado,
         contacto, telefono, email) = cotizacion
        
        # Obtener productos
        self.cursor.execute("""
            SELECT p.codigo, p.nombre, cd.cantidad, cd.precio_unitario, 
                   cd.subtotal, cd.iva, cd.total, cd.tiene_stock
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
        """, (cotizacion_id,))
        
        productos = self.cursor.fetchall()
        
        # Ventana
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle - {folio}")
        ventana.geometry("900x700")
        ventana.configure(bg='#ecf0f1')
        
        # Scroll
        canvas = tk.Canvas(ventana, bg='#ecf0f1')
        scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ecf0f1')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        frame_content = tk.Frame(scrollable_frame, bg='#ecf0f1', padx=20, pady=20)
        frame_content.pack(fill='both', expand=True)
        
        # Info General
        frame_general = tk.LabelFrame(frame_content, text="Información General", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
        frame_general.pack(fill='x', pady=(0, 15))
        
        info_general = [
            ("Folio:", folio),
            ("Fecha:", fecha),
            ("Estado:", estado),
            ("O.C.:", orden_compra or 'Sin O.C.'),
            ("Fecha O.C.:", fecha_oc or 'N/A')
        ]
        
        for label, valor in info_general:
            frame_item = tk.Frame(frame_general, bg='white')
            frame_item.pack(fill='x', pady=3)
            tk.Label(frame_item, text=label, font=('Arial', 9, 'bold'), bg='white', width=12, anchor='w').pack(side='left')
            tk.Label(frame_item, text=valor, font=('Arial', 9), bg='white').pack(side='left')
        
        # Cliente
        frame_cliente = tk.LabelFrame(frame_content, text="Cliente", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
        frame_cliente.pack(fill='x', pady=(0, 15))
        
        info_cliente = [
            ("Nombre:", cliente),
            ("Tipo:", tipo_cliente),
            ("Contacto:", contacto or 'N/A'),
            ("Teléfono:", telefono or 'N/A')
        ]
        
        for label, valor in info_cliente:
            frame_item = tk.Frame(frame_cliente, bg='white')
            frame_item.pack(fill='x', pady=3)
            tk.Label(frame_item, text=label, font=('Arial', 9, 'bold'), bg='white', width=12, anchor='w').pack(side='left')
            tk.Label(frame_item, text=valor, font=('Arial', 9), bg='white').pack(side='left')
        
        # Productos
        frame_productos = tk.LabelFrame(frame_content, text="Productos", font=('Arial', 11, 'bold'), bg='white', padx=10, pady=10)
        frame_productos.pack(fill='both', expand=True, pady=(0, 15))
        
        tree_productos = ttk.Treeview(
            frame_productos,
            columns=('Código', 'Producto', 'Cantidad', 'Precio', 'Total'),
            show='headings',
            height=8
        )
        
        for col in ('Código', 'Producto', 'Cantidad', 'Precio', 'Total'):
            tree_productos.heading(col, text=col)
        
        tree_productos.column('Código', width=80)
        tree_productos.column('Producto', width=300)
        tree_productos.column('Cantidad', width=100)
        tree_productos.column('Precio', width=120)
        tree_productos.column('Total', width=120)
        
        for prod in productos:
            tree_productos.insert('', 'end', values=(
                prod[0], prod[1], f"{prod[2]:.2f}",
                f"${prod[3]:,.2f}", f"${prod[6]:,.2f}"
            ))
        
        tree_productos.pack(fill='both', expand=True)
        
        # Totales
        frame_totales = tk.Frame(frame_content, bg='white', relief='raised', bd=2, padx=20, pady=15)
        frame_totales.pack(fill='x', pady=(0, 15))
        
        tk.Label(frame_totales, text=f"Subtotal: ${subtotal:,.2f}", font=('Arial', 10), bg='white').pack(anchor='e')
        tk.Label(frame_totales, text=f"IVA: ${iva:,.2f}", font=('Arial', 10), bg='white').pack(anchor='e')
        tk.Label(frame_totales, text=f"TOTAL: ${total:,.2f}", font=('Arial', 14, 'bold'), bg='white', fg='#e74c3c').pack(anchor='e')
        
        # Seguimiento
        dias_oc = "N/A"
        if fecha_oc:
            try:
                fecha_oc_dt = datetime.strptime(fecha_oc, '%Y-%m-%d')
                dias_transcurridos = (datetime.now() - fecha_oc_dt).days
                dias_oc = f"{dias_transcurridos} días"
                if dias_transcurridos > 30:
                    dias_oc += " ⚠️"
            except:
                pass
        
        frame_seg = tk.LabelFrame(frame_content, text="Seguimiento", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
        frame_seg.pack(fill='x', pady=(0, 15))
        
        seguimiento_info = [
            ("Días desde O.C.:", dias_oc),
            ("Monto Entregado:", f"${monto_entregado:,.2f}"),
            ("Monto Pagado:", f"${monto_pagado:,.2f}")
        ]
        
        for label, valor in seguimiento_info:
            frame_item = tk.Frame(frame_seg, bg='white')
            frame_item.pack(fill='x', pady=3)
            tk.Label(frame_item, text=label, font=('Arial', 9, 'bold'), bg='white', width=18, anchor='w').pack(side='left')
            tk.Label(frame_item, text=valor, font=('Arial', 9), bg='white').pack(side='left')
        
        if notas:
            frame_notas = tk.LabelFrame(frame_content, text="Notas", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
            frame_notas.pack(fill='x', pady=(0, 15))
            tk.Label(frame_notas, text=notas, font=('Arial', 9), bg='white', justify='left', wraplength=800).pack()
        
        tk.Button(frame_content, text="Cerrar", command=ventana.destroy, bg='#95a5a6', fg='white', font=('Arial', 11, 'bold'), padx=30, pady=10).pack(pady=10)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        ventana.transient(self.root)
        ventana.grab_set()
    
    # (removed - rebuilt in new ERP UI)
    def generar_pdf_cotizacion_nueva(self):
        """Genera PDF de cotización con nuevo formato CLY (con opción de impresión parcial)"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return

        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]

        # Mostrar diálogo de impresión (completa o parcial)
        dlg = DialogoImpresion(self.root, self.conn, cotizacion_id, tipo='cotizacion')
        dlg.ventana.wait_window()

        if dlg.resultado is None:
            return  # Cancelado

        try:
            generador = GeneradorPDFCLY()
            if dlg.resultado == 'completa':
                archivo = generador.generar_cotizacion(self.conn, cotizacion_id)
            else:
                archivo = generador.generar_cotizacion(
                    self.conn, cotizacion_id,
                    productos_override=dlg.productos_para_pdf,
                    totales_override=dlg.totales_para_pdf
                )

            if archivo:
                messagebox.showinfo("Éxito", f"PDF generado: {archivo}")
                os.startfile(archivo) if os.name == 'nt' else os.system(f'open "{archivo}"')
            else:
                messagebox.showerror("Error", "No se pudo generar el PDF")

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar PDF:\n{str(e)}")
    
    def generar_nota_remision(self):
        """Genera nota de remisión para la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        estado = item['values'][5]
        
        # Verificar que esté programada o entregada
        if estado not in ['Programada', 'Entregada', 'Parcialmente Entregada']:
            respuesta = messagebox.askyesno(
                "Advertencia",
                f"La cotización está en estado '{estado}'.\n\n" +
                "Se recomienda generar nota de remisión solo para cotizaciones Programadas.\n\n" +
                "¿Deseas continuar de todos modos?"
            )
            if not respuesta:
                return
        
        # Mostrar diálogo de impresión (completa o parcial)
        dlg = DialogoImpresion(self.root, self.conn, cotizacion_id, tipo='remision')
        dlg.ventana.wait_window()

        if dlg.resultado is None:
            return  # Cancelado

        try:
            generador = GeneradorPDFCLY()
            if dlg.resultado == 'completa':
                archivo = generador.generar_nota_remision(self.conn, cotizacion_id)
            else:
                archivo = generador.generar_nota_remision(
                    self.conn, cotizacion_id,
                    productos_override=dlg.productos_para_pdf,
                    totales_override=dlg.totales_para_pdf
                )

            if archivo:
                messagebox.showinfo("Éxito", f"Nota de remisión generada: {archivo}")
                os.startfile(archivo) if os.name == 'nt' else os.system(f'open "{archivo}"')
            else:
                messagebox.showerror("Error", "No se pudo generar la nota")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al generar nota:\n{str(e)}")
    
    def cambiar_estado_rapido(self, nuevo_estado):
        """Cambia el estado de la cotización seleccionada.
        Solo permite: Pendiente, Programada, Cancelada.
        (Entrega parcial/completa tienen sus propias funciones.)
        """
        ESTADOS_PERMITIDOS = {'Pendiente', 'Programada', 'Cancelada',
                              'Parcialmente Entregada', 'Entregada'}
        if nuevo_estado not in ESTADOS_PERMITIDOS:
            messagebox.showwarning("Estado no válido",
                f"'{nuevo_estado}' ya no es un estado de cotización válido.\n\n"
                "Los estados disponibles son: Pendiente, Programada, Entregada Parcialmente, "
                "Entregada por completo y Cancelada.\n\n"
                "Para registrar OC, Factura o Pago usa la sección de Seguimiento.")
            return

        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == nuevo_estado:
            messagebox.showinfo("Info", f"La cotización ya está en estado '{nuevo_estado}'")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar cambio",
            f"¿Cambiar estado de {folio}?\n\n" +
            f"De: {estado_actual}\n" +
            f"A: {nuevo_estado}"
        )
        
        if respuesta:
            try:
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = ?
                    WHERE id = ?
                """, (nuevo_estado, cotizacion_id))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, nuevo_estado)
                
                self.conn.commit()
                
                # Si cambió a Programada, preguntar si quiere generar nota de remisión
                if nuevo_estado == 'Programada':
                    generar_nota = messagebox.askyesno(
                        "Generar Nota de Remisión",
                        f"Cotización marcada como {nuevo_estado}.\n\n" +
                        "¿Deseas generar la Nota de Remisión ahora?"
                    )
                    
                    if generar_nota:
                        generador = GeneradorPDFCLY()
                        archivo = generador.generar_nota_remision(self.conn, cotizacion_id)
                        if archivo:
                            messagebox.showinfo("Éxito", f"Nota generada: {archivo}")
                            import os
                            os.startfile(archivo) if os.name == 'nt' else os.system(f'open "{archivo}"')
                else:
                    messagebox.showinfo("Éxito", f"Estado cambiado a {nuevo_estado}")
                
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo cambiar el estado:\n{str(e)}")
    
    def marcar_facturada(self):
        """Registra la factura de una cotización"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede facturar una cotización cancelada")
            return
        
        # Ventana de registro de factura
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Registrar Factura - {folio}")
        ventana.geometry("400x300")
        ventana.resizable(False, False)
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text=f"Cotización: {folio}", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        
        tk.Label(frame, text="Número de Factura:", font=('Arial', 10)).grid(
            row=1, column=0, sticky='w', pady=5)
        entry_num_factura = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_num_factura.grid(row=1, column=1, pady=5)
        entry_num_factura.focus()
        
        tk.Label(frame, text="Monto Facturado:", font=('Arial', 10)).grid(
            row=2, column=0, sticky='w', pady=5)
        
        # Obtener total de la cotización para pre-rellenar
        self.cursor.execute("SELECT total FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        total_cot = self.cursor.fetchone()[0]
        
        entry_monto = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_monto.grid(row=2, column=1, pady=5)
        entry_monto.insert(0, f"{total_cot:.2f}")
        
        tk.Label(frame, text="Fecha de Factura:", font=('Arial', 10)).grid(
            row=3, column=0, sticky='w', pady=5)
        entry_fecha = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_fecha.grid(row=3, column=1, pady=5)
        entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        tk.Label(frame, text="Notas:", font=('Arial', 10)).grid(
            row=4, column=0, sticky='nw', pady=5)
        text_notas = tk.Text(frame, width=18, height=3, font=('Arial', 10))
        text_notas.grid(row=4, column=1, pady=5)

        # Enter guarda (excepto dentro del Text de notas)
        entry_num_factura.bind('<Return>', lambda e: guardar_factura())
        entry_monto.bind('<Return>', lambda e: guardar_factura())
        entry_fecha.bind('<Return>', lambda e: guardar_factura())

        def guardar_factura():
            try:
                monto = float(entry_monto.get())
                fecha = entry_fecha.get().strip()
                num_factura = entry_num_factura.get().strip()
                notas = text_notas.get('1.0', 'end-1c').strip()
                
                if not fecha:
                    messagebox.showwarning("Advertencia", "Ingresa la fecha de factura", parent=ventana)
                    return
                
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Facturada',
                        monto_facturado = ?,
                        fecha_factura = ?,
                        numero_factura = CASE WHEN ? != '' THEN ? ELSE numero_factura END
                    WHERE id = ?
                """, (monto, fecha, num_factura, num_factura, cotizacion_id))

                # Sincronizar referencia de factura con seguimiento_etapas
                ref_fac = num_factura if num_factura else ''
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas (cotizacion_id, etapa, completada, referencia, fecha_etapa)
                    VALUES (?, 'Facturada', 1, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada = 1,
                        referencia = CASE WHEN excluded.referencia != '' THEN excluded.referencia ELSE referencia END,
                        fecha_etapa = excluded.fecha_etapa
                """, (cotizacion_id, ref_fac, fecha))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, 'Facturada', fecha)

                self.conn.commit()
                messagebox.showinfo("Éxito", f"Cotización {folio} marcada como Facturada", parent=ventana)
                ventana.destroy()
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except ValueError:
                messagebox.showwarning("Advertencia", "El monto debe ser un número válido", parent=ventana)
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e), parent=ventana)
        
        frame_btn = tk.Frame(frame)
        frame_btn.grid(row=5, column=0, columnspan=2, pady=15)
        
        tk.Button(frame_btn, text="💾 Guardar", command=guardar_factura,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(frame_btn, text="❌ Cancelar", command=ventana.destroy,
                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        
        ventana.transient(self.root)
        ventana.grab_set()
    
    def marcar_pagada(self):
        """Registra el pago de una cotización"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede registrar pago de una cotización cancelada")
            return
        
        # Ventana de registro de pago
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Registrar Pago - {folio}")
        ventana.geometry("400x280")
        ventana.resizable(False, False)
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text=f"Cotización: {folio}", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        
        # Obtener total y monto_pagado actual
        self.cursor.execute("SELECT total, monto_pagado FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        total_cot, pagado_actual = self.cursor.fetchone()
        pendiente = total_cot - (pagado_actual or 0)
        
        tk.Label(frame, text=f"Total: ${total_cot:,.2f}  |  Ya pagado: ${pagado_actual or 0:,.2f}  |  Pendiente: ${pendiente:,.2f}",
                 font=('Arial', 9), fg='#7f8c8d').grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))
        
        tk.Label(frame, text="Monto Pagado Ahora:", font=('Arial', 10)).grid(
            row=2, column=0, sticky='w', pady=5)
        entry_monto = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_monto.grid(row=2, column=1, pady=5)
        entry_monto.insert(0, f"{pendiente:.2f}")
        entry_monto.focus()
        
        tk.Label(frame, text="Fecha de Pago:", font=('Arial', 10)).grid(
            row=3, column=0, sticky='w', pady=5)
        entry_fecha = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_fecha.grid(row=3, column=1, pady=5)
        entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        tk.Label(frame, text="Referencia / Notas:", font=('Arial', 10)).grid(
            row=4, column=0, sticky='w', pady=5)
        entry_notas = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_notas.grid(row=4, column=1, pady=5)

        # Enter guarda desde cualquier campo
        for _e in (entry_monto, entry_fecha, entry_notas):
            _e.bind('<Return>', lambda e: guardar_pago())

        def guardar_pago():
            try:
                monto_nuevo = float(entry_monto.get())
                fecha = entry_fecha.get().strip()

                if not fecha:
                    messagebox.showwarning("Advertencia", "Ingresa la fecha de pago", parent=ventana)
                    return

                nuevo_total_pagado = (pagado_actual or 0) + monto_nuevo

                # Obtener estado actual limpio (sin emoji) directo de la BD
                self.cursor.execute("SELECT estado FROM cotizaciones WHERE id=?", (cotizacion_id,))
                estado_db = self.cursor.fetchone()[0]

                # Si el pago cubre el total → Pagada; si no, mantener estado actual
                nuevo_estado = 'Pagada' if nuevo_total_pagado >= total_cot else estado_db

                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET monto_pagado = ?,
                        fecha_pago   = ?,
                        estado       = ?
                    WHERE id = ?
                """, (nuevo_total_pagado, fecha, nuevo_estado, cotizacion_id))

                # Siempre sincronizar etapa Pagada en seguimiento con monto parcial o total
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas
                        (cotizacion_id, etapa, completada, fecha_etapa, notas)
                    VALUES (?, 'Pagada', ?, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada  = excluded.completada,
                        fecha_etapa = COALESCE(excluded.fecha_etapa, fecha_etapa),
                        notas       = COALESCE(excluded.notas, notas)
                """, (cotizacion_id,
                      1 if nuevo_estado == 'Pagada' else 0,
                      fecha,
                      f'Pago parcial ${monto_nuevo:,.2f}' if nuevo_estado != 'Pagada' else None))

                self.conn.commit()

                if nuevo_estado == 'Pagada':
                    msg = f"Cotización {folio} marcada como PAGADA completamente."
                else:
                    msg = (f"Pago de ${monto_nuevo:,.2f} registrado.\n"
                           f"Total pagado: ${nuevo_total_pagado:,.2f} de ${total_cot:,.2f}\n"
                           f"Pendiente: ${total_cot - nuevo_total_pagado:,.2f}")

                messagebox.showinfo("Éxito", msg, parent=ventana)
                ventana.destroy()
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()

            except ValueError:
                messagebox.showwarning("Advertencia", "El monto debe ser un número válido", parent=ventana)
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e), parent=ventana)
        
        frame_btn = tk.Frame(frame)
        frame_btn.grid(row=5, column=0, columnspan=2, pady=15)
        
        tk.Button(frame_btn, text="💾 Registrar Pago", command=guardar_pago,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(frame_btn, text="❌ Cancelar", command=ventana.destroy,
                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        
        ventana.transient(self.root)
        ventana.grab_set()
    
    def marcar_entregada_completa(self):
        """Marca la cotización como entregada completamente"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede entregar una cotización cancelada")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar entrega",
            f"¿Marcar como entregada completamente?\n\n" +
            f"Cotización: {folio}\n\n" +
            "Se descontará del inventario."
        )
        
        if respuesta:
            try:
                # Obtener productos
                self.cursor.execute("""
                    SELECT producto_id, cantidad
                    FROM cotizacion_detalle
                    WHERE cotizacion_id = ?
                """, (cotizacion_id,))
                
                productos = self.cursor.fetchall()
                
                # Descontar stock y registrar movimiento
                for producto_id, cantidad in productos:
                    self.cursor.execute(
                        "SELECT stock_actual FROM productos WHERE id = ?",
                        (producto_id,))
                    _row = self.cursor.fetchone()
                    _stock_antes = _row[0] if _row else 0

                    self.cursor.execute("""
                        UPDATE productos
                        SET stock_actual = stock_actual - ?
                        WHERE id = ?
                    """, (cantidad, producto_id))

                    self.cursor.execute("""
                        INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad,
                         stock_antes, stock_despues, referencia)
                        VALUES (?, 'salida', 'Entrega de cotización', ?,
                                ?, ?, ?)
                    """, (producto_id, cantidad,
                          _stock_antes, _stock_antes - cantidad, folio))

                # Actualizar cotización
                fecha_entrega = datetime.now().strftime('%Y-%m-%d')
                self.cursor.execute("""
                    SELECT total FROM cotizaciones WHERE id = ?
                """, (cotizacion_id,))
                total = self.cursor.fetchone()[0]

                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Entregada',
                        fecha_entrega = ?,
                        monto_entregado = ?,
                        entrega_parcial = 0
                    WHERE id = ?
                """, (fecha_entrega, total, cotizacion_id))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, 'Entregada', fecha_entrega)

                self.conn.commit()
                messagebox.showinfo("Éxito", "Cotización marcada como entregada\nStock actualizado")
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo marcar como entregada:\n{str(e)}")
    
    def marcar_entregada_parcial(self):
        """Abre ventana para marcar entrega parcial de productos"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        estado = item['values'][5]
        
        # Verificar que esté en estado Programada
        if estado != 'Programada':
            messagebox.showwarning(
                "Estado no válido",
                "Solo se pueden registrar entregas parciales en cotizaciones con estado 'Programada'.\n\n" +
                f"Estado actual: {estado}"
            )
            return
        
        # Abrir ventana de entregas parciales y ESPERAR a que se cierre
        ventana_parcial = VentanaEntregaParcial(self.root, self.conn, self.cursor, cotizacion_id)
        self.root.wait_window(ventana_parcial.ventana)

        # Actualizar después de cerrar la ventana
        self.cargar_cotizaciones()
        self.sistema.actualizar_dashboard()
        # Refrescar stock si el módulo está cargado
        if hasattr(self, '_stock'):
            try:
                self.sistema._stock.cargar_vista_stock()
                self.sistema._stock.cargar_historial()
            except Exception:
                pass
    

    def _doble_clic_cotizacion(self, event):
        """Doble clic en el treeview:
        - Columna Observaciones → popup de edición rápida
        - Cualquier otra columna → abrir detalle de cotización
        """
        region = self.tree_cotizaciones.identify('region', event.x, event.y)
        if region != 'cell':
            return
        col_id  = self.tree_cotizaciones.identify_column(event.x)
        item_id = self.tree_cotizaciones.identify_row(event.y)
        if not item_id:
            return
        cols = self.tree_cotizaciones['columns']
        try:
            col_name = cols[int(col_id[1:]) - 1]
        except (IndexError, ValueError):
            col_name = ''

        if col_name == 'Observaciones':
            self._editar_observacion_rapida(item_id)
        else:
            self.ver_detalle_cotizacion()

    def _editar_observacion_rapida(self, item_id):
        """Popup pequeño para editar observaciones de una cotización."""
        vals   = self.tree_cotizaciones.item(item_id)['values']
        cot_id = vals[0]
        folio  = vals[1]
        obs_actual = str(vals[12]) if len(vals) > 12 else ''

        # Obtener bbox de la celda para posicionar el popup cerca
        bbox = self.tree_cotizaciones.bbox(item_id, column='Observaciones')

        popup = tk.Toplevel(self.root)
        popup.title(f"Observación — {folio}")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()
        popup.configure(bg='#f8fafc')

        # Posicionar cerca de la celda si es posible
        if bbox:
            x = self.tree_cotizaciones.winfo_rootx() + bbox[0]
            y = self.tree_cotizaciones.winfo_rooty() + bbox[1]
            popup.geometry(f"340x160+{x}+{y}")
        else:
            popup.geometry("340x160")

        tk.Label(popup, text=f"📝  Observación — {folio}",
                 font=('Arial', 9, 'bold'), bg='#f8fafc', fg='#1e293b').pack(pady=(10, 4))

        txt = tk.Text(popup, font=('Arial', 9), width=38, height=4,
                      wrap='word', relief='solid', bd=1, padx=4, pady=4)
        txt.insert('1.0', obs_actual if obs_actual != 'None' else '')
        txt.pack(padx=10)
        txt.focus_set()
        txt.mark_set('insert', 'end')

        def guardar(event=None):
            nueva_obs = txt.get('1.0', 'end').strip()
            try:
                self.cursor.execute(
                    "UPDATE cotizaciones SET observaciones=? WHERE id=?",
                    (nueva_obs or None, cot_id))
                self.conn.commit()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=popup)
                return
            popup.destroy()
            self.cargar_cotizaciones()

        btns = tk.Frame(popup, bg='#f8fafc')
        btns.pack(pady=6)
        tk.Button(btns, text='💾 Guardar', command=guardar,
                  bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=10, pady=4, relief='raised').pack(side='left', padx=6)
        tk.Button(btns, text='Cancelar', command=popup.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=8, pady=4, relief='raised').pack(side='left')

        # Ctrl+Enter también guarda
        txt.bind('<Control-Return>', guardar)

    def _hover_icono_cotizacion(self, event):
        """Cambia cursor según la columna: mano para íconos de doc, lápiz para Observaciones."""
        col_id = self.tree_cotizaciones.identify_column(event.x)
        try:
            col_idx  = int(col_id[1:]) - 1
            col_name = self.tree_cotizaciones['columns'][col_idx]
        except (IndexError, ValueError):
            col_name = ''
        if col_name == 'Observaciones':
            self.tree_cotizaciones.configure(cursor='xterm')
            return
        if col_name in ('_oc_doc', '_fac_doc'):
            item_id = self.tree_cotizaciones.identify_row(event.y)
            if item_id:
                vals = self.tree_cotizaciones.item(item_id)['values']
                icon_val = str(vals[col_idx]) if len(vals) > col_idx else ''
                if icon_val in ('📋', '🧾'):
                    self.tree_cotizaciones.configure(cursor='hand2')
                    return
        self.tree_cotizaciones.configure(cursor='')

    def _click_icono_documento_cotizacion(self, event):
        """Si se hace clic en la columna 📄 de OC o Factura, abre el doc correspondiente."""
        import subprocess, platform
        region = self.tree_cotizaciones.identify('region', event.x, event.y)
        if region != 'cell':
            return
        col_id  = self.tree_cotizaciones.identify_column(event.x)   # '#1', '#2', ...
        item_id = self.tree_cotizaciones.identify_row(event.y)
        if not item_id:
            return
        # Mapear índice de columna → nombre
        cols = self.tree_cotizaciones['columns']
        try:
            col_idx  = int(col_id[1:]) - 1   # '#9' → 8
            col_name = cols[col_idx]
        except (IndexError, ValueError):
            return
        if col_name not in ('_oc_doc', '_fac_doc'):
            return
        # Obtener valor del ícono
        vals     = self.tree_cotizaciones.item(item_id)['values']
        icon_val = str(vals[col_idx])
        if icon_val not in ('📋', '🧾'):
            return                    # sin documento, no hacer nada

        cot_id = vals[0]

        if col_name == '_fac_doc':
            # Factura: abrir detalle del XML vinculado
            self._mostrar_detalle_factura_xml(cot_id)
            return

        # OC: abrir archivo físico desde documentos_cotizacion
        self.cursor.execute("""
            SELECT ruta_archivo FROM documentos_cotizacion
            WHERE cotizacion_id = ? AND tipo = 'Orden de Compra'
            ORDER BY fecha_registro DESC LIMIT 1
        """, (cot_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        ruta = row[0]
        if not os.path.exists(ruta):
            messagebox.showerror("Archivo no encontrado",
                f"El archivo ya no está en:\n{ruta}")
            return
        try:
            if platform.system() == 'Windows':
                os.startfile(ruta)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', ruta])
            else:
                subprocess.Popen(['xdg-open', ruta])
        except Exception as e:
            messagebox.showerror("Error al abrir", str(e))

    def _mostrar_detalle_factura_xml(self, cot_id, parent_win=None):
        """Muestra el detalle de la factura XML vinculada a una cotización."""
        self.cursor.execute("""
            SELECT id FROM facturas WHERE cotizacion_id = ?
            ORDER BY fecha_registro DESC LIMIT 1
        """, (cot_id,))
        row = self.cursor.fetchone()
        if not row:
            messagebox.showinfo("Sin factura XML",
                "Esta cotización no tiene una factura XML vinculada.\n\n"
                "Importa el CFDI en la sección 🧾 Facturación y vincúlalo.",
                parent=parent_win or self.root)
            return
        if hasattr(self, '_facturacion'):
            self.sistema._facturacion._mostrar_detalle_por_id(row[0])

    # Definición de etapas de seguimiento
    _ETAPAS_SEG = [
        ('Orden de Compra',     '📋', '#1a4b8c', '#dbeafe'),
        ('Entregada',           '🚚', '#166534', '#dcfce7'),
        ('Facturada',           '🧾', '#0e7490', '#cffafe'),
        ('Complemento de Pago', '💳', '#92400e', '#fef3c7'),
        ('Pagada',              '✅', '#6b21a8', '#f3e8ff'),
    ]

    def ver_estado_cuenta(self):
        """Abre la ventana de Estado de Cuenta de Pedidos."""
        VentanaEstadoCuenta(self.root, self.conn, self.cursor)

    def ver_seguimiento_cotizacion(self):
        """Abre ventana de seguimiento por etapas de la cotización seleccionada."""
        import subprocess, platform

        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return

        item   = self.tree_cotizaciones.item(seleccion[0])
        cot_id = item['values'][0]
        folio  = item['values'][1]

        # Obtener info del cliente
        self.cursor.execute("""
            SELECT cl.nombre_comercial, c.fecha, c.total, c.estado
            FROM cotizaciones c JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cot_id,))
        info = self.cursor.fetchone()
        cliente  = info[0] if info else ''
        cot_total = info[2] if info else 0
        cot_estado = info[3] if info else ''

        # Carpeta de documentos de esta cotización
        base_docs = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'documentos', folio)

        # ── Ventana principal ────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f"📋 Seguimiento — {folio}")
        win.geometry("900x580")
        win.configure(bg='#f1f5f9')
        win.transient(self.root)
        win.grab_set()

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg='#7c3aed', pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"📋  Seguimiento de Cotización",
                 font=('Arial', 12, 'bold'), bg='#7c3aed', fg='white').pack()
        tk.Label(hdr, text=f"{folio}  •  {cliente}  •  ${cot_total:,.2f}  •  {cot_estado}",
                 font=('Arial', 9), bg='#7c3aed', fg='#d8b4fe').pack()

        # ── Contenedor de tarjetas ────────────────────────────────────────────
        cards_frame = tk.Frame(win, bg='#f1f5f9')
        cards_frame.pack(fill='both', expand=True, padx=16, pady=12)

        # Diccionario para referencias a widgets por etapa
        widgets_etapa = {}

        def cargar_etapas():
            for w in cards_frame.winfo_children():
                w.destroy()

            # Obtener datos guardados de seguimiento
            self.cursor.execute("""
                SELECT etapa, completada, referencia, fecha_etapa, notas
                FROM seguimiento_etapas WHERE cotizacion_id = ?
            """, (cot_id,))
            datos = {row[0]: row for row in self.cursor.fetchall()}

            # Documentos físicos por tipo (OC, Complemento)
            self.cursor.execute("""
                SELECT tipo, COUNT(*) FROM documentos_cotizacion
                WHERE cotizacion_id = ? GROUP BY tipo
            """, (cot_id,))
            docs_count = dict(self.cursor.fetchall())

            # Factura XML vinculada
            self.cursor.execute("""
                SELECT id, uuid, serie, folio_factura, fecha, total,
                       rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
                       subtotal, iva, metodo_pago, forma_pago, ruta_xml
                FROM facturas WHERE cotizacion_id = ?
                ORDER BY fecha_registro DESC LIMIT 1
            """, (cot_id,))
            fac_row = self.cursor.fetchone()
            factura_xml = None
            if fac_row:
                factura_xml = {
                    'id': fac_row[0], 'uuid': fac_row[1],
                    'serie': fac_row[2], 'folio': fac_row[3],
                    'fecha': (fac_row[4] or '')[:10],
                    'total': fac_row[5] or 0,
                    'rfc_emisor': fac_row[6], 'nombre_emisor': fac_row[7],
                    'rfc_receptor': fac_row[8], 'nombre_receptor': fac_row[9],
                    'subtotal': fac_row[10] or 0, 'iva': fac_row[11] or 0,
                    'metodo_pago': fac_row[12], 'forma_pago': fac_row[13],
                    'ruta_xml': fac_row[14],
                }

            # Barra de progreso
            etapas_completas = sum(
                1 for e, _, _, _ in self._ETAPAS_SEG
                if datos.get(e, (None, 0))[1]
            )
            # Contar Facturada como completada si hay XML aunque no esté en seguimiento
            if factura_xml and not datos.get('Facturada', (None, 0))[1]:
                etapas_completas += 1
            total_etapas = len(self._ETAPAS_SEG)

            prog_frame = tk.Frame(cards_frame, bg='#f1f5f9')
            prog_frame.pack(fill='x', pady=(0, 10))
            tk.Label(prog_frame, text=f"Progreso: {etapas_completas}/{total_etapas} etapas",
                     font=('Arial', 9, 'bold'), bg='#f1f5f9', fg='#374151').pack(side='left')
            pct = int((etapas_completas / total_etapas) * 100)
            tk.Label(prog_frame, text=f"{pct}%",
                     font=('Arial', 9, 'bold'), bg='#f1f5f9', fg='#7c3aed').pack(side='right')
            bar_outer = tk.Frame(prog_frame, bg='#e2e8f0', height=8)
            bar_outer.pack(fill='x', pady=(6, 0))
            bar_outer.pack_propagate(False)
            if pct > 0:
                tk.Frame(bar_outer, bg='#7c3aed', height=8,
                         width=max(4, int(bar_outer.winfo_reqwidth() * pct / 100))
                         ).pack(side='left')

            # Una tarjeta por etapa
            for etapa, icono, fg, bg in self._ETAPAS_SEG:
                d = datos.get(etapa)
                completada  = bool(d[1]) if d else False
                referencia  = d[2] or '' if d else ''
                fecha_etapa = d[3] or '' if d else ''
                notas       = d[4] or '' if d else ''

                tipo_doc_map = {
                    'Orden de Compra':     'Orden de Compra',
                    'Facturada':           'Factura',
                    'Complemento de Pago': 'Complemento de Pago',
                }
                tipo_doc = tipo_doc_map.get(etapa)
                n_docs   = docs_count.get(tipo_doc, 0) if tipo_doc else 0

                # Facturada: completada visualmente si hay XML vinculado
                if etapa == 'Facturada' and factura_xml:
                    completada = True

                card_bg = bg if completada else '#ffffff'
                border  = fg if completada else '#cbd5e1'

                card = tk.Frame(cards_frame, bg=card_bg, pady=8, padx=12,
                                highlightbackground=border, highlightthickness=2)
                card.pack(fill='x', pady=4)

                top = tk.Frame(card, bg=card_bg)
                top.pack(fill='x')

                estado_txt = '✅' if completada else '⏳'
                tk.Label(top, text=f"{estado_txt} {icono}  {etapa}",
                         font=('Arial', 11, 'bold'), bg=card_bg,
                         fg=fg if completada else '#6b7280').pack(side='left')

                btn_frame = tk.Frame(top, bg=card_bg)
                btn_frame.pack(side='right')

                # Botón ver: Facturada → detalle XML; otros → archivo físico
                if etapa == 'Facturada' and factura_xml:
                    def _ver_fac_xml(fid=factura_xml['id']):
                        if hasattr(self, '_facturacion'):
                            self.sistema._facturacion._mostrar_detalle_por_id(fid)
                    tk.Button(btn_frame, text='🧾 Ver CFDI',
                              command=_ver_fac_xml, bg='#cffafe', fg='#0e7490',
                              font=('Arial', 8, 'bold'), cursor='hand2',
                              relief='flat', padx=8, pady=3).pack(side='left', padx=(0, 6))
                elif n_docs > 0 and tipo_doc and etapa != 'Facturada':
                    def _abrir_doc(tp=tipo_doc):
                        self.cursor.execute("""
                            SELECT ruta_archivo FROM documentos_cotizacion
                            WHERE cotizacion_id=? AND tipo=?
                            ORDER BY fecha_registro DESC LIMIT 1
                        """, (cot_id, tp))
                        frow = self.cursor.fetchone()
                        if frow and os.path.exists(frow[0]):
                            try:
                                if platform.system() == 'Windows': os.startfile(frow[0])
                                elif platform.system() == 'Darwin': subprocess.Popen(['open', frow[0]])
                                else: subprocess.Popen(['xdg-open', frow[0]])
                            except Exception as ex:
                                messagebox.showerror("Error", str(ex), parent=win)
                        else:
                            messagebox.showerror("No encontrado",
                                "El archivo no está disponible", parent=win)
                    lbl_doc = '📋' if tipo_doc == 'Orden de Compra' else '💳'
                    tk.Button(btn_frame, text=f'{lbl_doc} Ver doc ({n_docs})',
                              command=_abrir_doc, bg='#e0e7ff', fg='#3730a3',
                              font=('Arial', 8, 'bold'), cursor='hand2',
                              relief='flat', padx=8, pady=3).pack(side='left', padx=(0, 6))

                # Botón Editar etapa
                def _editar(e=etapa, comp=completada, ref=referencia,
                            fe=fecha_etapa, n=notas):
                    self._editar_etapa_seguimiento(win, cot_id, e, comp, ref, fe, n,
                                                   tipo_doc_map.get(e), cargar_etapas)
                tk.Button(btn_frame, text='✏️ Editar',
                          command=_editar, bg='#f3f4f6', fg='#374151',
                          font=('Arial', 8), cursor='hand2',
                          relief='flat', padx=8, pady=3).pack(side='left')

                # Detalle de la tarjeta
                if etapa == 'Facturada' and factura_xml:
                    det = tk.Frame(card, bg=card_bg)
                    det.pack(fill='x', pady=(6, 0))
                    fac = factura_xml
                    sf  = f"{fac['serie']}-{fac['folio']}" if fac['serie'] else (fac['folio'] or '—')
                    lineas = [
                        f"📄 {sf}   •   Fecha: {fac['fecha']}   •   Total: ${fac['total']:,.2f}",
                        f"UUID: {fac['uuid']}",
                        f"Receptor: {fac['rfc_receptor']}  {fac['nombre_receptor']}",
                    ]
                    if fac['metodo_pago'] or fac['forma_pago']:
                        lineas.append(
                            f"Método pago: {fac['metodo_pago'] or '—'}   Forma: {fac['forma_pago'] or '—'}")
                    if notas:
                        lineas.append(f"📝 {notas}")
                    for line in lineas:
                        tk.Label(det, text=line, font=('Arial', 8),
                                 bg=card_bg, fg='#0e7490', anchor='w').pack(fill='x')

                elif completada or referencia or fecha_etapa or notas:
                    det = tk.Frame(card, bg=card_bg)
                    det.pack(fill='x', pady=(6, 0))
                    campos = []
                    if referencia:  campos.append(f"Ref: {referencia}")
                    if fecha_etapa: campos.append(f"Fecha: {fecha_etapa}")
                    if notas:       campos.append(f"📝 {notas}")
                    if campos:
                        tk.Label(det, text="   ".join(campos),
                                 font=('Arial', 8), bg=card_bg, fg='#4b5563',
                                 anchor='w').pack(fill='x')


        # ── Pie de ventana ────────────────────────────────────────────────────
        foot = tk.Frame(win, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')
        tk.Button(foot, text='📎 Gestionar documentos',
                  command=lambda: [win.destroy(), self.gestionar_documentos_cotizacion()],
                  bg='#16a085', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5, relief='raised').pack(side='left', padx=12)
        def _cerrar_seguimiento():
            win.destroy()
            self.cargar_cotizaciones()
            self.sistema.actualizar_dashboard()

        tk.Button(foot, text='Cerrar', command=_cerrar_seguimiento,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=12, pady=5, relief='raised').pack(side='right', padx=12)

        win.protocol('WM_DELETE_WINDOW', _cerrar_seguimiento)

        cargar_etapas()

    def _editar_etapa_seguimiento(self, parent, cot_id, etapa, completada,
                                   referencia, fecha_etapa, notas,
                                   tipo_doc, callback_recargar):
        """Diálogo para editar una etapa de seguimiento."""
        import shutil

        dlg = tk.Toplevel(parent)
        dlg.title(f"Editar etapa — {etapa}")
        dlg.geometry("480x400")
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()
        dlg.configure(bg='#f8fafc')

        tk.Label(dlg, text=f"✏️  {etapa}",
                 font=('Arial', 12, 'bold'), bg='#f8fafc', fg='#1e293b').pack(pady=(18, 10))

        form = tk.Frame(dlg, bg='#f8fafc')
        form.pack(fill='x', padx=24)
        form.grid_columnconfigure(1, weight=1)

        def lbl(row, texto):
            tk.Label(form, text=texto, font=('Arial', 9, 'bold'),
                     bg='#f8fafc', fg='#374151', anchor='e').grid(
                row=row, column=0, sticky='e', padx=(0, 10), pady=6)

        # Completada
        lbl(0, 'Estado:')
        var_comp = tk.BooleanVar(value=completada)
        chk = tk.Checkbutton(form, text='Marcar como completada',
                              variable=var_comp, bg='#f8fafc',
                              font=('Arial', 9))
        chk.grid(row=0, column=1, sticky='w')

        # Referencia
        lbl(1, 'Referencia:')
        entry_ref = tk.Entry(form, font=('Arial', 9), width=32)
        entry_ref.insert(0, referencia)
        entry_ref.grid(row=1, column=1, sticky='ew')

        # Fecha
        lbl(2, 'Fecha:')
        entry_fecha = tk.Entry(form, font=('Arial', 9), width=18)
        entry_fecha.insert(0, fecha_etapa)
        entry_fecha.grid(row=2, column=1, sticky='w')
        tk.Label(form, text='YYYY-MM-DD', font=('Arial', 7),
                 bg='#f8fafc', fg='#9ca3af').grid(row=3, column=1, sticky='w')

        # Notas
        lbl(4, 'Notas:')
        entry_notas = tk.Text(form, font=('Arial', 9), width=32, height=3,
                              wrap='word', relief='solid', bd=1)
        entry_notas.insert('1.0', notas)
        entry_notas.grid(row=4, column=1, sticky='ew', pady=(0, 4))

        # Adjuntar documento
        if tipo_doc:
            lbl(5, 'Documento:')
            def _adjuntar():
                base_docs = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), 'documentos',
                )
                # Obtener folio para la carpeta
                self.cursor.execute("SELECT folio FROM cotizaciones WHERE id=?", (cot_id,))
                folio = self.cursor.fetchone()[0]
                tipo_carpeta_map = {
                    'Orden de Compra':     'OC',
                    'Factura':             'Facturas',
                    'Complemento de Pago': 'Complementos',
                }
                carpeta = os.path.join(base_docs, folio,
                                       tipo_carpeta_map.get(tipo_doc, 'Otros'))
                os.makedirs(carpeta, exist_ok=True)
                rutas = filedialog.askopenfilenames(
                    title=f"Adjuntar {tipo_doc}",
                    filetypes=[("Documentos", "*.pdf *.xml *.docx *.xlsx *.png *.jpg"),
                               ("Todos", "*.*")],
                    parent=dlg)
                for ruta_orig in rutas:
                    nombre = os.path.basename(ruta_orig)
                    destino = os.path.join(carpeta, nombre)
                    base, ext = os.path.splitext(nombre)
                    cnt = 1
                    while os.path.exists(destino):
                        destino = os.path.join(carpeta, f"{base}_{cnt}{ext}")
                        cnt += 1
                    try:
                        shutil.copy2(ruta_orig, destino)
                        self.cursor.execute("""
                            INSERT INTO documentos_cotizacion
                            (cotizacion_id, tipo, nombre_archivo, ruta_archivo)
                            VALUES (?, ?, ?, ?)
                        """, (cot_id, tipo_doc, os.path.basename(destino), destino))
                        self.conn.commit()
                    except Exception as e:
                        messagebox.showerror("Error", str(e), parent=dlg)
                if rutas:
                    messagebox.showinfo("Listo",
                        f"{len(rutas)} archivo(s) adjuntados", parent=dlg)

            tk.Button(form, text=f'📎 Adjuntar {tipo_doc}',
                      command=_adjuntar, bg='#16a085', fg='white',
                      font=('Arial', 8, 'bold'), cursor='hand2',
                      padx=10, pady=4, relief='raised').grid(
                row=5, column=1, sticky='w', pady=6)

        # Botones guardar/cancelar
        btns = tk.Frame(dlg, bg='#f8fafc')
        btns.pack(pady=14)

        def _guardar():
            comp  = var_comp.get()
            ref   = entry_ref.get().strip()
            fecha = entry_fecha.get().strip()
            n     = entry_notas.get('1.0', 'end').strip()
            try:
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas
                        (cotizacion_id, etapa, completada, referencia, fecha_etapa, notas)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada  = excluded.completada,
                        referencia  = excluded.referencia,
                        fecha_etapa = excluded.fecha_etapa,
                        notas       = excluded.notas
                """, (cot_id, etapa, int(comp), ref or None, fecha or None, n or None))

                # ── Si es Orden de Compra, sincronizar referencia → cotizaciones.orden_compra
                if etapa == 'Orden de Compra' and ref:
                    self.cursor.execute("""
                        UPDATE cotizaciones
                        SET orden_compra = ?,
                            fecha_orden_compra = COALESCE(NULLIF(?, ''), fecha_orden_compra)
                        WHERE id = ?
                    """, (ref, fecha or None, cot_id))

                # ── Si es Facturada, sincronizar referencia → cotizaciones.numero_factura
                if etapa == 'Facturada' and ref:
                    self.cursor.execute("""
                        UPDATE cotizaciones
                        SET numero_factura = ?,
                            fecha_factura = COALESCE(NULLIF(?, ''), fecha_factura)
                        WHERE id = ?
                    """, (ref, fecha or None, cot_id))

                # ── Sincronizar cotizaciones.estado ─────────────────────────
                self._sync_estado_desde_seguimiento(cot_id, etapa, comp)

                self.conn.commit()

                # Siempre refrescar lista (puede haber cambiado O.C. o estado)
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()

            except Exception as e:
                messagebox.showerror("Error al guardar", str(e), parent=dlg)
                return
            dlg.destroy()
            callback_recargar()

        tk.Button(btns, text='💾 Guardar', command=_guardar,
                  bg='#7c3aed', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=8)
        tk.Button(btns, text='Cancelar', command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='left')

    # ── Mapa bidireccional estado ↔ etapa de seguimiento ──────────────────────
    _ESTADO_A_ETAPA = {
        'Entregada':  'Entregada',
        'Facturada':  'Facturada',
        'Pagada':     'Pagada',
    }
    _ETAPA_A_ESTADO = {
        'Entregada':  'Entregada',
        'Facturada':  'Facturada',
        'Pagada':     'Pagada',
    }

    def _sync_seguimiento_desde_estado(self, cotizacion_id, nuevo_estado, fecha=None):
        """Sincroniza seguimiento_etapas cuando cambia cotizaciones.estado.
        
        Si el nuevo_estado corresponde a una etapa de seguimiento conocida,
        hace un UPSERT marcándola como completada con la fecha indicada.
        """
        etapa = self._ESTADO_A_ETAPA.get(nuevo_estado)
        if not etapa:
            return
        fecha_etapa = fecha or datetime.now().strftime('%Y-%m-%d')
        self.cursor.execute("""
            INSERT INTO seguimiento_etapas
                (cotizacion_id, etapa, completada, fecha_etapa)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                completada  = 1,
                fecha_etapa = COALESCE(excluded.fecha_etapa, fecha_etapa)
        """, (cotizacion_id, etapa, fecha_etapa))

    def _sync_estado_desde_seguimiento(self, cotizacion_id, etapa, completada):
        """Sincroniza cotizaciones.estado y monto_pagado cuando se edita
        una etapa de seguimiento.
        """
        if not completada:
            return False

        # ── Pagada: marcar pago completo ─────────────────────────────────
        if etapa == 'Pagada':
            self.cursor.execute(
                "SELECT total, monto_pagado, estado FROM cotizaciones WHERE id=?",
                (cotizacion_id,))
            row = self.cursor.fetchone()
            if not row:
                return False
            total, monto_pagado, estado_actual = row
            # Si aún no tiene monto_pagado registrado, asignar el total completo
            nuevo_pagado = monto_pagado if (monto_pagado and monto_pagado >= total) else total
            from datetime import datetime as _dt
            self.cursor.execute("""
                UPDATE cotizaciones
                SET monto_pagado = ?,
                    fecha_pago   = COALESCE(NULLIF(fecha_pago,''), ?),
                    estado       = 'Pagada'
                WHERE id = ?
            """, (nuevo_pagado, _dt.now().strftime('%Y-%m-%d'), cotizacion_id))
            return True

        # ── Entregada: sincronizar estado ────────────────────────────────
        if etapa != 'Entregada':
            return False
        nuevo_estado = 'Entregada'
        orden = ['Pendiente', 'Programada', 'Parcialmente Entregada', 'Entregada', 'Cancelada']
        self.cursor.execute("SELECT estado FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        row = self.cursor.fetchone()
        if not row:
            return False
        estado_actual = row[0]
        idx_actual = orden.index(estado_actual) if estado_actual in orden else 0
        idx_nuevo  = orden.index(nuevo_estado)  if nuevo_estado  in orden else 0
        if idx_nuevo > idx_actual:
            self.cursor.execute(
                "UPDATE cotizaciones SET estado = ? WHERE id = ?",
                (nuevo_estado, cotizacion_id))
            return True
        return False

    def gestionar_documentos_cotizacion(self):
        """Abre ventana para gestionar documentos adjuntos de la cotización seleccionada."""
        import shutil, subprocess, platform

        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return

        item   = self.tree_cotizaciones.item(seleccion[0])
        cot_id = item['values'][0]
        folio  = item['values'][1]

        # Directorio base de documentos junto a la BD
        base_docs = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'documentos', folio)
        tipos_carpeta = {
            'Orden de Compra':       os.path.join(base_docs, 'OC'),
            'Factura':               os.path.join(base_docs, 'Facturas'),
            'Complemento de Pago':   os.path.join(base_docs, 'Complementos'),
            'Otro':                  os.path.join(base_docs, 'Otros'),
        }
        for carpeta in tipos_carpeta.values():
            os.makedirs(carpeta, exist_ok=True)

        # ── Ventana ──────────────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f"📎 Documentos — {folio}")
        win.geometry("860x560")
        win.configure(bg='#eceff4')
        win.transient(self.root)

        # Header
        hdr = tk.Frame(win, bg='#16a085', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"📎  Documentos adjuntos", font=('Arial', 11, 'bold'),
                 bg='#16a085', fg='white').pack()
        tk.Label(hdr, text=folio, font=('Arial', 9),
                 bg='#16a085', fg='#d5f5ef').pack()

        # Toolbar
        tb = tk.Frame(win, bg='#d8dde8', pady=5)
        tb.pack(fill='x')
        tk.Frame(win, bg='#c5ccd8', height=1).pack(fill='x')

        # ── Tabla de documentos ───────────────────────────────────────────────
        cols = ('ID', 'Tipo', 'Archivo', 'Notas', 'Fecha')
        tree = ttk.Treeview(win, columns=cols, show='headings', selectmode='browse')
        tree.heading('ID',     text='ID')
        tree.heading('Tipo',   text='Tipo')
        tree.heading('Archivo',text='Archivo')
        tree.heading('Notas',  text='Notas')
        tree.heading('Fecha',  text='Fecha')
        tree.column('ID',     width=0,   stretch=False)
        tree.column('Tipo',   width=160, anchor='w')
        tree.column('Archivo',width=280, anchor='w')
        tree.column('Notas',  width=200, anchor='w')
        tree.column('Fecha',  width=140, anchor='w')

        # Colores por tipo
        tree.tag_configure('Orden de Compra',     background='#dbeafe', foreground='#1a4b8c')
        tree.tag_configure('Factura',             background='#dcfce7', foreground='#166534')
        tree.tag_configure('Complemento de Pago', background='#fef3c7', foreground='#92400e')
        tree.tag_configure('Otro',                background='#f1f5f9', foreground='#334155')
        tree.tag_configure('missing',             background='#fee2e2', foreground='#991b1b')

        sc_y = ttk.Scrollbar(win, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sc_y.set)

        frame_tree = tk.Frame(win, bg='#eceff4')
        frame_tree.pack(fill='both', expand=True, padx=10, pady=8)
        tree.pack(in_=frame_tree, side='left', fill='both', expand=True)
        sc_y.pack(in_=frame_tree, side='right', fill='y')

        def cargar_docs():
            tree.delete(*tree.get_children())
            self.cursor.execute("""
                SELECT id, tipo, nombre_archivo, ruta_archivo, notas, fecha_registro
                FROM documentos_cotizacion
                WHERE cotizacion_id = ?
                ORDER BY tipo, fecha_registro
            """, (cot_id,))
            for row in self.cursor.fetchall():
                doc_id, tipo, nombre, ruta, notas, fecha = row
                existe = os.path.exists(ruta)
                tag = tipo if existe else 'missing'
                nombre_show = nombre + (' ⚠ archivo no encontrado' if not existe else '')
                tree.insert('', 'end', values=(doc_id, tipo, nombre_show,
                                               notas or '', fecha[:16]),
                            tags=(tag,))

        def abrir_archivo(event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0])['values']
            doc_id = vals[0]
            self.cursor.execute("SELECT ruta_archivo FROM documentos_cotizacion WHERE id=?",
                                (doc_id,))
            row = self.cursor.fetchone()
            if not row:
                return
            ruta = row[0]
            if not os.path.exists(ruta):
                messagebox.showerror("No encontrado",
                    f"El archivo ya no existe en:\n{ruta}", parent=win)
                return
            try:
                if platform.system() == 'Windows':
                    os.startfile(ruta)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', ruta])
                else:
                    subprocess.Popen(['xdg-open', ruta])
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def abrir_carpeta():
            """Abre la carpeta de documentos de esta cotización en el explorador."""
            try:
                if platform.system() == 'Windows':
                    os.startfile(base_docs)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', base_docs])
                else:
                    subprocess.Popen(['xdg-open', base_docs])
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def agregar_documento():
            # Diálogo para elegir tipo
            dlg = tk.Toplevel(win)
            dlg.title("Agregar Documento")
            dlg.geometry("420x260")
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            dlg.configure(bg='#f8fafc')

            tk.Label(dlg, text="Tipo de documento:", font=('Arial', 10, 'bold'),
                     bg='#f8fafc').pack(pady=(18, 4))

            var_tipo = tk.StringVar(value='Orden de Compra')
            for t in tipos_carpeta:
                tk.Radiobutton(dlg, text=t, variable=var_tipo, value=t,
                               font=('Arial', 10), bg='#f8fafc').pack(anchor='w', padx=40)

            tk.Label(dlg, text="Notas (opcional):", font=('Arial', 9),
                     bg='#f8fafc').pack(pady=(10, 2))
            entry_notas = tk.Entry(dlg, font=('Arial', 9), width=40)
            entry_notas.pack()

            def seleccionar_archivo():
                tipo = var_tipo.get()
                notas = entry_notas.get().strip()
                carpeta_destino = tipos_carpeta[tipo]

                rutas = filedialog.askopenfilenames(
                    title=f"Seleccionar {tipo}",
                    filetypes=[
                        ("Documentos", "*.pdf *.xml *.docx *.xlsx *.png *.jpg *.jpeg"),
                        ("PDF", "*.pdf"), ("XML", "*.xml"), ("Todos", "*.*")
                    ],
                    parent=dlg
                )
                if not rutas:
                    return

                agregados = 0
                for ruta_orig in rutas:
                    nombre = os.path.basename(ruta_orig)
                    destino = os.path.join(carpeta_destino, nombre)

                    # Si ya existe, agregar sufijo numérico
                    base, ext = os.path.splitext(nombre)
                    contador = 1
                    while os.path.exists(destino):
                        destino = os.path.join(carpeta_destino, f"{base}_{contador}{ext}")
                        contador += 1
                    nombre_final = os.path.basename(destino)

                    try:
                        shutil.copy2(ruta_orig, destino)
                        self.cursor.execute("""
                            INSERT INTO documentos_cotizacion
                            (cotizacion_id, tipo, nombre_archivo, ruta_archivo, notas)
                            VALUES (?, ?, ?, ?, ?)
                        """, (cot_id, tipo, nombre_final, destino, notas or None))
                        agregados += 1
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo copiar {nombre}:\n{e}",
                                             parent=dlg)

                self.conn.commit()
                dlg.destroy()
                cargar_docs()
                if agregados:
                    messagebox.showinfo("Éxito",
                        f"{agregados} archivo(s) guardado(s) en:\n{carpeta_destino}",
                        parent=win)

            tk.Button(dlg, text="📂 Seleccionar archivo(s)", command=seleccionar_archivo,
                      bg='#16a085', fg='white', font=('Arial', 10, 'bold'),
                      cursor='hand2', padx=14, pady=7).pack(pady=14)

        def eliminar_documento():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un documento", parent=win)
                return
            vals  = tree.item(sel[0])['values']
            doc_id = vals[0]
            nombre = vals[2]

            self.cursor.execute("SELECT ruta_archivo FROM documentos_cotizacion WHERE id=?",
                                (doc_id,))
            row = self.cursor.fetchone()
            if not row:
                return
            ruta = row[0]

            resp = messagebox.askyesnocancel(
                "Eliminar documento",
                f"¿Qué deseas hacer con '{nombre}'?\n\n"
                "  [Sí]    → Eliminar registro Y archivo del disco\n"
                "  [No]    → Eliminar solo el registro (mantener archivo)\n"
                "  [Cancelar] → No hacer nada",
                parent=win
            )
            if resp is None:
                return
            try:
                self.cursor.execute("DELETE FROM documentos_cotizacion WHERE id=?", (doc_id,))
                self.conn.commit()
                if resp and os.path.exists(ruta):
                    os.remove(ruta)
                cargar_docs()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        # Botones del toolbar
        for texto, cmd, color in [
            ('➕ Agregar',        agregar_documento, '#16a085'),
            ('🗂️ Abrir carpeta',  abrir_carpeta,     '#1a4b8c'),
            ('📂 Abrir archivo',  abrir_archivo,     '#d97706'),
            ('🗑️ Eliminar',       eliminar_documento,'#c0392b'),
        ]:
            tk.Button(tb, text=texto, command=cmd,
                      bg=color, fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=10, pady=4,
                      relief='raised', bd=1).pack(side='left', padx=3)

        # Nota de ruta
        nota_frame = tk.Frame(win, bg='#e8f4f8', pady=4)
        nota_frame.pack(fill='x', padx=10, pady=(0, 6))
        tk.Label(nota_frame,
                 text=f"📁  Carpeta: {base_docs}",
                 font=('Arial', 7), bg='#e8f4f8', fg='#2c3e50',
                 anchor='w').pack(fill='x', padx=8)

        tree.bind('<Double-1>', abrir_archivo)
        cargar_docs()
        win.grab_set()


    def _on_select_cotizacion(self):
        """Actualiza el panel de preview al seleccionar una cotización."""
        sel = self.tree_cotizaciones.selection()
        if not sel:
            return
        cot_id = self.tree_cotizaciones.item(sel[0])['values'][0]
        self._actualizar_preview_cot(cot_id)

    def _actualizar_preview_cot(self, cot_id):
        """Rellena el panel de preview con los datos de la cotización indicada."""
        if not hasattr(self, '_pv_tree'):
            return

        # Datos generales
        self.cursor.execute("""
            SELECT c.folio, c.fecha, c.estado, c.subtotal, c.iva, c.total,
                   c.monto_entregado, c.monto_pagado,
                   cl.nombre_comercial, cl.contacto
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = ?
        """, (cot_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        (folio, fecha, estado, subtotal, iva, total,
         entregado, pagado, cliente, contacto) = row

        estado_colores = {
            'Pendiente': '#d97706', 'Programada': '#1d4ed8',
            'Parcialmente Entregada': '#7c3aed', 'Entregada': '#166534',
            'Facturada': '#0e7490', 'Pagada': '#065f46', 'Cancelada': '#6b7280',
        }
        color_estado = estado_colores.get(estado, '#374151')

        self._pv_folio.config(text=folio)
        self._pv_cliente.config(text=f'👤 {cliente}' + (f'  •  {contacto}' if contacto else ''))
        self._pv_estado.config(text=f'● {estado}', fg=color_estado)
        self._pv_fecha.config(text=f'📅 {(fecha or "")[:10]}')

        # Productos
        self._pv_tree.delete(*self._pv_tree.get_children())
        self.cursor.execute("""
            SELECT p.nombre, cd.cantidad, cd.precio_unitario, cd.subtotal
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = ?
            ORDER BY cd.id
        """, (cot_id,))
        for i, (nombre, cant, precio, subtotal_prod) in enumerate(self.cursor.fetchall()):
            tag = 'par' if i % 2 == 0 else 'impar'
            self._pv_tree.insert('', 'end', tags=(tag,), values=(
                nombre,
                f'{cant:g}',
                f'${precio:,.2f}',
                f'${subtotal_prod:,.2f}',
            ))

        # Totales
        self._pv_subtotal.config(text=f'${subtotal:,.2f}')
        self._pv_iva.config(text=f'${iva:,.2f}')
        self._pv_total.config(text=f'${total:,.2f}')
        self._pv_entregado.config(text=f'${entregado:,.2f}')
        self._pv_pagado.config(text=f'${pagado:,.2f}')

    # ── SECCIÓN: CATÁLOGOS ─────────────────────────────────────────────────


