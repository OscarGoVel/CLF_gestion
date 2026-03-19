#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estado de Cuenta de Pedidos — CLF Yucateca
Muestra el estatus completo de cada cotización:
  entrega, fecha, valor, O.C., factura, pago.
Permite generar un reporte PDF.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime


# ── Paleta de colores ──────────────────────────────────────────────────────────
C = {
    'header_bg':  '#1e2d45',
    'header_fg':  'white',
    'toolbar_bg': '#d8dde8',
    'content_bg': '#eceff4',
    'card_bg':    'white',
    'accent':     '#0f7b5e',
    'accent2':    '#1a4b8c',
    'warn':       '#d97706',
    'danger':     '#c0392b',
    'text_dark':  '#1e2d45',
    'text_muted': '#6b7e99',
}

# Tags de color por estado
ESTADO_COLORS = {
    'Pendiente':              '#fff3cd',
    'Programada':             '#cce5ff',
    'Parcialmente Entregada': '#e8d5ff',
    'Entregada':              '#d4edda',
    'Facturada':              '#cffafe',
    'Pagada':                 '#bbf7d0',
    'Cancelada':              '#f1f5f9',
}

# Íconos de estado para PDF/tabla
ESTADO_ICONS = {
    'Pendiente':              '⏳',
    'Programada':             '📅',
    'Parcialmente Entregada': '📦',
    'Entregada':              '✅',
    'Facturada':              '🧾',
    'Pagada':                 '💰',
    'Cancelada':              '❌',
}


