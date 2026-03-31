#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/dashboard.py
Componente Dashboard — KPIs, resumen financiero, cotizaciones programadas.

Uso:
    from ui.dashboard import Dashboard
    self.dashboard = Dashboard(self)          # self = SistemaGestion
    self.dashboard.crear_seccion()            # construye el frame
    self.dashboard.actualizar_dashboard()     # refresca datos
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, date


class Dashboard:
    """
    Componente de UI que encapsula el Dashboard completo.
    Recibe `sistema` (instancia de SistemaGestion) como única dependencia.
    """

    def __init__(self, sistema):
        self.sistema = sistema
        self.cursor  = sistema.cursor
        self.C       = sistema.C

        # Widgets internos — se crean en crear_seccion()
        self._kpi_labels      = {}
        self._mes_labels      = {}
        self._estado_labels   = {}
        self._fin_labels      = {}
        self._fin_periodo     = None
        self._estado_periodo  = None
        self.tree_cot_pendientes = None
        self.tree_margen         = None
        self._top_prod_frame     = None
        self._dash_inner         = None
        self._aten_frame         = None
        self._estado_frame       = None

    def crear_seccion(self):
        sec = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['dashboard'] = sec

        # Toolbar
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], relief='flat', bd=0)
        tb.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self.sistema._toolbar_btn(tb, '🔄 Actualizar', self.actualizar_dashboard)

        # ── Área scrollable ───────────────────────────────────────────────────
        canvas = tk.Canvas(sec, bg=self.C['content_bg'], highlightthickness=0)
        sb = ttk.Scrollbar(sec, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=self.C['content_bg'])
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        def _on_canvas_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        inner.bind('<Configure>', _on_configure)
        canvas.bind('<Configure>', _on_canvas_resize)

        # ── FILA 1: 4 KPI cards (ancho completo) ─────────────────────────────
        kpi_row = tk.Frame(inner, bg=self.C['content_bg'])
        kpi_row.pack(fill='x', padx=12, pady=(10, 4))

        kpi_defs = [
            ('kpi_prog',   '📋 Programadas',      '0',  '#c0392b'),
            ('kpi_pend',   '⏳ Sin Programar',     '0',  '#d97706'),
            ('kpi_cobrar', '💵 Por Cobrar',        '$0', '#1a4b8c'),
            ('kpi_stock',  '⚠ Bajo Stock Mín.',   '0',  '#0f7b5e'),
        ]
        self._kpi_labels = {}
        for i, (attr, label, val, color) in enumerate(kpi_defs):
            card = tk.Frame(kpi_row, bg='white', relief='flat', bd=0,
                            highlightbackground='#dde3ed', highlightthickness=1)
            card.grid(row=0, column=i, sticky='nsew', padx=5, pady=2)
            kpi_row.grid_columnconfigure(i, weight=1)
            tk.Frame(card, bg=color, height=4).pack(fill='x')
            tk.Label(card, text=label, font=('Arial', 8),
                     bg='white', fg='#6b7e99').pack(anchor='w', padx=12, pady=(8, 0))
            lbl = tk.Label(card, text=val, font=('Arial', 20, 'bold'),
                           bg='white', fg=color)
            lbl.pack(anchor='w', padx=12, pady=(2, 10))
            self._kpi_labels[attr] = lbl
            _tips = {
                'kpi_prog':   'Cotizaciones programadas o con entrega parcial pendiente',
                'kpi_pend':   'Cotizaciones en estado Pendiente — sin fecha de entrega',
                'kpi_cobrar': 'Saldo pendiente de pago de cotizaciones activas',
                'kpi_stock':  'Productos con stock ≤ stock mínimo configurado',
            }
            if attr in _tips:
                self.sistema._tip(card, _tips[attr])

        # ── FILA 2: izquierda (60%) + derecha (40%) ───────────────────────────
        main_row = tk.Frame(inner, bg=self.C['content_bg'])
        main_row.pack(fill='both', expand=True, padx=12, pady=4)
        main_row.grid_columnconfigure(0, weight=6)
        main_row.grid_columnconfigure(1, weight=4)
        main_row.grid_rowconfigure(1, weight=1)

        # ════════════════ COLUMNA IZQUIERDA ══════════════════════════════════

        # ── L1: Resumen Financiero ─────────────────────────────────────────
        frame_fin = tk.LabelFrame(main_row,
            text='  💰  Resumen Financiero  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg=self.C['text_dark'], relief='flat', bd=1)
        frame_fin.grid(row=0, column=0, sticky='ew', padx=(0, 6), pady=(0, 6))

        # Selector de temporalidad
        ctrl_row = tk.Frame(frame_fin, bg=self.C['content_bg'])
        ctrl_row.pack(fill='x', padx=8, pady=(6, 2))
        tk.Label(ctrl_row, text='Período:', font=('Arial', 9, 'bold'),
                 bg=self.C['content_bg']).pack(side='left', padx=(0, 6))
        self._fin_periodo = ttk.Combobox(ctrl_row, values=[
            'Este mes', 'Últimos 3 meses', 'Últimos 6 meses',
            'Este año', 'Año anterior', 'Todo el tiempo'
        ], state='readonly', width=18, font=('Arial', 9))
        self._fin_periodo.set('Este año')
        self._fin_periodo.pack(side='left')
        self._fin_periodo.bind('<<ComboboxSelected>>',
                               lambda e: self._actualizar_resumen_financiero())

        # Grid 2 filas × 4 columnas de métricas
        metricas_frame = tk.Frame(frame_fin, bg=self.C['content_bg'])
        metricas_frame.pack(fill='x', padx=8, pady=6)
        for i in range(4):
            metricas_frame.grid_columnconfigure(i, weight=1)

        fin_defs = [
            ('fin_entregado',  '📦 Monto Entregado Neto',       '#1a4b8c', '#dbeafe'),
            ('fin_u_esperada', '🎯 Utilidad Esperada',           '#d97706', '#fef3c7'),
            ('fin_u_real',     '✅ Utilidad Real',               '#166534', '#dcfce7'),
            ('fin_costo_pres', '📋 Costo Directo Presupuestado', '#7c3aed', '#ede9fe'),
            ('fin_costo_real', '🛒 Costo Directo Real',          '#dc2626', '#fee2e2'),
            ('fin_ahorro',     '💡 Ahorro en Compras',           '#0e7490', '#cffafe'),
            ('fin_u_diff',     '📊 U. Real vs U. Esperada',      '#6b21a8', '#f3e8ff'),
        ]
        self._fin_labels = {}
        for i, (key, label, fg, bg) in enumerate(fin_defs):
            col = i % 4
            row = i // 4
            cell = tk.Frame(metricas_frame, bg=bg, padx=10, pady=8,
                            highlightbackground='#dde3ed', highlightthickness=1)
            cell.grid(row=row, column=col, sticky='nsew', padx=3, pady=3)
            tk.Label(cell, text=label, font=('Arial', 7, 'bold'),
                     bg=bg, fg=fg, wraplength=130, justify='left').pack(anchor='w')
            lbl = tk.Label(cell, text='$0', font=('Arial', 12, 'bold'), bg=bg, fg=fg)
            lbl.pack(anchor='w', pady=(2, 0))
            self._fin_labels[key] = lbl

        # ── L2: Cotizaciones programadas ───────────────────────────────────
        frame_cot = tk.LabelFrame(main_row,
            text='  📋  Cotizaciones Programadas / Parcialmente Entregadas  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg=self.C['text_dark'], relief='flat', bd=1)
        frame_cot.grid(row=1, column=0, sticky='nsew', padx=(0, 6))

        cols_prog = ('Folio', 'Cliente', 'Monto', 'Productos', 'Días')
        self.tree_cot_pendientes = ttk.Treeview(
            frame_cot, columns=cols_prog, show='headings', height=10)
        wcfg = {'Folio': 120, 'Cliente': 190, 'Monto': 90,
                'Productos': 230, 'Días': 60}
        for col in cols_prog:
            self.tree_cot_pendientes.heading(col, text=col)
            anchor = 'e' if col in ('Monto', 'Días') else 'w'
            self.tree_cot_pendientes.column(col, width=wcfg[col], anchor=anchor)

        self.tree_cot_pendientes.tag_configure('urgente',  background='#fde8e8', foreground='#c0392b')
        self.tree_cot_pendientes.tag_configure('proximo',  background='#fff3cd', foreground='#856404')
        self.tree_cot_pendientes.tag_configure('ok',       background='#d4edda', foreground='#1a6b3a')
        self.tree_cot_pendientes.tag_configure('sin_fecha',foreground='#6b7e99')

        sc = ttk.Scrollbar(frame_cot, orient='vertical',
                           command=self.tree_cot_pendientes.yview)
        self.tree_cot_pendientes.configure(yscrollcommand=sc.set)
        self.tree_cot_pendientes.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        sc.pack(side='right', fill='y', pady=6)

        leyenda = tk.Frame(frame_cot, bg=self.C['content_bg'])
        leyenda.pack(fill='x', padx=6, pady=(0, 4))
        for txt, bg, fg in [('≤3 días', '#fde8e8', '#c0392b'),
                             ('4-7 días', '#fff3cd', '#856404'),
                             ('>7 días', '#d4edda', '#1a6b3a')]:
            lf = tk.Frame(leyenda, bg=bg, padx=6, pady=1)
            lf.pack(side='left', padx=3)
            tk.Label(lf, text=txt, font=('Arial', 7), bg=bg, fg=fg).pack()

        # ════════════════ COLUMNA DERECHA ══════════════════════════════════════
        right_col = tk.Frame(main_row, bg=self.C['content_bg'])
        right_col.grid(row=0, column=1, rowspan=2, sticky='nsew')

        # ── R1: Mes Actual ────────────────────────────────────────────────
        frame_mes = tk.LabelFrame(right_col,
            text='  📅  Mes Actual  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg=self.C['text_dark'], relief='flat', bd=1)
        frame_mes.pack(fill='x', pady=(0, 6))

        mes_defs = [
            ('lbl_mes_entregado', 'Entregado',  '#1a6b3a'),
            ('lbl_mes_facturado', 'Facturado',  '#1a4b8c'),
            ('lbl_mes_pagado',    'Pagado',      '#8e44ad'),
        ]
        self._mes_labels = {}
        row_mes = tk.Frame(frame_mes, bg=self.C['content_bg'])
        row_mes.pack(fill='x', padx=8, pady=6)
        for i, (attr, label, color) in enumerate(mes_defs):
            cell = tk.Frame(row_mes, bg='white',
                            highlightbackground='#dde3ed', highlightthickness=1)
            cell.grid(row=0, column=i, sticky='ew', padx=3)
            row_mes.grid_columnconfigure(i, weight=1)
            tk.Label(cell, text=label, font=('Arial', 7),
                     bg='white', fg='#6b7e99').pack(anchor='w', padx=6, pady=(4, 0))
            lbl = tk.Label(cell, text='$0', font=('Arial', 11, 'bold'),
                           bg='white', fg=color)
            lbl.pack(anchor='w', padx=6, pady=(0, 4))
            self._mes_labels[attr] = lbl

        # ── R2: Cotizaciones por Estado ───────────────────────────────────
        frame_estado = tk.LabelFrame(right_col,
            text='  📊  Cotizaciones por Estado  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg=self.C['text_dark'], relief='flat', bd=1)
        frame_estado.pack(fill='x', pady=(0, 6))

        def _darken(hex_color):
            try:
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                return f'#{int(r*0.88):02x}{int(g*0.88):02x}{int(b*0.88):02x}'
            except Exception:
                return hex_color

        ctrl_est = tk.Frame(frame_estado, bg=self.C['content_bg'])
        ctrl_est.pack(fill='x', padx=8, pady=(4, 0))
        tk.Label(ctrl_est, text='Período:',
                 font=('Arial', 8), bg=self.C['content_bg'],
                 fg=self.C['text_muted']).pack(side='left', padx=(0, 4))
        self._estado_periodo = ttk.Combobox(ctrl_est, values=[
            'Último mes', 'Últimos 3 meses', 'Este año', 'Todo el tiempo'
        ], state='readonly', width=15, font=('Arial', 8))
        self._estado_periodo.set('Último mes')
        self._estado_periodo.pack(side='left')
        self._estado_periodo.bind('<<ComboboxSelected>>',
                                  lambda e: self.actualizar_dashboard())

        self._estado_frame = tk.Frame(frame_estado, bg=self.C['content_bg'])
        self._estado_frame.pack(fill='x', padx=8, pady=6)

        estados_cfg = [
            ('Pendiente',              '#d97706', '#fff3cd'),
            ('Programada',             '#1a4b8c', '#dbeafe'),
            ('Parcialmente Entregada', '#7c3aed', '#ede9fe'),
            ('Entregada',              '#1a6b3a', '#d4edda'),
            ('Cancelada',              '#6b7e99', '#f1f5f9'),
        ]
        self._estado_labels = {}
        for i, (estado, fg, bg) in enumerate(estados_cfg):
            row_e = i // 2
            col_e = i % 2
            cell = tk.Frame(self._estado_frame, bg=bg, padx=8, pady=4,
                            cursor='hand2')
            cell.grid(row=row_e, column=col_e, sticky='ew', padx=3, pady=2)
            self._estado_frame.grid_columnconfigure(col_e, weight=1)
            lbl_n = tk.Label(cell, text='0', font=('Arial', 14, 'bold'),
                             bg=bg, fg=fg, cursor='hand2')
            lbl_n.pack(side='left')
            lbl_txt = tk.Label(cell, text=f'  {estado}', font=('Arial', 8),
                                bg=bg, fg=fg, cursor='hand2')
            lbl_txt.pack(side='left')
            self._estado_labels[estado] = lbl_n
            def _ir_estado(e=None, _est=estado):
                if hasattr(self.sistema, 'cotizaciones_ui') and self.sistema.cotizaciones_ui._filtro_estado_cot:
                    self.sistema.cotizaciones_ui._filtro_estado_cot.set(_est)
                self.sistema._navegar('cotizaciones')
            bg_dark = _darken(bg)
            for widget in (cell, lbl_n, lbl_txt):
                widget.bind('<Button-1>', _ir_estado)
                widget.bind('<Enter>', lambda e, w=cell, c=bg_dark: w.config(bg=c))
                widget.bind('<Leave>', lambda e, w=cell, c=bg: w.config(bg=c))

        # ── R3: Margen por Cotización ─────────────────────────────────────
        frame_margen = tk.LabelFrame(right_col,
            text='  📈  Margen por Cotización (últimas entregadas)  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg=self.C['text_dark'], relief='flat', bd=1)
        frame_margen.pack(fill='x', pady=(0, 6))

        cols_m = ('Folio', 'Venta', 'Costo', 'Margen %')
        self.tree_margen = ttk.Treeview(frame_margen, columns=cols_m,
                                        show='headings', height=5)
        for col in cols_m:
            anchor = 'e' if col != 'Folio' else 'w'
            self.tree_margen.heading(col, text=col)
            self.tree_margen.column(col,
                width={'Folio': 110, 'Venta': 80, 'Costo': 80, 'Margen %': 70}[col],
                anchor=anchor)
        self.tree_margen.tag_configure('bueno',  foreground='#1a6b3a')
        self.tree_margen.tag_configure('medio',  foreground='#856404')
        self.tree_margen.tag_configure('bajo',   foreground='#c0392b')
        self.tree_margen.pack(fill='x', padx=6, pady=6)

        # ── R4: Top Productos ─────────────────────────────────────────────
        frame_top = tk.LabelFrame(right_col,
            text='  🏆  Top Productos Vendidos (mes actual)  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg=self.C['text_dark'], relief='flat', bd=1)
        frame_top.pack(fill='x', pady=(0, 6))

        self._top_prod_frame = tk.Frame(frame_top, bg=self.C['content_bg'])
        self._top_prod_frame.pack(fill='x', padx=8, pady=6)

        # ── R5: Requieren atención ───────────────────────────────────
        frame_aten = tk.LabelFrame(right_col,
            text='  ⚠  Requieren atención  ',
            font=('Arial', 9, 'bold'), bg=self.C['content_bg'],
            fg='#92400e', relief='flat', bd=1)
        frame_aten.pack(fill='x', pady=(0, 6))
        self._aten_frame = tk.Frame(frame_aten, bg=self.C['content_bg'])
        self._aten_frame.pack(fill='x', padx=8, pady=6)

        # Guardar referencia al inner para el scrollable
        self._dash_inner = inner

        # ── ACTUALIZAR DASHBOARD ──────────────────────────────────────────────────
    def actualizar_dashboard(self):
        """Actualiza todos los widgets del dashboard."""
        from datetime import datetime, date
        import calendar

        hoy = date.today()
        primer_dia_mes = hoy.replace(day=1).isoformat()

        # ── KPI 1: Programadas sin entregar ──────────────────────────────────
        self.cursor.execute("""
            SELECT COUNT(*) FROM cotizaciones
            WHERE estado IN ('Programada', 'Parcialmente Entregada')
        """)
        self._kpi_labels['kpi_prog'].config(text=str(self.cursor.fetchone()[0]))

        # ── KPI 2: Sin programar ──────────────────────────────────────────────
        self.cursor.execute("""
            SELECT COUNT(*) FROM cotizaciones WHERE estado = 'Pendiente'
        """)
        self._kpi_labels['kpi_pend'].config(text=str(self.cursor.fetchone()[0]))

        # ── KPI 3: Por cobrar ─────────────────────────────────────────────────
        # Incluye todo estado excepto Cancelada y Pendiente.
        # Se excluye solo cuando la etapa 'Pagada' en seguimiento esté completada.
        self.cursor.execute("""
            SELECT COALESCE(SUM(total - monto_pagado), 0)
            FROM cotizaciones c
            WHERE c.estado NOT IN ('Cancelada', 'Pendiente')
            AND NOT EXISTS (
                SELECT 1 FROM seguimiento_etapas se
                WHERE se.cotizacion_id = c.id
                  AND se.etapa = 'Pagada'
                  AND se.completada = 1
            )
        """)
        monto = self.cursor.fetchone()[0] or 0
        self._kpi_labels['kpi_cobrar'].config(text=f'${monto:,.0f}')

        # ── KPI 4: Bajo stock ─────────────────────────────────────────────────
        self.cursor.execute("""
            SELECT COUNT(*) FROM productos
            WHERE stock_actual <= stock_minimo AND stock_minimo > 0
        """)
        self._kpi_labels['kpi_stock'].config(text=str(self.cursor.fetchone()[0]))

        # ── Cotizaciones programadas con productos pendientes ─────────────────
        self.tree_cot_pendientes.delete(*self.tree_cot_pendientes.get_children())
        self.cursor.execute("""
            SELECT
                c.folio,
                cl.nombre_comercial,
                c.total,
                c.fecha_entrega,
                GROUP_CONCAT(
                    p.nombre || ' x' || CAST(
                        CAST(cd.cantidad AS INTEGER) AS TEXT),
                    ' | '
                ) AS productos
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            JOIN productos p ON p.id = cd.producto_id
            WHERE c.estado IN ('Programada', 'Parcialmente Entregada')
            GROUP BY c.id, c.folio, cl.nombre_comercial, c.total, c.fecha_entrega
            ORDER BY c.fecha_entrega ASC NULLS LAST, c.folio
        """)
        for folio, cliente, total, fecha_entrega, prods in self.cursor.fetchall():
            # Calcular días restantes
            if fecha_entrega:
                try:
                    fe = date.fromisoformat(str(fecha_entrega)[:10])
                    dias = (fe - hoy).days
                    dias_txt = f'{dias}d'
                    tag = 'urgente' if dias <= 3 else ('proximo' if dias <= 7 else 'ok')
                except Exception:
                    dias_txt = '—'
                    tag = 'sin_fecha'
            else:
                dias_txt = '—'
                tag = 'sin_fecha'

            prods_str = prods or '—'
            if len(prods_str) > 55:
                prods_str = prods_str[:52] + '…'

            self.tree_cot_pendientes.insert('', 'end', tags=(tag,), values=(
                folio, cliente, f'${total:,.0f}', prods_str, dias_txt))

        # ── Mes actual: Entregado / Facturado / Pagado ────────────────────────
        self.cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN c.estado IN ('Entregada','Facturada','Pagada',
                             'Parcialmente Entregada')
                             THEN c.total ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN EXISTS (
                    SELECT 1 FROM seguimiento_etapas se
                    WHERE se.cotizacion_id = c.id AND se.etapa = 'Facturada'
                    AND se.completada = 1)
                             THEN c.total ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN c.monto_pagado > 0
                             THEN c.monto_pagado ELSE 0 END), 0)
            FROM cotizaciones c
            WHERE c.fecha >= ?
        """, (primer_dia_mes,))
        ent, fac, pag = self.cursor.fetchone()
        self._mes_labels['lbl_mes_entregado'].config(text=f'${ent:,.0f}')
        self._mes_labels['lbl_mes_facturado'].config(text=f'${fac:,.0f}')
        self._mes_labels['lbl_mes_pagado'].config(text=f'${pag:,.0f}')

        # ── Cotizaciones por estado ───────────────────────────────────────────
        from datetime import date, timedelta
        _hoy = date.today()
        _periodo = getattr(self, '_estado_periodo', None)
        _periodo = _periodo.get() if _periodo else 'Último mes'
        if _periodo == 'Último mes':
            _desde = (_hoy - timedelta(days=30)).isoformat()
        elif _periodo == 'Últimos 3 meses':
            _desde = (_hoy - timedelta(days=90)).isoformat()
        elif _periodo == 'Este año':
            _desde = _hoy.replace(month=1, day=1).isoformat()
        else:
            _desde = '2000-01-01'
        self.cursor.execute("""
            SELECT estado, COUNT(*) FROM cotizaciones
            WHERE fecha >= ? GROUP BY estado
        """, (_desde,))
        conteos = dict(self.cursor.fetchall())
        for estado, lbl in self._estado_labels.items():
            lbl.config(text=str(conteos.get(estado, 0)))

        # ── Margen % por cotización (últimas 8 entregadas) ────────────────────
        self.tree_margen.delete(*self.tree_margen.get_children())
        self.cursor.execute("""
            SELECT
                c.folio,
                c.total AS venta,
                COALESCE(SUM(cd.costo_snapshot * cd.cantidad), 0) AS costo_est
            FROM cotizaciones c
            JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
            WHERE c.estado IN ('Entregada', 'Facturada', 'Pagada')
            GROUP BY c.id, c.folio, c.total, c.fecha
            ORDER BY c.fecha DESC
            LIMIT 8
        """)
        for folio, venta, costo in self.cursor.fetchall():
            if venta > 0 and costo > 0:
                margen = ((venta - costo) / venta) * 100
                tag_m = 'bueno' if margen >= 30 else ('medio' if margen >= 15 else 'bajo')
            elif venta > 0:
                margen = 0.0
                tag_m = 'bajo'
            else:
                continue
            self.tree_margen.insert('', 'end', tags=(tag_m,), values=(
                folio,
                f'${venta:,.0f}',
                f'${costo:,.0f}',
                f'{margen:.1f}%'
            ))

        # ── Resumen financiero ───────────────────────────────────────────────
        self._actualizar_resumen_financiero()

        # ── Top 5 productos vendidos mes actual ───────────────────────────────
        for w in self._top_prod_frame.winfo_children():
            w.destroy()

        self.cursor.execute("""
            SELECT p.nombre, SUM(cd.cantidad) AS total_cant
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            JOIN cotizaciones c ON c.id = cd.cotizacion_id
            WHERE c.fecha >= ?
              AND c.estado IN ('Entregada', 'Facturada', 'Pagada',
                               'Programada', 'Parcialmente Entregada')
            GROUP BY p.id
            ORDER BY total_cant DESC
            LIMIT 5
        """, (primer_dia_mes,))
        top_rows = self.cursor.fetchall()

        if not top_rows:
            tk.Label(self._top_prod_frame, text='Sin datos este mes',
                     font=('Arial', 8), bg=self.C['content_bg'],
                     fg=self.C['text_muted']).pack()
        else:
            max_cant = top_rows[0][1] if top_rows else 1
            colores = ['#1a4b8c', '#1a6b3a', '#8e44ad', '#d97706', '#0e7490']
            for i, (nombre, cant) in enumerate(top_rows):
                fila = tk.Frame(self._top_prod_frame, bg=self.C['content_bg'])
                fila.pack(fill='x', pady=1)

                # Número
                tk.Label(fila, text=f'{i+1}.',
                         font=('Arial', 8, 'bold'), width=2,
                         bg=self.C['content_bg'], fg=colores[i]).pack(side='left')

                # Nombre truncado
                nombre_corto = nombre[:28] + '…' if len(nombre) > 28 else nombre
                tk.Label(fila, text=nombre_corto, font=('Arial', 8),
                         bg=self.C['content_bg'], width=30,
                         anchor='w').pack(side='left', padx=(2, 6))

                # Barra proporcional
                pct = int((cant / max_cant) * 80)
                barra_outer = tk.Frame(fila, bg='#e8ecf2', height=14, width=80)
                barra_outer.pack(side='left')
                barra_outer.pack_propagate(False)
                tk.Frame(barra_outer, bg=colores[i],
                         height=14, width=max(4, pct)).pack(side='left')

                # Cantidad
                tk.Label(fila, text=f'{cant:g}',
                         font=('Arial', 8, 'bold'),
                         bg=self.C['content_bg'], fg=colores[i]).pack(side='left', padx=4)

        # ── Sección Atención: cotizaciones urgentes ─────────────────────────────
        self._actualizar_seccion_atencion(hoy)

    def _actualizar_seccion_atencion(self, hoy):
        """Llena la sección 'Requieren atención' con cotizaciones urgentes."""
        if not hasattr(self, '_aten_frame'):
            return
        for w in self._aten_frame.winfo_children():
            w.destroy()

        self.cursor.execute("""
            SELECT c.folio, cl.nombre_comercial, c.estado,
                   c.fecha, c.fecha_entrega, c.total
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.estado NOT IN ('Cancelada', 'Pagada')
            ORDER BY c.folio DESC
        """)
        urgentes = []
        from datetime import date as _d
        for folio, cliente, estado, fecha, fecha_entrega, total in self.cursor.fetchall():
            try:
                dias = (hoy - _d.fromisoformat(str(fecha)[:10])).days
            except Exception:
                continue
            if estado in ('Pendiente', 'Programada') and dias > 14:
                urgentes.append((folio, cliente[:22], f'{dias}d sin avanzar', '#dc2626'))
            elif estado == 'Entregada':
                try:
                    fe = _d.fromisoformat(str(fecha_entrega or fecha)[:10])
                    dias_e = (hoy - fe).days
                    if dias_e > 3:
                        urgentes.append((folio, cliente[:22], f'{dias_e}d sin facturar', '#d97706'))
                except Exception:
                    pass
            elif estado == 'Facturada' and dias > 30:
                urgentes.append((folio, cliente[:22], f'{dias}d sin pago', '#d97706'))

        if not urgentes:
            tk.Label(self._aten_frame, text='✅  Todo al día',
                     font=('Arial', 8), bg=self.C['content_bg'],
                     fg='#16a34a').pack(anchor='w')
            return

        for folio, cliente, motivo, color in urgentes[:6]:
            r = tk.Frame(self._aten_frame, bg=self.C['content_bg'])
            r.pack(fill='x', pady=1)
            tk.Label(r, text=folio, font=('Arial', 8, 'bold'),
                     bg=self.C['content_bg'], fg=color,
                     width=14, anchor='w').pack(side='left')
            tk.Label(r, text=cliente, font=('Arial', 8),
                     bg=self.C['content_bg'], fg=self.C['text_muted2'],
                     width=22, anchor='w').pack(side='left', padx=(4,0))
            tk.Label(r, text=motivo, font=('Arial', 8, 'bold'),
                     bg=self.C['content_bg'], fg=color).pack(side='right')

        if len(urgentes) > 6:
            tk.Label(self._aten_frame,
                     text=f'... y {len(urgentes)-6} más',
                     font=('Arial', 7, 'italic'), bg=self.C['content_bg'],
                     fg=self.C['text_muted']).pack(anchor='e')

    # (removed - rebuilt in new ERP UI)

    def _actualizar_resumen_financiero(self):
        """Calcula y muestra el resumen financiero según el período seleccionado."""
        from datetime import date, timedelta
        import calendar

        hoy = date.today()
        periodo = self._fin_periodo.get()

        # ── Calcular rango de fechas ──────────────────────────────────────────
        if periodo == 'Este mes':
            fecha_ini = hoy.replace(day=1).isoformat()
            fecha_fin = hoy.isoformat()
        elif periodo == 'Últimos 3 meses':
            fecha_ini = (hoy - timedelta(days=90)).isoformat()
            fecha_fin = hoy.isoformat()
        elif periodo == 'Últimos 6 meses':
            fecha_ini = (hoy - timedelta(days=180)).isoformat()
            fecha_fin = hoy.isoformat()
        elif periodo == 'Este año':
            fecha_ini = hoy.replace(month=1, day=1).isoformat()
            fecha_fin = hoy.isoformat()
        elif periodo == 'Año anterior':
            fecha_ini = hoy.replace(year=hoy.year - 1, month=1, day=1).isoformat()
            fecha_fin = hoy.replace(year=hoy.year - 1, month=12, day=31).isoformat()
        else:  # Todo el tiempo
            fecha_ini = '2000-01-01'
            fecha_fin = '2099-12-31'

        # Estados que confirman entrega (independientemente de si ya se facturó o pagó)
        _estados_entregados = (
            'Entregada', 'Parcialmente Entregada', 'Facturada', 'Pagada'
        )
        _placeholders = ','.join('?' * len(_estados_entregados))

        # ── Monto Entregado Neto (total vendido, con o sin pago) ──────────────
        # Incluye todos los estados post-entrega para no perder cotizaciones
        # que ya avanzaron a Facturada o Pagada.
        self.cursor.execute(f"""
            SELECT COALESCE(SUM(total), 0)
            FROM cotizaciones
            WHERE estado IN ({_placeholders})
              AND fecha BETWEEN ? AND ?
        """, (*_estados_entregados, fecha_ini, fecha_fin))
        monto_entregado = self.cursor.fetchone()[0] or 0

        # ── Costo Directo Presupuestado (precio_base × cantidad cotizada) ─────
        self.cursor.execute(f"""
            SELECT COALESCE(SUM(cd.cantidad * p.precio_base), 0)
            FROM cotizacion_detalle cd
            JOIN cotizaciones c  ON c.id  = cd.cotizacion_id
            JOIN productos p     ON p.id  = cd.producto_id
            WHERE c.estado IN ({_placeholders})
              AND c.fecha BETWEEN ? AND ?
        """, (*_estados_entregados, fecha_ini, fecha_fin))
        costo_presupuestado = self.cursor.fetchone()[0] or 0

        # ── Utilidad Esperada = Venta - Costo Presupuestado ───────────────────
        u_esperada = monto_entregado - costo_presupuestado

        # ── Costo Directo Real (costo al momento de cotizar × cantidad) ──────
        self.cursor.execute(f"""
            SELECT COALESCE(SUM(cd.costo_snapshot * cd.cantidad), 0)
            FROM cotizacion_detalle cd
            JOIN cotizaciones c ON c.id = cd.cotizacion_id
            WHERE c.estado IN ({_placeholders})
              AND c.fecha BETWEEN ? AND ?
        """, (*_estados_entregados, fecha_ini, fecha_fin))
        costo_real = self.cursor.fetchone()[0] or 0

        # ── Utilidad Real = Venta - Costo Real ───────────────────────────────
        u_real = monto_entregado - costo_real

        # ── Ahorro = Costo Presupuestado - Costo Real ─────────────────────────
        ahorro = costo_presupuestado - costo_real

        # ── Diferencia U Real vs U Esperada ───────────────────────────────────
        u_diff = u_real - u_esperada

        # ── Actualizar labels ─────────────────────────────────────────────────
        def fmt(v):
            signo = '-' if v < 0 else ''
            return f'{signo}${abs(v):,.2f}'

        self._fin_labels['fin_entregado'].config(text=fmt(monto_entregado))
        self._fin_labels['fin_costo_pres'].config(text=fmt(costo_presupuestado))
        self._fin_labels['fin_u_esperada'].config(text=fmt(u_esperada))
        self._fin_labels['fin_costo_real'].config(text=fmt(costo_real))
        self._fin_labels['fin_u_real'].config(text=fmt(u_real))
        self._fin_labels['fin_ahorro'].config(text=fmt(ahorro))
        self._fin_labels['fin_u_diff'].config(text=fmt(u_diff))



