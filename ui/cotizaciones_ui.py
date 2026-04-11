#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/cotizaciones_ui.py
Componente CotizacionesUI — orquesta la sección Cotizaciones.
La lógica de cada sección está en los mixins correspondientes.

Uso:
    from ui.cotizaciones_ui import CotizacionesUI
    self.cotizaciones_ui = CotizacionesUI(self)
    self.cotizaciones_ui.crear_seccion()
"""

import tkinter as tk
from tkinter import ttk, messagebox

from modules.vinculacion import PanelVinculacion, detectar_pendientes

from ui.cotizaciones_lista_mixin       import _CotizacionesListaMixin
from ui.cotizaciones_detalle_mixin     import _CotizacionesDetalleMixin
from ui.cotizaciones_estados_mixin     import _CotizacionesEstadosMixin
from ui.cotizaciones_seguimiento_mixin import _CotizacionesSeguimientoMixin


class CotizacionesUI(
    _CotizacionesListaMixin,
    _CotizacionesDetalleMixin,
    _CotizacionesEstadosMixin,
    _CotizacionesSeguimientoMixin,
):
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

        self.sistema._toolbar_btn(tb, '➕ Nueva', self.nueva_cotizacion, color=self.C['accent'], tip='Nueva cotización (Ctrl+N)')
        self.sistema._toolbar_btn(tb, '✏️ Editar', self.editar_cotizacion, tip='Editar cotización seleccionada')
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
        self.sistema._toolbar_btn(tb, '📋 Seguimiento', self.ver_seguimiento_cotizacion, color='#7c3aed', tip='Ver y editar etapas de seguimiento: OC, Entrega, Factura, Complemento y Pago')
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '📊 Estado de Cuenta', self.ver_estado_cuenta, color='#0e7490', tip='Generar estado de cuenta del cliente con detalle de pedidos y saldos')
        self.sistema._toolbar_sep(tb)
        self._btn_vincular = self.sistema._toolbar_btn(tb, '🔗 Vincular', self._abrir_centro_vinculacion, color='#7c3aed', tip='Vincular facturas XML a cotizaciones. Muestra el número de facturas pendientes de vincular')
        self._actualizar_badge_vinculacion()

        # ── Atajos de sección ──────────────────────────────────────────────
        def _atajos_cot(event):
            key = event.keysym.lower()
            state = event.state
            ctrl = (state & 0x4) != 0
            if ctrl and key == 'n':
                self.nueva_cotizacion()
            elif ctrl and key == 'e':
                self.editar_cotizacion()
            elif ctrl and key == 'f':
                self.entry_buscar_cotizacion.focus()
                self.entry_buscar_cotizacion.select_range(0, 'end')
            elif key == 'escape':
                # Limpiar búsqueda y filtro
                self.entry_buscar_cotizacion.delete(0, 'end')
                if self._filtro_estado_cot:
                    self._filtro_estado_cot.set('Todos')
                self.cargar_cotizaciones()
            elif key == 'f5':
                self.cargar_cotizaciones()
            return 'break' if ctrl and key in ('n','e','f') else None

        sec.bind('<Key>', _atajos_cot)
        sec.bind_all('<Key>', lambda e: _atajos_cot(e)
                     if self.sistema._seccion_actual.get() == 'cotizaciones' else None)
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '📊 Exportar CSV', self.exportar_csv, color='#065f46', tip='Exportar vista actual a CSV (respeta filtros activos)')

        # Barra de filtros
        ff = tk.Frame(sec, bg=self.C['toolbar_bg'], pady=4)
        ff.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        tk.Label(ff, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=(8, 2))
        self.entry_buscar_cotizacion = tk.Entry(ff, font=('Arial', 9), width=25)
        self.entry_buscar_cotizacion.pack(side='left', padx=4)
        self.entry_buscar_cotizacion.bind('<KeyRelease>', lambda e: self.cargar_cotizaciones())
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
                'Observaciones', 'Días')
        self.tree_cotizaciones = ttk.Treeview(
            ft, columns=cols, show='headings', selectmode='browse')

        wcfg = {
            'ID': 0, 'Folio': 115, 'Fecha': 88, 'Cliente': 185,
            'Total': 88, 'Estado': 138,
            'Entregado': 86, 'O.C.': 120, '_oc_doc': 36,
            'Ref. Factura': 120, '_fac_doc': 36, 'Pagado': 86,
            'Observaciones': 160, 'Días': 55,
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
        # Urgencia — sin cambio de fondo, el indicador visual está en la columna Días
        self.tree_cotizaciones.tag_configure('urg_alta',  font=('Arial', 9))
        self.tree_cotizaciones.tag_configure('urg_media', font=('Arial', 9))
        self.tree_cotizaciones.tag_configure('urg_baja',  font=('Arial', 9))

        sc_y = ttk.Scrollbar(ft, orient='vertical',   command=self.tree_cotizaciones.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal', command=self.tree_cotizaciones.xview)
        self.tree_cotizaciones.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        self.tree_cotizaciones.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        self.tree_cotizaciones.bind('<Double-1>', self._doble_clic_cotizacion)

        # Tooltips para columnas de íconos
        _tip_tree = [None]
        def _tree_tooltip(event):
            col = self.tree_cotizaciones.identify_column(event.x)
            tips = {
                '#9':  '📋 Documentos de OC\nClic para ver/adjuntar archivos',
                '#11': '🧾 Facturas XML vinculadas\nClic para ver detalle',
            }
            txt = tips.get(col)
            if _tip_tree[0]:
                try: _tip_tree[0].destroy()
                except: pass
                _tip_tree[0] = None
            if txt:
                t = tk.Toplevel()
                t.wm_overrideredirect(True)
                t.wm_geometry(f'+{event.x_root+10}+{event.y_root+18}')
                t.configure(bg='#1e2d45')
                tk.Label(t, text=txt, font=('Arial', 8), bg='#1e2d45',
                         fg='#e2e8f0', padx=8, pady=4, justify='left').pack()
                _tip_tree[0] = t
                t.after(2200, lambda _t=t: _t.destroy() if _tip_tree[0] == _t else None)
        self.tree_cotizaciones.bind('<Motion>', _tree_tooltip)
        self.tree_cotizaciones.bind('<Leave>',
            lambda e: [_tip_tree[0].destroy(), _tip_tree.__setitem__(0, None)]
            if _tip_tree[0] else None)
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
        """Panel de preview — layout C: avatar, KPIs, etapas, tabla, financiero."""
        BG   = '#f8fafc'
        BG2  = '#f1f5f9'
        BDR  = '#e2e8f0'

        parent.grid_rowconfigure(3, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # ── HEADER: avatar + folio + cliente + estado + KPIs ──────────────
        hdr = tk.Frame(parent, bg=BG2)
        hdr.grid(row=0, column=0, columnspan=2, sticky='ew')

        hdr_top = tk.Frame(hdr, bg=BG2, padx=10, pady=8)
        hdr_top.pack(fill='x')

        # Avatar (iniciales)
        self._pv_avatar = tk.Label(hdr_top, text='—',
            font=('Arial', 13, 'bold'), bg='#fef3c7', fg='#92400e',
            width=3, relief='flat')
        self._pv_avatar.pack(side='left', padx=(0, 8))

        hdr_info = tk.Frame(hdr_top, bg=BG2)
        hdr_info.pack(side='left', fill='x', expand=True)

        self._pv_folio = tk.Label(hdr_info, text='—',
            font=('Arial', 12, 'bold'), bg=BG2, fg='#1e2d45', anchor='w')
        self._pv_folio.pack(fill='x')

        self._pv_cliente = tk.Label(hdr_info, text='Selecciona una cotización',
            font=('Arial', 9), bg=BG2, fg='#6b7280', anchor='w')
        self._pv_cliente.pack(fill='x')

        self._pv_fecha = tk.Label(hdr_info, text='',
            font=('Arial', 8), bg=BG2, fg='#9ca3af', anchor='w')
        self._pv_fecha.pack(fill='x')

        hdr_right = tk.Frame(hdr_top, bg=BG2)
        hdr_right.pack(side='right', anchor='ne')

        self._pv_estado = tk.Label(hdr_right, text='',
            font=('Arial', 9, 'bold'), bg='#fef3c7', fg='#92400e',
            padx=6, pady=2, relief='flat')
        self._pv_estado.pack(anchor='e')

        self._pv_dias = tk.Label(hdr_right, text='',
            font=('Arial', 8), bg=BG2, fg='#9ca3af', anchor='e')
        self._pv_dias.pack(anchor='e', pady=(3,0))

        # KPI strip
        tk.Frame(hdr, bg=BDR, height=1).pack(fill='x')
        kpi_frame = tk.Frame(hdr, bg=BG2, padx=8, pady=6)
        kpi_frame.pack(fill='x')
        kpi_frame.grid_columnconfigure((0,1,2), weight=1, uniform='kpi')

        def _kpi(col, label, attr, color):
            f = tk.Frame(kpi_frame, bg='white', relief='flat',
                         highlightbackground=BDR, highlightthickness=1)
            f.grid(row=0, column=col, sticky='ew',
                   padx=(0 if col==0 else 4, 0))
            tk.Label(f, text=label, font=('Arial', 7), bg='white',
                     fg='#9ca3af').pack(anchor='w', padx=5, pady=(4,0))
            lbl = tk.Label(f, text='—', font=('Arial', 11, 'bold'),
                           bg='white', fg=color, anchor='w')
            lbl.pack(anchor='w', padx=5, pady=(0,4))
            setattr(self, attr, lbl)

        _kpi(0, 'Total',      '_pv_kpi_total',     '#0f7b5e')
        _kpi(1, 'Entregado',  '_pv_kpi_entregado', '#1d4ed8')
        _kpi(2, 'Pagado',     '_pv_kpi_pagado',    '#166534')

        tk.Frame(parent, bg=BDR, height=1).grid(row=0, column=0,
            columnspan=2, sticky='ew')

        # ── SEGUIMIENTO: etapas verticales ────────────────────────────────
        seg_outer = tk.Frame(parent, bg=BG)
        seg_outer.grid(row=1, column=0, columnspan=2, sticky='ew')

        tk.Label(seg_outer, text='SEGUIMIENTO', font=('Arial', 7, 'bold'),
                 bg=BG, fg='#9ca3af').pack(anchor='w', padx=12, pady=(7,4))

        self._pv_seg_frame = tk.Frame(seg_outer, bg=BG)
        self._pv_seg_frame.pack(fill='x', padx=8, pady=(0,6))

        tk.Frame(parent, bg=BDR, height=1).grid(row=2, column=0,
            columnspan=2, sticky='ew')

        # ── PRODUCTOS: tabla expansible ───────────────────────────────────
        tk.Label(parent, text='PRODUCTOS', font=('Arial', 7, 'bold'),
                 bg=BG, fg='#9ca3af', anchor='w', padx=12, pady=6
                 ).grid(row=3, column=0, columnspan=2, sticky='ew')

        cols_pv = ('Descripción', 'Cant.', 'P.Unit.', 'Subtotal')
        self._pv_tree = ttk.Treeview(parent, columns=cols_pv,
                                      show='headings', selectmode='none')
        wcfg = {'Descripción': 160, 'Cant.': 38, 'P.Unit.': 68, 'Subtotal': 72}
        for col in cols_pv:
            r = col != 'Descripción'
            self._pv_tree.heading(col, text=col, anchor='e' if r else 'w')
            self._pv_tree.column(col, width=wcfg[col], minwidth=wcfg[col],
                                 stretch=(col == 'Descripción'),
                                 anchor='e' if r else 'w')
        self._pv_tree.tag_configure('par',   background='#f8fafc')
        self._pv_tree.tag_configure('impar', background='white')

        sc_pv = ttk.Scrollbar(parent, orient='vertical',
                               command=self._pv_tree.yview)
        self._pv_tree.configure(yscrollcommand=sc_pv.set)
        self._pv_tree.grid(row=4, column=0, sticky='nsew', padx=(8,0))
        sc_pv.grid(row=4, column=1, sticky='ns')
        parent.grid_rowconfigure(4, weight=1)

        tk.Frame(parent, bg=BDR, height=1).grid(row=5, column=0,
            columnspan=2, sticky='ew')

        # ── RESUMEN FINANCIERO ────────────────────────────────────────────
        fin = tk.Frame(parent, bg=BG, padx=12, pady=8)
        fin.grid(row=6, column=0, columnspan=2, sticky='ew')

        tk.Label(fin, text='RESUMEN FINANCIERO', font=('Arial', 7, 'bold'),
                 bg=BG, fg='#9ca3af').pack(anchor='w', pady=(0,5))

        def _fin_row(label, attr, color='#374151', bold=False, sep=False):
            if sep:
                tk.Frame(fin, bg=BDR, height=1).pack(fill='x', pady=3)
                return
            r = tk.Frame(fin, bg=BG)
            r.pack(fill='x', pady=1)
            tk.Label(r, text=label, font=('Arial', 9), bg=BG,
                     fg='#9ca3af').pack(side='left')
            lbl = tk.Label(r, text='—',
                           font=('Arial', 9, 'bold' if bold else 'normal'),
                           bg=BG, fg=color)
            lbl.pack(side='right')
            setattr(self, attr, lbl)

        _fin_row('Subtotal',         '_pv_subtotal')
        _fin_row('IVA',              '_pv_iva')
        _fin_row(None, None, sep=True)
        _fin_row('Total',            '_pv_total',    '#0f7b5e', bold=True)
        _fin_row(None, None, sep=True)
        _fin_row('Entregado',        '_pv_entregado', '#1d4ed8')
        _fin_row('Pagado',           '_pv_pagado',    '#166534')
        _fin_row(None, None, sep=True)
        _fin_row('Pendiente pago',   '_pv_pendiente', '#d97706', bold=True)


    def _actualizar_badge_urgentes(self):
        """Actualiza el título del tab de cotizaciones con conteo de urgentes."""
        try:
            n = sum(
                1 for iid in self.tree_cotizaciones.get_children()
                if 'urg_alta' in self.tree_cotizaciones.item(iid, 'tags')
                or 'urg_media' in self.tree_cotizaciones.item(iid, 'tags')
            )
            # Buscar el frame de la sección y su LabelFrame padre
            sec = self.sistema._secciones.get('cotizaciones')
            if not sec:
                return
            # Subir hasta encontrar el Notebook (padre del padre del sec)
            nb = sec.master
            if not hasattr(nb, 'tab'):
                nb = nb.master
            if not hasattr(nb, 'tab'):
                return
            for i in range(nb.index('end')):
                txt = nb.tab(i, 'text')
                if 'otizaci' in txt:
                    base = '📋  Cotizaciones'
                    nb.tab(i, text=f'{base}  ⚠ {n}' if n > 0 else base)
                    break
        except Exception:
            pass

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