class VentanaEstadoCuenta:
    """
    Ventana principal de Estado de Cuenta de Pedidos.
    Puede abrirse de forma standalone o como modal desde SistemaGestion.
    """

    def __init__(self, parent, conn, cursor):
        self.parent = parent
        self.conn   = conn
        self.cursor = cursor

        self.win = tk.Toplevel(parent)
        self.win.title("📊 Estado de Cuenta de Pedidos — CLF Yucateca")
        self.win.geometry("1280x720")
        self.win.configure(bg=C['content_bg'])
        self.win.transient(parent)
        self.win.grab_set()

        self._init_corporativos()
        self._build_ui()
        self._cargar_corporativos_combo()
        self._cargar_clientes_combo()
        self.cargar_datos()

    # ── Construcción de interfaz ───────────────────────────────────────────────

    def _build_ui(self):
        # ── Encabezado ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self.win, bg=C['header_bg'], pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text="📊  Estado de Cuenta de Pedidos",
                 font=('Arial', 13, 'bold'), bg=C['header_bg'],
                 fg='white').pack(side='left', padx=18)
        tk.Label(hdr,
                 text="Comercializadora, Logística y Fuerza Yucateca",
                 font=('Arial', 9), bg=C['header_bg'],
                 fg='#94a3b8').pack(side='right', padx=18)

        # ── Filtros ─────────────────────────────────────────────────────────────
        ff = tk.Frame(self.win, bg=C['toolbar_bg'], pady=6)
        ff.pack(fill='x')
        tk.Frame(self.win, bg='#c5ccd8', height=1).pack(fill='x')

        def lbl(txt):
            tk.Label(ff, text=txt, font=('Arial', 9),
                     bg=C['toolbar_bg']).pack(side='left', padx=(10, 2))

        # Corporativo
        lbl('Corporativo:')
        self._var_corp = tk.StringVar(value='Todos')
        self._combo_corp = ttk.Combobox(ff, textvariable=self._var_corp,
                                        state='readonly', width=20,
                                        font=('Arial', 9))
        self._combo_corp.pack(side='left', padx=4)
        self._combo_corp.bind('<<ComboboxSelected>>', self._on_corp_change)

        tk.Button(ff, text='⚙️', font=('Arial', 9), cursor='hand2',
                  bg=C['toolbar_bg'], relief='flat', padx=4, pady=2,
                  command=self._gestionar_corporativos).pack(side='left', padx=(0, 6))

        # Cliente
        lbl('Cliente:')
        self._var_cliente = tk.StringVar(value='Todos')
        self._combo_cliente = ttk.Combobox(ff, textvariable=self._var_cliente,
                                           state='readonly', width=24,
                                           font=('Arial', 9))
        self._combo_cliente.pack(side='left', padx=4)
        self._combo_cliente.bind('<<ComboboxSelected>>', lambda e: self.cargar_datos())

        # Fecha desde
        lbl('Desde:')
        self._entry_desde = tk.Entry(ff, font=('Arial', 9), width=11)
        self._entry_desde.pack(side='left', padx=4)
        self._entry_desde.bind('<Return>', lambda e: self.cargar_datos())

        # Fecha hasta
        lbl('Hasta:')
        self._entry_hasta = tk.Entry(ff, font=('Arial', 9), width=11)
        self._entry_hasta.pack(side='left', padx=4)
        self._entry_hasta.bind('<Return>', lambda e: self.cargar_datos())

        # Rellenar fechas por defecto (año en curso)
        hoy = datetime.now()
        self._entry_desde.insert(0, f"{hoy.year}-01-01")
        self._entry_hasta.insert(0, hoy.strftime('%Y-%m-%d'))

        # Estado
        lbl('Estado:')
        self._var_estado = tk.StringVar(value='Todos')
        self._combo_estado = ttk.Combobox(
            ff, textvariable=self._var_estado,
            values=['Todos', 'Pendiente', 'Programada', 'Parcialmente Entregada',
                    'Entregada', 'Facturada', 'Pagada', 'Cancelada'],
            state='readonly', width=22, font=('Arial', 9))
        self._combo_estado.pack(side='left', padx=4)
        self._combo_estado.bind('<<ComboboxSelected>>', lambda e: self.cargar_datos())

        # Botones
        tk.Button(ff, text='🔍 Buscar', command=self.cargar_datos,
                  font=('Arial', 9), bg=C['accent2'], fg='white',
                  cursor='hand2', relief='raised', padx=8, pady=3
                  ).pack(side='left', padx=(10, 2))

        tk.Button(ff, text='📄 Generar PDF', command=self.generar_pdf,
                  font=('Arial', 9, 'bold'), bg=C['accent'], fg='white',
                  cursor='hand2', relief='raised', padx=8, pady=3
                  ).pack(side='left', padx=2)

        tk.Button(ff, text='📊 Exportar Excel', command=self.exportar_excel,
                  font=('Arial', 9, 'bold'), bg='#166534', fg='white',
                  cursor='hand2', relief='raised', padx=8, pady=3
                  ).pack(side='left', padx=2)

        tk.Button(ff, text='❌ Cerrar', command=self.win.destroy,
                  font=('Arial', 9), bg=C['danger'], fg='white',
                  cursor='hand2', relief='raised', padx=8, pady=3
                  ).pack(side='right', padx=10)

        # ── Tabla principal ──────────────────────────────────────────────────────
        ft = tk.Frame(self.win, bg=C['content_bg'])
        ft.pack(fill='both', expand=True, padx=8, pady=8)

        cols = ('ID', 'Folio', 'Fecha', 'Cliente',
                'Total', 'Estado',
                'Fecha Entrega', 'Monto Entregado',
                'Orden Compra', 'Fecha O.C.',
                'N° Factura', 'Fecha Factura',
                'Monto Facturado',
                'Fecha Pago', 'Monto Pagado',
                'Saldo Pendiente')

        self.tree = ttk.Treeview(ft, columns=cols, show='headings',
                                 selectmode='browse')

        # Anchos de columna
        anchos = {
            'ID': 0, 'Folio': 110, 'Fecha': 86, 'Cliente': 175,
            'Total': 90, 'Estado': 145,
            'Fecha Entrega': 95, 'Monto Entregado': 100,
            'Orden Compra': 115, 'Fecha O.C.': 90,
            'N° Factura': 115, 'Fecha Factura': 90,
            'Monto Facturado': 100,
            'Fecha Pago': 90, 'Monto Pagado': 90,
            'Saldo Pendiente': 100,
        }
        for col in cols:
            self.tree.heading(col, text='' if col == 'ID' else col)
            self.tree.column(col, width=anchos[col], minwidth=anchos[col],
                             stretch=(col not in ('ID',)))
        self.tree.column('ID', stretch=False)

        # Colores por estado
        for estado, bg in ESTADO_COLORS.items():
            self.tree.tag_configure(estado, background=bg)

        sc_y = ttk.Scrollbar(ft, orient='vertical',   command=self.tree.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        # ── Barra de totales ─────────────────────────────────────────────────────
        self._frame_totales = tk.Frame(self.win, bg=C['header_bg'], pady=6)
        self._frame_totales.pack(fill='x')
        self._lbl_totales = tk.Label(
            self._frame_totales, text='',
            font=('Arial', 9), bg=C['header_bg'], fg='#94a3b8')
        self._lbl_totales.pack(side='left', padx=16)

    # ── Datos ──────────────────────────────────────────────────────────────────

    def _init_corporativos(self):
        """Crea tabla corporativos si no existe (ya debería existir por main.py)."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS corporativos (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE
            )
        ''')
        try:
            self.cursor.execute('ALTER TABLE clientes ADD COLUMN corporativo_id INTEGER')
        except Exception:
            pass
        self.conn.commit()

    def _cargar_corporativos_combo(self):
        self.cursor.execute("SELECT nombre FROM corporativos ORDER BY nombre")
        nombres = ['Todos'] + [r[0] for r in self.cursor.fetchall()]
        self._combo_corp['values'] = nombres

    def _on_corp_change(self, event=None):
        """Al cambiar corporativo, filtra el combo de clientes."""
        corp = self._var_corp.get()
        if corp and corp != 'Todos':
            self.cursor.execute("""
                SELECT cl.nombre_comercial FROM clientes cl
                JOIN corporativos co ON co.id = cl.corporativo_id
                WHERE co.nombre = ?
                  AND cl.id IN (SELECT DISTINCT cliente_id FROM cotizaciones)
                ORDER BY cl.nombre_comercial
            """, (corp,))
            miembros = [r[0] for r in self.cursor.fetchall()]
            self._combo_cliente['values'] = ['Todos'] + miembros
        else:
            self._cargar_clientes_combo()
        self._var_cliente.set('Todos')
        self.cargar_datos()

    def _cargar_clientes_combo(self, corp_filtro=None):
        self.cursor.execute(
            "SELECT DISTINCT cl.nombre_comercial FROM clientes cl "
            "INNER JOIN cotizaciones c ON cl.id = c.cliente_id "
            "ORDER BY cl.nombre_comercial")
        nombres = ['Todos'] + [r[0] for r in self.cursor.fetchall()]
        self._combo_cliente['values'] = nombres

    def _gestionar_corporativos(self):
        """Ventana para crear/editar corporativos y asignar clientes."""
        win = tk.Toplevel(self.win)
        win.title("⚙️  Gestionar Corporativos")
        win.geometry("700x520")
        win.configure(bg='#f1f5f9')
        win.transient(self.win)
        win.grab_set()
        win.lift()

        # Cabecera
        hdr = tk.Frame(win, bg='#1e2d45', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text="⚙️  Corporativos — Grupos de Clientes",
                 font=('Arial', 11, 'bold'), bg='#1e2d45', fg='white').pack(side='left', padx=12)

        body = tk.Frame(win, bg='#f1f5f9')
        body.pack(fill='both', expand=True, padx=12, pady=8)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(2, weight=2)
        body.grid_rowconfigure(1, weight=1)

        # ── Panel izquierdo: lista de corporativos ─────────────────────────
        tk.Label(body, text="Corporativos", font=('Arial', 9, 'bold'),
                 bg='#f1f5f9', fg='#1e2d45').grid(row=0, column=0, sticky='w', pady=(0,2))

        lf = tk.Frame(body, bg='#f1f5f9')
        lf.grid(row=1, column=0, sticky='nsew')
        lf.grid_rowconfigure(0, weight=1)
        lf.grid_columnconfigure(0, weight=1)

        lb_corp = tk.Listbox(lf, font=('Arial', 9), selectmode='browse',
                              bg='white', activestyle='none',
                              selectbackground='#1e3a5f', selectforeground='white')
        sc_lb = ttk.Scrollbar(lf, orient='vertical', command=lb_corp.yview)
        lb_corp.configure(yscrollcommand=sc_lb.set)
        lb_corp.grid(row=0, column=0, sticky='nsew')
        sc_lb.grid(row=0, column=1, sticky='ns')

        # Botones corporativo
        bf = tk.Frame(body, bg='#f1f5f9')
        bf.grid(row=2, column=0, sticky='ew', pady=4)
        entry_corp_nom = tk.Entry(bf, font=('Arial', 9), width=18)
        entry_corp_nom.pack(side='left', padx=(0,4))

        def _agregar_corp():
            nom = entry_corp_nom.get().strip()
            if not nom:
                return
            try:
                self.cursor.execute("INSERT INTO corporativos (nombre) VALUES (?)", (nom,))
                self.conn.commit()
                entry_corp_nom.delete(0, 'end')
                _reload_corps()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def _eliminar_corp():
            sel = lb_corp.curselection()
            if not sel:
                return
            nom = lb_corp.get(sel[0])
            if messagebox.askyesno("Confirmar",
                    f"¿Eliminar corporativo '{nom}'?\nLos clientes quedarán sin grupo.",
                    parent=win):
                self.cursor.execute(
                    "UPDATE clientes SET corporativo_id=NULL WHERE corporativo_id="
                    "(SELECT id FROM corporativos WHERE nombre=?)", (nom,))
                self.cursor.execute("DELETE FROM corporativos WHERE nombre=?", (nom,))
                self.conn.commit()
                _reload_corps()
                _reload_miembros(None)

        tk.Button(bf, text="➕ Agregar", font=('Arial', 8), cursor='hand2',
                  bg='#0f7b5e', fg='white', padx=6, pady=3, relief='flat',
                  command=_agregar_corp).pack(side='left', padx=2)
        tk.Button(bf, text="🗑 Eliminar", font=('Arial', 8), cursor='hand2',
                  bg='#c0392b', fg='white', padx=6, pady=3, relief='flat',
                  command=_eliminar_corp).pack(side='left', padx=2)

        # ── Separador ─────────────────────────────────────────────────────
        tk.Frame(body, bg='#cbd5e1', width=1).grid(row=0, column=1, rowspan=3,
                                                    sticky='ns', padx=8)

        # ── Panel derecho: clientes del corporativo ────────────────────────
        tk.Label(body, text="Clientes del corporativo seleccionado",
                 font=('Arial', 9, 'bold'), bg='#f1f5f9',
                 fg='#1e2d45').grid(row=0, column=2, sticky='w', pady=(0,2))

        rf = tk.Frame(body, bg='#f1f5f9')
        rf.grid(row=1, column=2, sticky='nsew')
        rf.grid_rowconfigure(0, weight=1)
        rf.grid_rowconfigure(2, weight=1)
        rf.grid_columnconfigure(0, weight=1)

        tk.Label(rf, text="Miembros:", font=('Arial', 8, 'bold'),
                 bg='#f1f5f9', fg='#065f46').grid(row=0, column=0, sticky='nw')
        lb_miem = tk.Listbox(rf, font=('Arial', 9), selectmode='browse',
                              bg='#f0fdf4', activestyle='none', height=6,
                              selectbackground='#065f46', selectforeground='white')
        lb_miem.grid(row=0, column=0, sticky='nsew', pady=(16,2))

        btns_m = tk.Frame(rf, bg='#f1f5f9')
        btns_m.grid(row=1, column=0, sticky='ew', pady=2)

        tk.Label(rf, text="Clientes disponibles (sin grupo):",
                 font=('Arial', 8, 'bold'), bg='#f1f5f9',
                 fg='#1e3a5f').grid(row=2, column=0, sticky='sw', pady=(4,0))
        lb_disp = tk.Listbox(rf, font=('Arial', 9), selectmode='browse',
                              bg='#eff6ff', activestyle='none', height=6,
                              selectbackground='#1e3a5f', selectforeground='white')
        lb_disp.grid(row=2, column=0, sticky='nsew', pady=(16,2))

        btns_d = tk.Frame(rf, bg='#f1f5f9')
        btns_d.grid(row=3, column=0, sticky='ew')

        corp_id_sel = [None]  # mutable ref

        def _reload_corps():
            lb_corp.delete(0, 'end')
            self.cursor.execute("SELECT nombre FROM corporativos ORDER BY nombre")
            for r in self.cursor.fetchall():
                lb_corp.insert('end', r[0])

        def _reload_miembros(corp_id):
            lb_miem.delete(0, 'end')
            lb_disp.delete(0, 'end')
            if corp_id is None:
                return
            # Miembros actuales
            self.cursor.execute(
                "SELECT nombre_comercial FROM clientes WHERE corporativo_id=? ORDER BY nombre_comercial",
                (corp_id,))
            for r in self.cursor.fetchall():
                lb_miem.insert('end', r[0])
            # Disponibles (sin grupo)
            self.cursor.execute(
                "SELECT nombre_comercial FROM clientes WHERE corporativo_id IS NULL ORDER BY nombre_comercial")
            for r in self.cursor.fetchall():
                lb_disp.insert('end', r[0])

        def _on_corp_sel(event):
            sel = lb_corp.curselection()
            if not sel:
                return
            nom = lb_corp.get(sel[0])
            self.cursor.execute("SELECT id FROM corporativos WHERE nombre=?", (nom,))
            row = self.cursor.fetchone()
            if row:
                corp_id_sel[0] = row[0]
                _reload_miembros(row[0])

        lb_corp.bind('<<ListboxSelect>>', _on_corp_sel)

        def _quitar_miembro():
            sel = lb_miem.curselection()
            if not sel or corp_id_sel[0] is None:
                return
            nom = lb_miem.get(sel[0])
            self.cursor.execute(
                "UPDATE clientes SET corporativo_id=NULL WHERE nombre_comercial=?", (nom,))
            self.conn.commit()
            _reload_miembros(corp_id_sel[0])

        def _agregar_miembro():
            sel = lb_disp.curselection()
            if not sel or corp_id_sel[0] is None:
                return
            nom = lb_disp.get(sel[0])
            self.cursor.execute(
                "UPDATE clientes SET corporativo_id=? WHERE nombre_comercial=?",
                (corp_id_sel[0], nom))
            self.conn.commit()
            _reload_miembros(corp_id_sel[0])

        tk.Button(btns_m, text="✖ Quitar del corporativo", font=('Arial', 8),
                  cursor='hand2', bg='#c0392b', fg='white', padx=6, pady=2,
                  relief='flat', command=_quitar_miembro).pack(side='left')
        tk.Button(btns_d, text="✚ Agregar al corporativo", font=('Arial', 8),
                  cursor='hand2', bg='#1e3a5f', fg='white', padx=6, pady=2,
                  relief='flat', command=_agregar_miembro).pack(side='left')

        _reload_corps()

        # Pie
        foot = tk.Frame(win, bg='#e2e8f0', pady=6)
        foot.pack(fill='x', side='bottom')
        tk.Button(foot, text='Cerrar y actualizar', font=('Arial', 9),
                  bg='#1e2d45', fg='white', cursor='hand2', padx=12, pady=4,
                  relief='flat',
                  command=lambda: [win.destroy(),
                                   self._cargar_corporativos_combo(),
                                   self._cargar_clientes_combo()]).pack(side='right', padx=10)

    def cargar_datos(self):
        """Consulta BD y llena la tabla."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        cliente_filtro = self._var_cliente.get()
        corp_filtro    = self._var_corp.get()
        estado_filtro  = self._var_estado.get()
        desde = self._entry_desde.get().strip()
        hasta = self._entry_hasta.get().strip()

        params = []
        where  = []

        # Filtro por corporativo (agrupa todos sus clientes miembros)
        if corp_filtro and corp_filtro != 'Todos':
            if cliente_filtro and cliente_filtro != 'Todos':
                # Corporativo activo + cliente específico dentro de él
                where.append('cl.nombre_comercial = ?')
                params.append(cliente_filtro)
            else:
                # Todos los clientes del corporativo
                where.append(
                    'cl.corporativo_id = (SELECT id FROM corporativos WHERE nombre=?)')
                params.append(corp_filtro)
        elif cliente_filtro and cliente_filtro != 'Todos':
            where.append('cl.nombre_comercial = ?')
            params.append(cliente_filtro)

        if estado_filtro and estado_filtro != 'Todos':
            where.append('c.estado = ?')
            params.append(estado_filtro)

        if desde:
            where.append('c.fecha >= ?')
            params.append(desde)

        if hasta:
            where.append('c.fecha <= ?')
            params.append(hasta)

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        self.cursor.execute(f"""
            SELECT
                c.id,
                c.folio,
                c.fecha,
                cl.nombre_comercial,
                c.total,
                c.estado,
                c.fecha_entrega,
                c.monto_entregado,
                c.orden_compra,
                c.fecha_orden_compra,
                c.numero_factura,
                c.fecha_factura,
                c.monto_facturado,
                c.fecha_pago,
                c.monto_pagado,
                c.entrega_parcial
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            {where_sql}
            ORDER BY c.fecha DESC, c.folio DESC
        """, params)

        rows = self.cursor.fetchall()

        # Obtener referencias de seguimiento para OC y Factura
        if rows:
            ids = [r[0] for r in rows]
            ph  = ','.join('?' * len(ids))
            self.cursor.execute(f"""
                SELECT cotizacion_id, etapa, referencia, fecha_etapa
                FROM seguimiento_etapas
                WHERE cotizacion_id IN ({ph})
                  AND etapa IN ('Orden de Compra', 'Facturada')
            """, ids)
            seg = {}
            for cid, etapa, ref, fec in self.cursor.fetchall():
                seg.setdefault(cid, {})[etapa] = (ref, fec)
        else:
            seg = {}

        total_valor = 0
        total_pagado = 0
        total_saldo  = 0

        for row in rows:
            (cid, folio, fecha, cliente, total, estado,
             fecha_entrega, monto_entregado,
             orden_compra, fecha_oc,
             num_factura, fecha_factura, monto_facturado,
             fecha_pago, monto_pagado,
             entrega_parcial) = row

            s = seg.get(cid, {})

            # O.C.: preferir seguimiento
            oc_ref, oc_fec = s.get('Orden de Compra', (None, None))
            oc_txt  = oc_ref  or orden_compra or ''
            oc_fecha_txt = oc_fec  or fecha_oc    or ''

            # Factura: preferir seguimiento
            fac_ref, fac_fec = s.get('Facturada', (None, None))
            fac_txt  = fac_ref  or num_factura or ''
            fac_fecha_txt = fac_fec or fecha_factura or ''

            # Saldo
            pagado = monto_pagado or 0
            saldo  = (total or 0) - pagado

            # Acumulados
            total_valor  += total or 0
            total_pagado += pagado
            total_saldo  += saldo

            # Estado con ícono
            icono = ESTADO_ICONS.get(estado, '')
            estado_txt = f"{icono} {estado}"

            # Entrega
            if entrega_parcial:
                fe_txt = f"Parcial · {fecha_entrega or 'pendiente'}"
            else:
                fe_txt = fecha_entrega or ('' if estado not in ('Entregada','Pagada','Facturada') else '—')

            values = (
                cid,
                folio,
                fecha or '',
                cliente,
                f'${total:,.2f}' if total else '$0.00',
                estado_txt,
                fe_txt,
                f'${monto_entregado:,.2f}' if monto_entregado else '—',
                oc_txt  or '—',
                oc_fecha_txt or '—',
                fac_txt or '—',
                fac_fecha_txt or '—',
                f'${monto_facturado:,.2f}' if monto_facturado else '—',
                fecha_pago or '—',
                f'${pagado:,.2f}' if pagado else '—',
                f'${saldo:,.2f}',
            )

            tag = estado if estado in ESTADO_COLORS else ''
            self.tree.insert('', 'end', values=values, tags=(tag,))

        # Barra de totales
        n = len(rows)
        self._lbl_totales.config(
            text=(f"  {n} pedido(s)     |     "
                  f"Valor total: ${total_valor:,.2f}     |     "
                  f"Cobrado: ${total_pagado:,.2f}     |     "
                  f"Saldo pendiente: ${total_saldo:,.2f}"))

    # ── Generador de PDF ───────────────────────────────────────────────────────

    def generar_pdf(self):
        """
        Genera PDF de Estado de Cuenta en 3 secciones:
          1. Información del cliente
          2. Resumen del periodo (balance inicial vs final)
          3. Tabla detalle de pendientes de pago
        """
        try:
            from reportlab.lib          import colors as rl_colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units     import inch, mm
            from reportlab.platypus      import (SimpleDocTemplate, Table,
                                                  TableStyle, Paragraph,
                                                  Spacer, HRFlowable,
                                                  KeepTogether)
            from reportlab.lib.styles   import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums    import TA_CENTER, TA_LEFT, TA_RIGHT
        except ImportError:
            messagebox.showerror(
                "Error", "Instala reportlab:\n  pip install reportlab",
                parent=self.win)
            return

        # ── Parámetros del filtro ─────────────────────────────────────────────
        cliente_filtro = self._var_cliente.get()
        corp_filtro    = self._var_corp.get()
        desde  = self._entry_desde.get().strip()
        hasta  = self._entry_hasta.get().strip()

        # Modo corporativo: el combo corporativo está activo y cliente es "Todos"
        modo_corp = (corp_filtro and corp_filtro != 'Todos'
                     and (not cliente_filtro or cliente_filtro == 'Todos'))

        if not modo_corp and (not cliente_filtro or cliente_filtro == 'Todos'):
            messagebox.showwarning(
                "Selecciona destino",
                "Selecciona un cliente específico, o un corporativo completo.",
                parent=self.win)
            return

        # ── Datos del sujeto (cliente individual o corporativo) ───────────────
        corp_nombre = corp_filtro if modo_corp else None

        if modo_corp:
            # Obtener todos los clientes miembros
            self.cursor.execute("""
                SELECT cl.nombre_comercial, cl.razon_social, cl.rfc,
                       cl.contacto, cl.telefono, cl.email,
                       cl.regimen_fiscal, cl.uso_cfdi, cl.cp_fiscal
                FROM clientes cl
                JOIN corporativos co ON co.id = cl.corporativo_id
                WHERE co.nombre = ?
                ORDER BY cl.nombre_comercial
            """, (corp_nombre,))
            miembros = self.cursor.fetchall()
            if not miembros:
                messagebox.showerror("Sin clientes",
                    f"El corporativo '{corp_nombre}' no tiene clientes asignados.",
                    parent=self.win)
                return
            # Para las queries de balance usamos la lista de nombres
            nombres_clientes = [m[0] for m in miembros]
            # Título del documento
            nombre_doc = corp_nombre
        else:
            self.cursor.execute("""
                SELECT nombre_comercial, razon_social, rfc,
                       contacto, telefono, email,
                       regimen_fiscal, uso_cfdi, cp_fiscal
                FROM clientes WHERE nombre_comercial = ? LIMIT 1
            """, (cliente_filtro,))
            cli_row = self.cursor.fetchone()
            if not cli_row:
                messagebox.showerror("Error", "No se encontró la información del cliente.",
                                     parent=self.win)
                return
            miembros = [cli_row]
            nombres_clientes = [cliente_filtro]
            nombre_doc = cliente_filtro

        # ── Elegir destino ────────────────────────────────────────────────────
        ruta = filedialog.asksaveasfilename(
            parent=self.win,
            title="Guardar Estado de Cuenta",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"EstadoCuenta_{nombre_doc.replace(' ','_')}"
                        f"_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        if not ruta:
            return

        # ── Colores corporativos ──────────────────────────────────────────────
        AZL   = rl_colors.HexColor('#1e2d45')
        ORO   = rl_colors.HexColor('#D4AF37')
        VERDE = rl_colors.HexColor('#0f7b5e')
        GRIS  = rl_colors.HexColor('#6b7e99')
        BGCL  = rl_colors.HexColor('#f1f5f9')
        BGVD  = rl_colors.HexColor('#d1fae5')
        BGAM  = rl_colors.HexColor('#fef3c7')
        BGAZ  = rl_colors.HexColor('#dbeafe')
        BLANCO= rl_colors.white

        styles = getSampleStyleSheet()
        def _st(name, **kw):
            return ParagraphStyle(name, parent=styles['Normal'], **kw)

        ST_EMPRESA  = _st('emp',  fontSize=13, fontName='Helvetica-Bold',
                          textColor=BLANCO, alignment=TA_LEFT)
        ST_RFC      = _st('rfc',  fontSize=8,  fontName='Helvetica',
                          textColor=rl_colors.HexColor('#94a3b8'), alignment=TA_LEFT)
        ST_TITULO   = _st('tit',  fontSize=11, fontName='Helvetica-Bold',
                          textColor=ORO, alignment=TA_RIGHT)
        ST_SEC      = _st('sec',  fontSize=9,  fontName='Helvetica-Bold',
                          textColor=BLANCO)
        ST_LBL      = _st('lbl',  fontSize=8,  fontName='Helvetica-Bold',
                          textColor=GRIS)
        ST_VAL      = _st('val',  fontSize=9,  fontName='Helvetica',
                          textColor=AZL)
        ST_NUM      = _st('num',  fontSize=10, fontName='Helvetica-Bold',
                          textColor=AZL, alignment=TA_RIGHT)
        ST_NUMVD    = _st('nvd',  fontSize=10, fontName='Helvetica-Bold',
                          textColor=VERDE, alignment=TA_RIGHT)
        ST_NUMAM    = _st('nam',  fontSize=10, fontName='Helvetica-Bold',
                          textColor=rl_colors.HexColor('#b45309'), alignment=TA_RIGHT)
        ST_HDR_COL  = _st('hc',   fontSize=8,  fontName='Helvetica-Bold',
                          textColor=BLANCO, alignment=TA_CENTER)
        ST_CEL      = _st('cel',  fontSize=8,  fontName='Helvetica',
                          textColor=AZL)
        ST_CEL_C    = _st('celc', fontSize=8,  fontName='Helvetica',
                          textColor=AZL, alignment=TA_CENTER)
        ST_CEL_R    = _st('celr', fontSize=8,  fontName='Helvetica',
                          textColor=AZL, alignment=TA_RIGHT)
        ST_PIE      = _st('pie',  fontSize=6,  fontName='Helvetica',
                          textColor=GRIS, alignment=TA_CENTER)

        # ── Documento vertical (carta) ────────────────────────────────────────
        doc = SimpleDocTemplate(
            ruta, pagesize=letter,
            leftMargin=0.6*inch, rightMargin=0.6*inch,
            topMargin=0.5*inch,  bottomMargin=0.5*inch,
            title=f"Estado de Cuenta — ")

        W = doc.width
        story = []

        # ══════════════════════════════════════════════════════════════════════
        # CABECERA DEL DOCUMENTO
        # ══════════════════════════════════════════════════════════════════════
        hdr_data = [[
            Paragraph("COMERCIALIZADORA, LOGÍSTICA<br/>Y FUERZA YUCATECA", ST_EMPRESA),
            Paragraph("RFC: CLF240418U94<br/>clfyucateca@gmail.com", ST_RFC),
            Paragraph("ESTADO DE CUENTA<br/>DE PEDIDOS", ST_TITULO),
        ]]
        hdr_t = Table(hdr_data, colWidths=[W*0.40, W*0.30, W*0.30])
        hdr_t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), AZL),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING',   (0, 0), (-1, -1), 12),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 12),
        ]))
        story.append(hdr_t)

        periodo_txt = f"Período: {desde or '—'}  →  {hasta or '—'}     " \
                      f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        story.append(Paragraph(periodo_txt,
            _st('pf', fontSize=7, fontName='Helvetica', textColor=GRIS,
                alignment=TA_RIGHT, spaceBefore=3)))
        story.append(Spacer(1, 8))

        # ══════════════════════════════════════════════════════════════════════
        # SECCIÓN 1 — INFORMACIÓN DEL CLIENTE
        # ══════════════════════════════════════════════════════════════════════
        story.append(Table(
            [[Paragraph("  1.  INFORMACIÓN DEL CLIENTE", ST_SEC)]],
            colWidths=[W],
            style=TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), AZL),
                ('TOPPADDING',    (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ])))
        story.append(Spacer(1, 4))

        def _campo(lbl, val):
            return [Paragraph(lbl, ST_LBL), Paragraph(str(val) if val else '—', ST_VAL)]

        if modo_corp:
            # Corporativo: nombre arriba, tabla de miembros abajo
            story.append(Paragraph(f'<b>Corporativo:</b> {corp_nombre}',
                _st('corpnom', fontSize=11, fontName='Helvetica-Bold',
                    textColor=AZL, spaceBefore=4, spaceAfter=6)))

            # Tabla de miembros: columnas que coincidan para todos
            mem_hdr = [[
                Paragraph('Empresa / Nombre Comercial', ST_HDR_COL),
                Paragraph('RFC',     ST_HDR_COL),
                Paragraph('Email',   ST_HDR_COL),
            ]]
            mem_rows = []
            for i, m in enumerate(miembros):
                nom_m, razon_m, rfc_m, cont_m, tel_m, email_m, reg_m, uso_m, cp_m = m
                bg = BLANCO if i % 2 == 0 else BGCL
                mem_rows.append([
                    Paragraph(nom_m or '—', ST_VAL),
                    Paragraph(rfc_m  or '—', ST_CEL_C),
                    Paragraph(email_m or '—', ST_CEL),
                ])
            mem_t = Table(mem_hdr + mem_rows,
                          colWidths=[W*0.48, W*0.22, W*0.30])
            mem_ts = TableStyle([
                ('BACKGROUND',    (0,0), (-1,0), AZL),
                ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0,0), (-1,0), 8),
                ('TOPPADDING',    (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING',   (0,0), (-1,-1), 6),
                ('GRID',          (0,0), (-1,-1), 0.3, rl_colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS',(0,1), (-1,-1), [BLANCO, BGCL]),
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ])
            mem_t.setStyle(mem_ts)
            story.append(mem_t)
        else:
            # Cliente individual
            (cli_nom, cli_razon, cli_rfc, cli_contacto,
             cli_tel, cli_email, cli_regimen, cli_uso_cfdi, cli_cp) = miembros[0]
            cli_data = [
                _campo('Nombre / Razón Social',
                       f'{cli_nom}' + (f' / {cli_razon}' if cli_razon and cli_razon != cli_nom else '')),
                _campo('RFC',            cli_rfc),
                _campo('Contacto',       cli_contacto),
                _campo('Teléfono',       cli_tel),
                _campo('Email',          cli_email),
                _campo('Régimen Fiscal', cli_regimen),
            ]
            cli_t = Table(cli_data, colWidths=[W*0.22, W*0.78])
            cli_t.setStyle(TableStyle([
                ('FONTSIZE',      (0,0), (-1,-1), 8),
                ('TOPPADDING',    (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING',   (0,0), (-1,-1), 6),
                ('ROWBACKGROUNDS',(0,0), (-1,-1), [BLANCO, BGCL]),
                ('GRID',          (0,0), (-1,-1), 0.3, rl_colors.HexColor('#e2e8f0')),
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(cli_t)
        story.append(Spacer(1, 12))

        # ══════════════════════════════════════════════════════════════════════
        # SECCIÓN 2 — RESUMEN DEL PERIODO
        # ══════════════════════════════════════════════════════════════════════
        story.append(Table(
            [[Paragraph("  2.  RESUMEN DEL PERÍODO", ST_SEC)]],
            colWidths=[W],
            style=TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), AZL),
                ('TOPPADDING',    (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ])))
        story.append(Spacer(1, 4))

        # ── Calcular balances (soporta lista de clientes para corporativos) ─────
        def _calc_balance(fecha_hasta_calc):
            ph_cli = ','.join('?' * len(nombres_clientes))
            params_b = list(nombres_clientes)
            w_hasta  = ''
            if fecha_hasta_calc:
                w_hasta = 'AND c.fecha <= ?'
                params_b.append(fecha_hasta_calc)

            self.cursor.execute(f"""
                SELECT
                    COUNT(*)                                    AS n_solicitadas,
                    COALESCE(SUM(c.total), 0)                  AS monto_solicitadas,
                    -- Entregadas: incluye Entregada, Facturada y Pagada
                    SUM(CASE WHEN c.estado IN ('Entregada','Facturada','Pagada')
                        THEN 1 ELSE 0 END)                     AS n_entregadas,
                    COALESCE(SUM(CASE WHEN c.estado IN ('Entregada','Facturada','Pagada')
                        THEN c.total ELSE 0 END), 0)           AS monto_entregadas,
                    -- En tránsito: programadas + parcialmente entregadas
                    COALESCE(SUM(CASE WHEN c.estado IN
                        ('Programada','Parcialmente Entregada')
                        THEN c.total ELSE 0 END), 0)           AS monto_transito,
                    -- Total activo = entregado + en tránsito
                    COALESCE(SUM(CASE WHEN c.estado IN
                        ('Programada','Parcialmente Entregada','Entregada','Facturada','Pagada')
                        THEN c.total ELSE 0 END), 0)           AS monto_activo,
                    -- Pagado: suma de monto_pagado de todos los estados activos
                    COALESCE(SUM(CASE WHEN c.estado IN
                        ('Programada','Parcialmente Entregada','Entregada','Facturada','Pagada')
                        THEN COALESCE(c.monto_pagado, 0) ELSE 0 END), 0) AS monto_pagado
                FROM cotizaciones c
                JOIN clientes cl ON cl.id = c.cliente_id
                WHERE cl.nombre_comercial IN ({ph_cli})
                  AND c.estado != 'Cancelada'
                  {w_hasta}
            """, params_b)
            row = self.cursor.fetchone()
            n_sol, m_sol, n_ent, m_ent, m_tra, m_act, m_pag = row
            return {
                'n_sol':   int(n_sol or 0),
                'm_sol':   float(m_sol or 0),
                'n_ent':   int(n_ent or 0),
                'm_ent':   float(m_ent or 0),
                'm_act':   float(m_act or 0),
                'm_tra':   float(m_tra or 0),
                'm_pag':   float(m_pag or 0),
                # Saldo = total activo - pagado
                'm_pend':  float(m_act or 0) - float(m_pag or 0),
            }

        # Balance inicial = estado hasta el día ANTERIOR al inicio del período
        from datetime import timedelta
        try:
            d_ini_dt  = datetime.strptime(desde, '%Y-%m-%d')
            d_ant_str = (d_ini_dt - timedelta(days=1)).strftime('%Y-%m-%d')
        except Exception:
            d_ant_str = None

        bal_ini = _calc_balance(d_ant_str)
        bal_fin = _calc_balance(hasta if hasta else None)

        # ── Tabla de balance comparativo ──────────────────────────────────────
        COL_MET = W * 0.38
        COL_INI = W * 0.31
        COL_FIN = W * 0.31

        def _m(val, style=ST_NUM):
            return Paragraph(f'${val:,.2f}', style)
        def _n(val):
            return Paragraph(str(val), ST_NUM)

        bal_head = [[
            Paragraph('', ST_HDR_COL),
            Paragraph(f'Balance Inicial\n(al {d_ant_str or "inicio"})', ST_HDR_COL),
            Paragraph(f'Balance Final\n(al {hasta or "hoy"})',           ST_HDR_COL),
        ]]
        bal_rows = [
            [Paragraph('Órdenes solicitadas',           ST_LBL),
             _n(bal_ini['n_sol']),   _n(bal_fin['n_sol'])],
            [Paragraph('Órdenes entregadas',            ST_LBL),
             _n(bal_ini['n_ent']),   _n(bal_fin['n_ent'])],
            [Paragraph('Monto entregado\n(entregadas totalmente)',
                       _st('lbl2', fontSize=8, fontName='Helvetica-Bold',
                           textColor=GRIS)),
             _m(bal_ini['m_ent']),   _m(bal_fin['m_ent'], ST_NUMVD)],
            [Paragraph('Monto en tránsito\n(programadas + parcialmente entregadas)',
                       _st('lbl2', fontSize=8, fontName='Helvetica-Bold',
                           textColor=GRIS)),
             _m(bal_ini['m_tra']),   _m(bal_fin['m_tra'])],
            [Paragraph('Monto total activo\n(entregado + en tránsito)',
                       _st('lbl2', fontSize=8, fontName='Helvetica-Bold',
                           textColor=GRIS)),
             _m(bal_ini['m_act']),   _m(bal_fin['m_act'])],
            [Paragraph('Monto pagado\n(cotizaciones marcadas Pagada)',
                       _st('lbl2', fontSize=8, fontName='Helvetica-Bold',
                           textColor=GRIS)),
             _m(bal_ini['m_pag'], ST_NUMVD),
             _m(bal_fin['m_pag'], ST_NUMVD)],
            [Paragraph('Saldo pendiente de pago\n(total activo − pagado)',
                       ST_LBL),
             _m(bal_ini['m_pend'], ST_NUMAM),
             _m(bal_fin['m_pend'], ST_NUMAM)],
        ]

        bal_data = bal_head + bal_rows
        bal_t = Table(bal_data, colWidths=[COL_MET, COL_INI, COL_FIN])
        bal_ts = TableStyle([
            # Encabezado
            ('BACKGROUND',    (0,0), (-1,0), AZL),
            ('TEXTCOLOR',     (0,0), (-1,0), BLANCO),
            ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,0), 8),
            ('TOPPADDING',    (0,0), (-1,0), 6),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('ALIGN',         (0,0), (-1,0), 'CENTER'),
            # Cuerpo
            ('FONTSIZE',      (0,1), (-1,-1), 8),
            ('TOPPADDING',    (0,1), (-1,-1), 5),
            ('BOTTOMPADDING', (0,1), (-1,-1), 5),
            ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ('RIGHTPADDING',  (0,0), (-1,-1), 8),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [BLANCO, BGCL]),
            ('GRID',          (0,0), (-1,-1), 0.3, rl_colors.HexColor('#d0d7e4')),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            # Separador visual antes de saldo pendiente (última fila)
            ('LINEABOVE',     (0,-1), (-1,-1), 1.0, AZL),
            ('BACKGROUND',    (0,-1), (-1,-1), BGAM),
            ('FONTNAME',      (0,-1), (-1,-1), 'Helvetica-Bold'),
        ])
        bal_t.setStyle(bal_ts)
        story.append(bal_t)
        story.append(Spacer(1, 14))

        # ══════════════════════════════════════════════════════════════════════
        # SECCIÓN 3 — DETALLE DE PENDIENTES DE PAGO
        # ══════════════════════════════════════════════════════════════════════
        story.append(Table(
            [[Paragraph("  3.  DETALLE DE PENDIENTES DE PAGO", ST_SEC)]],
            colWidths=[W],
            style=TableStyle([
                ('BACKGROUND',    (0,0), (-1,-1), AZL),
                ('TOPPADDING',    (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('LEFTPADDING',   (0,0), (-1,-1), 8),
            ])))
        story.append(Spacer(1, 4))

        # Órdenes con saldo pendiente en el período, estados activos
        ph_cli_p  = ','.join('?' * len(nombres_clientes))
        params_p  = list(nombres_clientes)
        w_desde_p = w_hasta_p = ''
        if desde:
            w_desde_p = 'AND c.fecha >= ?'
            params_p.append(desde)
        if hasta:
            w_hasta_p = 'AND c.fecha <= ?'
            params_p.append(hasta)

        self.cursor.execute(f"""
            SELECT c.folio, c.fecha, cl.nombre_comercial,
                   c.total, c.monto_pagado, c.estado, c.orden_compra, c.id
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE cl.nombre_comercial IN ({ph_cli_p})
              AND c.estado IN ('Programada','Parcialmente Entregada','Entregada','Facturada')
              AND (c.total - COALESCE(c.monto_pagado,0)) > 0.01
              {w_desde_p}
              {w_hasta_p}
            ORDER BY cl.nombre_comercial ASC, c.fecha ASC, c.folio ASC
        """, params_p)
        pend_rows = self.cursor.fetchall()

        # Obtener referencias OC desde seguimiento
        oc_map = {}
        if pend_rows:
            ids_p = [r[7] for r in pend_rows]
            ph    = ','.join('?' * len(ids_p))
            self.cursor.execute(f"""
                SELECT cotizacion_id, referencia FROM seguimiento_etapas
                WHERE cotizacion_id IN ({ph}) AND etapa = 'Orden de Compra'
            """, ids_p)
            for cid, ref in self.cursor.fetchall():
                oc_map[cid] = ref

        if not pend_rows:
            story.append(Paragraph(
                '✅  No hay órdenes pendientes de pago en el período seleccionado.',
                _st('ok', fontSize=9, fontName='Helvetica',
                    textColor=VERDE, spaceBefore=6, spaceAfter=6)))
        else:
            ESTADO_COLOR_PDF = {
                'Programada':             BGAZ,
                'Parcialmente Entregada': rl_colors.HexColor('#ede9fe'),
                'Entregada':              BGVD,
                'Facturada':              rl_colors.HexColor('#cffafe'),
            }

            # Encabezados tabla
            if modo_corp:
                det_head = [[
                    Paragraph('Folio',   ST_HDR_COL),
                    Paragraph('Fecha',   ST_HDR_COL),
                    Paragraph('Cliente', ST_HDR_COL),
                    Paragraph('Total',   ST_HDR_COL),
                    Paragraph('Saldo\nPendiente', ST_HDR_COL),
                    Paragraph('Estado',  ST_HDR_COL),
                    Paragraph('O.C.',    ST_HDR_COL),
                ]]
            else:
                det_head = [[
                    Paragraph('Folio',   ST_HDR_COL),
                    Paragraph('Fecha',   ST_HDR_COL),
                    Paragraph('Cliente', ST_HDR_COL),
                    Paragraph('Total',   ST_HDR_COL),
                    Paragraph('Saldo\nPendiente', ST_HDR_COL),
                    Paragraph('Estado',  ST_HDR_COL),
                    Paragraph('O.C.',    ST_HDR_COL),
                ]]
            det_data = list(det_head)

            total_pend = 0.0
            row_colors = []

            for folio, fecha, cliente, total, m_pag, estado, oc, cid in pend_rows:
                saldo = (total or 0) - (m_pag or 0)
                total_pend += saldo
                oc_txt = oc_map.get(cid) or (oc or '—')

                icono_est = {
                    'Programada': '📅',
                    'Parcialmente Entregada': '📦',
                    'Entregada': '✅',
                    'Facturada': '🧾',
                }.get(estado, '')

                row_cells = [
                    Paragraph(str(folio),              ST_CEL_C),
                    Paragraph((fecha or '')[:10],       ST_CEL_C),
                    Paragraph(str(cliente)[:30],        ST_CEL),
                    Paragraph(f'${total:,.2f}',         ST_CEL_R),
                    Paragraph(f'${saldo:,.2f}',
                               _st('sr', fontSize=8, fontName='Helvetica-Bold',
                                   textColor=rl_colors.HexColor('#b45309'),
                                   alignment=TA_RIGHT)),
                    Paragraph(f'{icono_est} {estado}',  ST_CEL_C),
                    Paragraph(str(oc_txt)[:22],         ST_CEL_C),
                ]
                det_data.append(row_cells)
                row_colors.append(ESTADO_COLOR_PDF.get(estado, BLANCO))

            # Fila de total
            tot_row = [
                Paragraph('', ST_CEL),
                Paragraph('', ST_CEL),
                Paragraph('TOTAL PENDIENTE', _st('tp', fontSize=8,
                           fontName='Helvetica-Bold', textColor=BLANCO,
                           alignment=TA_RIGHT)),
                Paragraph('', ST_CEL),
                Paragraph(f'${total_pend:,.2f}',
                           _st('totpend', fontSize=9, fontName='Helvetica-Bold',
                               textColor=BLANCO, alignment=TA_RIGHT)),
                Paragraph('', ST_CEL),
                Paragraph('', ST_CEL),
            ]
            det_data.append(tot_row)

            # En modo corporativo la columna Cliente es más visible
            CW = [W*0.10, W*0.09, W*0.24, W*0.11, W*0.13, W*0.20, W*0.13]
            det_t = Table(det_data, colWidths=CW, repeatRows=1)
            det_ts = TableStyle([
                # Header
                ('BACKGROUND',    (0,0), (-1,0), AZL),
                ('FONTNAME',      (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE',      (0,0), (-1,0), 8),
                ('TOPPADDING',    (0,0), (-1,0), 5),
                ('BOTTOMPADDING', (0,0), (-1,0), 5),
                # Cuerpo
                ('FONTSIZE',      (0,1), (-1,-2), 8),
                ('TOPPADDING',    (0,1), (-1,-1), 4),
                ('BOTTOMPADDING', (0,1), (-1,-1), 4),
                ('LEFTPADDING',   (0,0), (-1,-1), 5),
                ('RIGHTPADDING',  (0,0), (-1,-1), 5),
                ('GRID',          (0,0), (-1,-2), 0.3,
                 rl_colors.HexColor('#d0d7e4')),
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
                # Fila de total (última)
                ('BACKGROUND',    (0,-1), (-1,-1), AZL),
                ('LINEABOVE',     (0,-1), (-1,-1), 1.0, ORO),
                ('SPAN',          (2,-1), (2,-1)),
            ])
            # Colorear filas por estado
            for i, col in enumerate(row_colors, start=1):
                det_ts.add('BACKGROUND', (0, i), (-1, i), col)
            det_t.setStyle(det_ts)
            story.append(det_t)

        # ══════════════════════════════════════════════════════════════════════
        # PIE DE PÁGINA
        # ══════════════════════════════════════════════════════════════════════
        story.append(Spacer(1, 10))
        story.append(HRFlowable(
            width='100%', thickness=0.5,
            color=rl_colors.HexColor('#d0d7e4')))
        story.append(Paragraph(
            "Comercializadora, Logística y Fuerza Yucateca  ·  RFC: CLF240418U94  ·  "
            f"Generado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}",
            ST_PIE))

        # ── Build ─────────────────────────────────────────────────────────────
        try:
            doc.build(story)
            messagebox.showinfo("PDF generado",
                f"Estado de cuenta guardado en:\n{ruta}", parent=self.win)
            import subprocess, platform
            try:
                if platform.system() == 'Windows':
                    os.startfile(ruta)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', ruta])
                else:
                    subprocess.Popen(['xdg-open', ruta])
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error al generar PDF", str(e), parent=self.win)

    # ── Exportar Excel ─────────────────────────────────────────────────────────

    def exportar_excel(self):
        """Genera un archivo .xlsx con el estado de cuenta formateado."""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import (Font, PatternFill, Alignment,
                                         Border, Side)
            from openpyxl.utils import get_column_letter
        except ImportError:
            # Intentar instalar automáticamente
            import subprocess, sys
            resp = messagebox.askyesno(
                "Librería faltante",
                "Se necesita 'openpyxl' para exportar Excel.\n\n"
                "¿Deseas instalarlo ahora automáticamente?",
                parent=self.win)
            if not resp:
                return
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "openpyxl"],
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            except Exception as e:
                messagebox.showerror(
                    "Error al instalar",
                    f"No se pudo instalar openpyxl:\n{e}\n\n"
                    "Ejecútalo manualmente:\n  pip install openpyxl",
                    parent=self.win)
                return
            # Reintentar importación
            try:
                from openpyxl import Workbook
                from openpyxl.styles import (Font, PatternFill, Alignment,
                                             Border, Side)
                from openpyxl.utils import get_column_letter
            except ImportError as e:
                messagebox.showerror("Error", str(e), parent=self.win)
                return

        # Elegir destino
        ruta = filedialog.asksaveasfilename(
            parent=self.win,
            title="Guardar Estado de Cuenta Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=f"Estado_Cuenta_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )
        if not ruta:
            return

        filas = [self.tree.item(iid)['values']
                 for iid in self.tree.get_children()]

        if not filas:
            messagebox.showwarning("Sin datos", "No hay datos para exportar.",
                                   parent=self.win)
            return

        wb = Workbook()

        # ── Hoja principal ────────────────────────────────────────────────────
        ws = wb.active
        ws.title = "Estado de Cuenta"

        # ── Paleta de colores ─────────────────────────────────────────────────
        COLOR_AZUL      = "1E2D45"
        COLOR_ORO       = "D4AF37"
        COLOR_GRIS_CLR  = "D8DDE8"
        COLOR_BLANCO    = "FFFFFF"
        COLOR_VERDE_HDR = "0F7B5E"

        # Colores de estado (sin #)
        ESTADO_BG = {
            'Pendiente':              'FFF3CD',
            'Programada':             'CCE5FF',
            'Parcialmente Entregada': 'E8D5FF',
            'Entregada':              'D4EDDA',
            'Facturada':              'CFFAFE',
            'Pagada':                 'BBF7D0',
            'Cancelada':              'F1F5F9',
        }

        def fill(hex_color):
            return PatternFill("solid", fgColor=hex_color)

        def border_thin():
            s = Side(style='thin', color='C5CCD8')
            return Border(left=s, right=s, top=s, bottom=s)

        def border_medium():
            s = Side(style='medium', color='1E2D45')
            return Border(left=s, right=s, top=s, bottom=s)

        # ── Fila 1: Título de empresa ─────────────────────────────────────────
        ws.merge_cells('A1:P1')
        c = ws['A1']
        c.value = "COMERCIALIZADORA, LOGÍSTICA Y FUERZA YUCATECA"
        c.font      = Font(name='Arial', size=13, bold=True, color=COLOR_BLANCO)
        c.fill      = fill(COLOR_AZUL)
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 22

        # ── Fila 2: Sub-título ────────────────────────────────────────────────
        ws.merge_cells('A2:P2')
        c = ws['A2']
        c.value = "ESTADO DE CUENTA DE PEDIDOS"
        c.font      = Font(name='Arial', size=11, bold=True, color=COLOR_ORO)
        c.fill      = fill(COLOR_AZUL)
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[2].height = 18

        # ── Fila 3: Filtros / Fecha ───────────────────────────────────────────
        filtros = []
        if self._var_corp.get() != 'Todos':
            filtros.append(f"Corporativo: {self._var_corp.get()}")
        if self._var_cliente.get() != 'Todos':
            filtros.append(f"Cliente: {self._var_cliente.get()}")
        if self._var_estado.get() != 'Todos':
            filtros.append(f"Estado: {self._var_estado.get()}")
        d = self._entry_desde.get().strip()
        h = self._entry_hasta.get().strip()
        if d or h:
            filtros.append(f"Período: {d or '—'} → {h or '—'}")
        filtros.append(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        ws.merge_cells('A3:P3')
        c = ws['A3']
        c.value = "   ".join(filtros)
        c.font      = Font(name='Arial', size=8, color="6B7E99")
        c.fill      = fill("ECF0F4")
        c.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[3].height = 14

        # ── Fila 4: Espacio ───────────────────────────────────────────────────
        ws.row_dimensions[4].height = 6

        # ── Fila 5: Encabezados de columna ───────────────────────────────────
        HEADERS = [
            'Folio', 'Fecha', 'Cliente',
            'Total ($)', 'Estado',
            'Fecha Entrega', 'Mto. Entregado ($)',
            'Orden Compra', 'Fecha O.C.',
            'N° Factura', 'Fecha Factura',
            'Mto. Facturado ($)',
            'Fecha Pago', 'Mto. Pagado ($)',
            'Saldo Pendiente ($)',
        ]
        # Índices del tree a usar (0=ID se omite, 1..15)
        IDX = list(range(1, 16))

        HDR_ROW = 5
        for col_i, header in enumerate(HEADERS, start=1):
            c = ws.cell(row=HDR_ROW, column=col_i, value=header)
            c.font      = Font(name='Arial', size=9, bold=True, color=COLOR_BLANCO)
            c.fill      = fill(COLOR_VERDE_HDR)
            c.alignment = Alignment(horizontal='center', vertical='center',
                                    wrap_text=True)
            c.border    = border_medium()
        ws.row_dimensions[HDR_ROW].height = 28

        # ── Filas de datos ────────────────────────────────────────────────────
        def _num(val):
            """Convierte '$1,234.56' → float o None"""
            try:
                return float(str(val).replace('$', '').replace(',', '').strip())
            except Exception:
                return None

        # Columnas que son montos (índice 1-based en la hoja, relativo a HEADERS)
        # Total=4, MtoEntregado=7, MtoFacturado=12, MtoPagado=14, Saldo=15
        COLS_MONTO = {4, 7, 12, 14, 15}  # posición en HEADERS (1-based)
        COLS_FECHA = {2, 6, 9, 11, 13}   # posición en HEADERS

        fmt_peso  = '#,##0.00'
        fmt_fecha = 'YYYY-MM-DD'

        for row_i, v in enumerate(filas, start=HDR_ROW + 1):
            estado_val = str(v[5]) if len(v) > 5 else ''

            # Determinar color de fondo por estado
            row_bg = None
            for key, bg in ESTADO_BG.items():
                if key in estado_val:
                    row_bg = bg
                    break

            for col_i, tree_idx in enumerate(IDX, start=1):
                raw = v[tree_idx] if tree_idx < len(v) else ''
                val = raw

                # Intentar convertir montos a número
                if col_i in COLS_MONTO:
                    num = _num(raw)
                    val = num if num is not None else raw

                c = ws.cell(row=row_i, column=col_i, value=val)
                c.font   = Font(name='Arial', size=8)
                c.border = border_thin()
                c.alignment = Alignment(vertical='center', wrap_text=False)

                # Formato número
                if col_i in COLS_MONTO and isinstance(val, float):
                    c.number_format = fmt_peso
                    c.alignment = Alignment(horizontal='right', vertical='center')

                # Alineación centrada para fechas y estado
                if col_i in COLS_FECHA or col_i == 5:
                    c.alignment = Alignment(horizontal='center', vertical='center')

                # Color de fila
                if row_bg:
                    c.fill = fill(row_bg)
                else:
                    # Filas alternas blanco / gris muy claro
                    alt = "F7F9FC" if (row_i % 2 == 0) else COLOR_BLANCO
                    c.fill = fill(alt)

            ws.row_dimensions[row_i].height = 16

        # ── Fila de totales ───────────────────────────────────────────────────
        tot_row = HDR_ROW + len(filas) + 1

        # Calcular fila de inicio y fin de datos para fórmulas
        data_start = HDR_ROW + 1
        data_end   = HDR_ROW + len(filas)

        # Col 3 = Cliente → "TOTALES"
        c = ws.cell(row=tot_row, column=3, value="TOTALES")
        c.font      = Font(name='Arial', size=9, bold=True, color=COLOR_BLANCO)
        c.fill      = fill(COLOR_AZUL)
        c.alignment = Alignment(horizontal='right', vertical='center')
        c.border    = border_medium()

        # Columnas con suma: Total(4), MtoEntregado(7), MtoFacturado(12), MtoPagado(14), Saldo(15)
        COLS_SUMA = {4: 'D', 7: 'G', 12: 'L', 14: 'N', 15: 'O'}
        for col_i in range(1, len(HEADERS) + 1):
            c = ws.cell(row=tot_row, column=col_i)
            if col_i in COLS_SUMA:
                col_letra = COLS_SUMA[col_i]
                c.value        = f'=SUM({col_letra}{data_start}:{col_letra}{data_end})'
                c.number_format = fmt_peso
                c.font  = Font(name='Arial', size=9, bold=True, color=COLOR_BLANCO)
                c.fill  = fill(COLOR_AZUL)
                c.alignment = Alignment(horizontal='right', vertical='center')
            else:
                if col_i != 3:
                    c.fill = fill(COLOR_AZUL)
            c.border = border_medium()
        ws.row_dimensions[tot_row].height = 18

        # ── Fila de conteo ────────────────────────────────────────────────────
        cnt_row = tot_row + 1
        ws.merge_cells(f'A{cnt_row}:C{cnt_row}')
        c = ws[f'A{cnt_row}']
        c.value     = f"Total de pedidos: {len(filas)}"
        c.font      = Font(name='Arial', size=8, italic=True, color="6B7E99")
        c.alignment = Alignment(horizontal='left', vertical='center')
        ws.row_dimensions[cnt_row].height = 14

        # ── Anchos de columna ─────────────────────────────────────────────────
        anchos = [13, 11, 28, 13, 22, 13, 16, 16, 11, 16, 13, 16, 11, 13, 16]
        for col_i, ancho in enumerate(anchos, start=1):
            ws.column_dimensions[get_column_letter(col_i)].width = ancho

        # ── Inmovilizar encabezados ───────────────────────────────────────────
        ws.freeze_panes = f'A{HDR_ROW + 1}'

        # ── Auto-filtro ───────────────────────────────────────────────────────
        ws.auto_filter.ref = (
            f"A{HDR_ROW}:{get_column_letter(len(HEADERS))}{HDR_ROW}")

        # ── Hoja resumen por cliente ──────────────────────────────────────────
        ws2 = wb.create_sheet("Resumen por Cliente")
        ws2['A1'] = "Cliente"
        ws2['B1'] = "Pedidos"
        ws2['C1'] = "Valor Total ($)"
        ws2['D1'] = "Mto. Pagado ($)"
        ws2['E1'] = "Saldo Pendiente ($)"

        for col in ['A', 'B', 'C', 'D', 'E']:
            c = ws2[f'{col}1']
            c.font      = Font(name='Arial', size=9, bold=True, color=COLOR_BLANCO)
            c.fill      = fill(COLOR_VERDE_HDR)
            c.alignment = Alignment(horizontal='center', vertical='center')
            c.border    = border_medium()
        ws2.row_dimensions[1].height = 22

        # Agrupar por cliente
        resumen = {}
        for v in filas:
            cliente = str(v[3])
            total   = _num(v[4])  or 0
            pagado  = _num(v[14]) or 0
            saldo   = _num(v[15]) or 0
            if cliente not in resumen:
                resumen[cliente] = {'n': 0, 'total': 0, 'pagado': 0, 'saldo': 0}
            resumen[cliente]['n']      += 1
            resumen[cliente]['total']  += total
            resumen[cliente]['pagado'] += pagado
            resumen[cliente]['saldo']  += saldo

        for r_i, (cliente, datos) in enumerate(
                sorted(resumen.items()), start=2):
            alt = "F7F9FC" if r_i % 2 == 0 else COLOR_BLANCO
            for col_i, val in enumerate(
                    [cliente, datos['n'], datos['total'],
                     datos['pagado'], datos['saldo']], start=1):
                c = ws2.cell(row=r_i, column=col_i, value=val)
                c.font   = Font(name='Arial', size=8)
                c.fill   = fill(alt)
                c.border = border_thin()
                if col_i >= 3:
                    c.number_format = fmt_peso
                    c.alignment = Alignment(horizontal='right', vertical='center')
            ws2.row_dimensions[r_i].height = 15

        # Totals row
        t_row = len(resumen) + 2
        ws2.cell(row=t_row, column=1, value="TOTAL GENERAL").font = Font(
            name='Arial', size=9, bold=True, color=COLOR_BLANCO)
        for col_i in range(1, 6):
            c = ws2.cell(row=t_row, column=col_i)
            c.fill   = fill(COLOR_AZUL)
            c.border = border_medium()
            if col_i == 2:
                c.value  = f'=SUM(B2:B{t_row-1})'
                c.font   = Font(name='Arial', size=9, bold=True, color=COLOR_BLANCO)
            elif col_i >= 3:
                col_l = get_column_letter(col_i)
                c.value         = f'=SUM({col_l}2:{col_l}{t_row-1})'
                c.number_format = fmt_peso
                c.font  = Font(name='Arial', size=9, bold=True, color=COLOR_BLANCO)
                c.alignment = Alignment(horizontal='right', vertical='center')

        for col, w in zip(['A','B','C','D','E'], [32, 9, 16, 14, 16]):
            ws2.column_dimensions[col].width = w
        ws2.freeze_panes = 'A2'

        # ── Guardar ───────────────────────────────────────────────────────────
        try:
            wb.save(ruta)
        except PermissionError:
            messagebox.showerror(
                "Error", f"No se pudo guardar. ¿El archivo está abierto?\n{ruta}",
                parent=self.win)
            return

        messagebox.showinfo(
            "Excel generado",
            f"Estado de cuenta exportado correctamente:\n{ruta}",
            parent=self.win)

        import subprocess, platform
        try:
            if platform.system() == 'Windows':
                os.startfile(ruta)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', ruta])
            else:
                subprocess.Popen(['xdg-open', ruta])
        except Exception:
            pass
