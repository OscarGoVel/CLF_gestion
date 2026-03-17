#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Gestión de Stock
Sistema de Gestión Comercial - CLF Yucateca

Funcionalidades:
  - Vista de stock real con categorización ABC
  - Registro de salidas (mermas, ajustes, uso interno, devoluciones)
  - Historial de movimientos (entradas + salidas)
  - Análisis ABC automático por valor de inventario
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
#  COLORES Y ESTILOS
# ─────────────────────────────────────────────────────────────────────────────

COLOR_A       = '#1a6b3a'   # Verde oscuro — Categoría A
COLOR_A_BG    = '#d4edda'
COLOR_B       = '#856404'   # Amarillo oscuro — Categoría B
COLOR_B_BG    = '#fff3cd'
COLOR_C       = '#6c757d'   # Gris — Categoría C
COLOR_C_BG    = '#f8f9fa'
COLOR_BAJO    = '#c0392b'   # Rojo — bajo stock mínimo
COLOR_BAJO_BG = '#fde8e8'

MOTIVOS_SALIDA = [
    'Merma / Daño',
    'Uso interno',
    'Devolución a proveedor',
    'Ajuste de inventario',
    'Muestra / Demo',
    'Pérdida',
    'Otro',
]


# ─────────────────────────────────────────────────────────────────────────────
#  LÓGICA ABC
# ─────────────────────────────────────────────────────────────────────────────

def calcular_abc(cursor):
    """
    Calcula la categoría ABC de cada producto basada en valor de inventario
    (stock_actual × costo_promedio).

    Reglas clásicas:
      A → acumulado hasta  80 % del valor total
      B → acumulado de 80 % a 95 %
      C → acumulado de 95 % a 100 %

    Retorna: dict  {producto_id: {'categoria': 'A'|'B'|'C',
                                   'valor': float,
                                   'porcentaje_acum': float}}
    """
    cursor.execute("""
        SELECT p.id,
               p.nombre,
               p.codigo,
               p.stock_actual,
               COALESCE(
                   (SELECT AVG(cd.costo_unitario)
                    FROM compra_detalle cd
                    WHERE cd.producto_id = p.id),
                   0
               ) AS costo_prom
        FROM productos p
        WHERE p.stock_actual > 0
        ORDER BY (p.stock_actual * COALESCE(
                   (SELECT AVG(cd.costo_unitario)
                    FROM compra_detalle cd
                    WHERE cd.producto_id = p.id), 0))
        DESC
    """)
    rows = cursor.fetchall()

    if not rows:
        return {}

    total_valor = sum(r[3] * r[4] for r in rows)
    if total_valor == 0:
        # Si no hay costos registrados, clasificar por cantidad
        total_valor = sum(r[3] for r in rows)
        datos = [(r[0], r[3]) for r in rows]   # (id, stock)
    else:
        datos = [(r[0], r[3] * r[4]) for r in rows]  # (id, valor)

    resultado = {}
    acum = 0.0
    for pid, valor in datos:
        acum += valor
        pct = (acum / total_valor) * 100 if total_valor else 100
        if pct <= 80:
            cat = 'A'
        elif pct <= 95:
            cat = 'B'
        else:
            cat = 'C'
        resultado[pid] = {
            'categoria': cat,
            'valor': valor,
            'porcentaje_acum': round(pct, 1),
        }

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
#  SECCIÓN STOCK (se inyecta en SistemaGestion)
# ─────────────────────────────────────────────────────────────────────────────

class SeccionStock:
    """
    Crea y gestiona la sección de stock dentro de la ventana principal.
    Se instancia desde main.py pasando la referencia al sistema.
    """

    def __init__(self, sistema):
        self.s        = sistema          # referencia a SistemaGestion
        self.conn     = sistema.conn
        self.cursor   = sistema.cursor
        self.C        = sistema.C        # paleta de colores
        self._abc     = {}               # cache de cálculo ABC

        self._asegurar_tablas()
        self._crear_ui()

    # ── Tablas ────────────────────────────────────────────────────────────────
    def _asegurar_tablas(self):
        """Crea las tablas necesarias si no existen."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos_stock (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id     INTEGER NOT NULL,
                tipo            TEXT    NOT NULL,   -- 'entrada' | 'salida'
                motivo          TEXT,
                cantidad        REAL    NOT NULL,
                stock_antes     REAL    NOT NULL,
                stock_despues   REAL    NOT NULL,
                referencia      TEXT,               -- folio compra/cotizacion
                notas           TEXT,
                fecha           DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
        """)
        self.conn.commit()

    # ── UI principal ──────────────────────────────────────────────────────────
    def _crear_ui(self):
        """Construye el frame principal de la sección Stock."""
        sec = tk.Frame(self.s._content_area, bg=self.C['content_bg'])
        self.s._secciones['stock'] = sec

        # ── Toolbar principal ─────────────────────────────────────────
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], pady=4)
        tb.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        tk.Button(
            tb, text='📥  Nueva Entrada',
            font=('Arial', 9, 'bold'),
            bg='#27ae60', fg='white', bd=0, padx=14,
            cursor='hand2',
            command=self.abrir_entrada
        ).pack(side='left', padx=6, pady=4)

        tk.Button(
            tb, text='📤  Nueva Salida',
            font=('Arial', 9, 'bold'),
            bg='#e74c3c', fg='white', bd=0, padx=14,
            cursor='hand2',
            command=self.abrir_salida
        ).pack(side='left', padx=2, pady=4)

        tk.Frame(tb, bg=self.C['toolbar_border'], width=1
                 ).pack(side='left', fill='y', pady=4, padx=6)

        tk.Button(
            tb, text='🛒  Presupuesto de Compra',
            font=('Arial', 9, 'bold'),
            bg=self.C['accent2'], fg='white', bd=0, padx=14,
            cursor='hand2',
            command=self._abrir_presupuesto_compra
        ).pack(side='left', padx=2, pady=4)

        # ── Sub-pestañas ──────────────────────────────────────────────
        nb = ttk.Notebook(sec)
        nb.pack(fill='both', expand=True, padx=6, pady=6)

        tab_vista     = tk.Frame(nb, bg=self.C['content_bg'])
        tab_historial = tk.Frame(nb, bg=self.C['content_bg'])
        tab_abc       = tk.Frame(nb, bg=self.C['content_bg'])

        nb.add(tab_vista,     text='📦  Vista de Stock')
        nb.add(tab_historial, text='📋  Historial de Movimientos')
        nb.add(tab_abc,       text='📊  Análisis ABC')

        self._construir_tab_vista(tab_vista)
        self._construir_tab_historial(tab_historial)
        self._construir_tab_abc(tab_abc)

        # Refrescar al cambiar de pestaña
        nb.bind('<<NotebookTabChanged>>', self._on_tab_cambio)
        self._nb = nb

        # Carga inicial
        self.cargar_vista_stock()

    def abrir_entrada(self):
        """Abre la ventana de registro de compra/entrada — idéntica a Compras."""
        from compras import VentanaCompra  # import lazy para evitar circular import

        def _refrescar():
            try:
                self.cargar_vista_stock()
                self.cargar_historial()
                self.s.actualizar_dashboard()
            except Exception:
                pass

        win = VentanaCompra(self.s.root, self.conn, self.cursor,
                            on_guardado=_refrescar)
        win.ventana.protocol('WM_DELETE_WINDOW',
                             lambda: (win.ventana.destroy(), _refrescar()))

    def abrir_salida(self):
        """Abre la ventana de registro de salida de stock."""
        VentanaSalida(self.s.root, self.conn, self.cursor,
                      on_guardar=self._on_salida_guardada)

    def _abrir_presupuesto_compra(self):
        """Delega al método de presupuesto de compra del sistema principal."""
        if hasattr(self.s, 'generar_presupuesto_compra'):
            self.s.generar_presupuesto_compra()

    def _on_salida_guardada(self):
        """Callback tras guardar una salida."""
        self.cargar_vista_stock()
        self.cargar_historial()
        self.s.actualizar_dashboard()

    # ── Tab: Vista de Stock ───────────────────────────────────────────────────
    def _construir_tab_vista(self, parent):
        # Toolbar
        tb = tk.Frame(parent, bg=self.C['toolbar_bg'], pady=4)
        tb.pack(fill='x')

        tk.Button(tb, text='🔄 Actualizar', font=('Arial', 9, 'bold'),
                  bg=self.C['accent'], fg='white', bd=0, padx=12,
                  cursor='hand2', command=self.cargar_vista_stock
                  ).pack(side='left', padx=6)

        tk.Button(tb, text='📊 Calcular ABC', font=('Arial', 9, 'bold'),
                  bg='#8e44ad', fg='white', bd=0, padx=12,
                  cursor='hand2', command=self._calcular_y_mostrar_abc
                  ).pack(side='left', padx=2)

        # Filtro categoría
        tk.Label(tb, text='Categoría:', font=('Arial', 9),
                 bg=self.C['toolbar_bg']).pack(side='left', padx=(14, 2))
        self.var_filtro_cat = tk.StringVar(value='Todas')
        combo_cat = ttk.Combobox(tb, textvariable=self.var_filtro_cat,
                                 values=['Todas', 'A', 'B', 'C', 'Sin clasificar'],
                                 width=12, state='readonly')
        combo_cat.pack(side='left')
        combo_cat.bind('<<ComboboxSelected>>', lambda e: self.cargar_vista_stock())

        # Filtro bajo stock
        self.var_solo_bajo = tk.BooleanVar(value=False)
        tk.Checkbutton(tb, text='Solo bajo stock mínimo',
                       variable=self.var_solo_bajo,
                       command=self.cargar_vista_stock,
                       bg=self.C['toolbar_bg'], font=('Arial', 9)
                       ).pack(side='left', padx=8)

        # Buscar
        tk.Label(tb, text='Buscar:', font=('Arial', 9),
                 bg=self.C['toolbar_bg']).pack(side='right', padx=(0, 4))
        self.entry_buscar_stock = tk.Entry(tb, width=22, font=('Arial', 9))
        self.entry_buscar_stock.pack(side='right', padx=(0, 8))
        self.entry_buscar_stock.bind('<KeyRelease>',
                                     lambda e: self.cargar_vista_stock())

        # Leyenda ABC
        leyenda = tk.Frame(parent, bg=self.C['content_bg'])
        leyenda.pack(fill='x', padx=8, pady=(4, 0))
        for cat, color, bg, desc in [
            ('A', COLOR_A, COLOR_A_BG, '80% del valor — alta rotación / prioridad máxima'),
            ('B', COLOR_B, COLOR_B_BG, '15% del valor — rotación media'),
            ('C', COLOR_C, COLOR_C_BG,  '5% del valor — baja rotación'),
        ]:
            frame_leg = tk.Frame(leyenda, bg=bg, padx=6, pady=2,
                                 relief='flat', bd=1)
            frame_leg.pack(side='left', padx=4)
            tk.Label(frame_leg, text=f'  {cat}  ', font=('Arial', 9, 'bold'),
                     bg=bg, fg=color).pack(side='left')
            tk.Label(frame_leg, text=desc, font=('Arial', 8),
                     bg=bg, fg='#444').pack(side='left')

        # Tabla
        ft = tk.Frame(parent, bg=self.C['content_bg'])
        ft.pack(fill='both', expand=True, padx=8, pady=6)

        cols = ('Código', 'Producto', 'Cat.', 'Stock Actual',
                'Stock Mín.', 'Estado', 'Valor Inv.', 'Unidad')
        self.tree_stock = ttk.Treeview(ft, columns=cols,
                                       show='headings', selectmode='browse')
        anchos = {'Código': 90, 'Producto': 280, 'Cat.': 50,
                  'Stock Actual': 100, 'Stock Mín.': 90,
                  'Estado': 110, 'Valor Inv.': 110, 'Unidad': 70}
        alinear_der = {'Stock Actual', 'Stock Mín.', 'Valor Inv.'}
        for col in cols:
            anchor = 'e' if col in alinear_der else 'w'
            self.tree_stock.heading(col, text=col)
            self.tree_stock.column(col, width=anchos[col], anchor=anchor)

        # Tags de color
        self.tree_stock.tag_configure('cat_a',  background=COLOR_A_BG,
                                                 foreground=COLOR_A)
        self.tree_stock.tag_configure('cat_b',  background=COLOR_B_BG,
                                                 foreground=COLOR_B)
        self.tree_stock.tag_configure('cat_c',  background=COLOR_C_BG,
                                                 foreground=COLOR_C)
        self.tree_stock.tag_configure('bajo',   background=COLOR_BAJO_BG,
                                                 foreground=COLOR_BAJO)

        sc_y = ttk.Scrollbar(ft, orient='vertical',
                              command=self.tree_stock.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal',
                              command=self.tree_stock.xview)
        self.tree_stock.configure(yscrollcommand=sc_y.set,
                                   xscrollcommand=sc_x.set)
        self.tree_stock.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        # Resumen inferior
        self.lbl_resumen_stock = tk.Label(parent, text='',
                                          font=('Arial', 8),
                                          bg=self.C['content_bg'],
                                          fg=self.C['text_muted'])
        self.lbl_resumen_stock.pack(pady=(0, 4))

    def cargar_vista_stock(self):
        """Carga la tabla principal de stock con categorías ABC."""
        self.tree_stock.delete(*self.tree_stock.get_children())

        buscar   = self.entry_buscar_stock.get().strip().lower()
        filtro   = self.var_filtro_cat.get()
        solo_bajo= self.var_solo_bajo.get()

        self.cursor.execute("""
            SELECT p.id, p.codigo, p.nombre, p.stock_actual,
                   p.stock_minimo, p.unidad_medida,
                   COALESCE((SELECT AVG(cd.costo_unitario)
                              FROM compra_detalle cd
                              WHERE cd.producto_id = p.id), 0) AS costo_prom
            FROM productos p
            WHERE p.stock_actual != 0 OR p.stock_minimo > 0
            ORDER BY p.nombre
        """)
        rows = self.cursor.fetchall()

        total_productos = 0
        valor_total = 0.0
        bajo_minimo = 0

        for pid, codigo, nombre, stock, stock_min, unidad, costo in rows:
            # Filtro texto
            if buscar and buscar not in nombre.lower() and buscar not in (codigo or '').lower():
                continue

            # Filtro bajo stock
            if solo_bajo and (stock_min == 0 or stock > stock_min):
                continue

            # Categoría ABC (del cache)
            abc_data = self._abc.get(pid, {})
            cat = abc_data.get('categoria', '—')

            # Filtro categoría
            if filtro != 'Todas':
                if filtro == 'Sin clasificar' and cat != '—':
                    continue
                elif filtro in ('A', 'B', 'C') and cat != filtro:
                    continue

            valor = stock * costo
            valor_total += valor
            total_productos += 1

            if stock_min > 0 and stock <= stock_min:
                estado = '⚠ Bajo mínimo'
                bajo_minimo += 1
            elif stock == 0:
                estado = '❌ Sin stock'
                bajo_minimo += 1
            else:
                estado = '✅ OK'

            # Tag de color: bajo stock tiene prioridad sobre ABC
            if stock_min > 0 and stock <= stock_min:
                tag = 'bajo'
            elif cat == 'A':
                tag = 'cat_a'
            elif cat == 'B':
                tag = 'cat_b'
            else:
                tag = 'cat_c'

            self.tree_stock.insert('', 'end', iid=str(pid), values=(
                codigo or '',
                nombre,
                cat,
                f'{stock:,.2f}',
                f'{stock_min:,.2f}',
                estado,
                f'${valor:,.2f}',
                unidad or '',
            ), tags=(tag,))

        self.lbl_resumen_stock.config(
            text=f'{total_productos} productos  |  '
                 f'Valor total inventario: ${valor_total:,.2f}  |  '
                 f'{bajo_minimo} bajo stock mínimo'
        )


    # ── Tab: Historial ────────────────────────────────────────────────────────
    def _construir_tab_historial(self, parent):
        # Toolbar
        tb = tk.Frame(parent, bg=self.C['toolbar_bg'], pady=4)
        tb.pack(fill='x')

        tk.Label(tb, text='Tipo:', font=('Arial', 9),
                 bg=self.C['toolbar_bg']).pack(side='left', padx=(8, 2))
        self.var_filtro_tipo = tk.StringVar(value='Todos')
        ttk.Combobox(tb, textvariable=self.var_filtro_tipo,
                     values=['Todos', 'Entradas', 'Salidas'],
                     width=10, state='readonly'
                     ).pack(side='left')

        tk.Label(tb, text='Buscar producto:', font=('Arial', 9),
                 bg=self.C['toolbar_bg']).pack(side='left', padx=(12, 2))
        self.entry_buscar_hist = tk.Entry(tb, width=22, font=('Arial', 9))
        self.entry_buscar_hist.pack(side='left')

        tk.Button(tb, text='🔍 Buscar', font=('Arial', 9),
                  bg=self.C['accent2'], fg='white', bd=0, padx=10,
                  cursor='hand2', command=self.cargar_historial
                  ).pack(side='left', padx=6)

        # Tabla
        ft = tk.Frame(parent, bg=self.C['content_bg'])
        ft.pack(fill='both', expand=True, padx=8, pady=6)

        cols = ('Fecha', 'Tipo', 'Producto', 'Motivo',
                'Cantidad', 'Stock Antes', 'Stock Después', 'Referencia')
        self.tree_historial = ttk.Treeview(ft, columns=cols,
                                           show='headings', selectmode='browse',
                                           height=20)
        anchos = {'Fecha': 140, 'Tipo': 70, 'Producto': 240,
                  'Motivo': 160, 'Cantidad': 80,
                  'Stock Antes': 90, 'Stock Después': 100, 'Referencia': 120}
        for col in cols:
            anchor = 'e' if col in ('Cantidad', 'Stock Antes', 'Stock Después') else 'w'
            self.tree_historial.heading(col, text=col)
            self.tree_historial.column(col, width=anchos[col], anchor=anchor)

        self.tree_historial.tag_configure('entrada', foreground='#1a6b3a')
        self.tree_historial.tag_configure('salida',  foreground='#c0392b')

        sc_y = ttk.Scrollbar(ft, orient='vertical',
                              command=self.tree_historial.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal',
                              command=self.tree_historial.xview)
        self.tree_historial.configure(yscrollcommand=sc_y.set,
                                      xscrollcommand=sc_x.set)
        self.tree_historial.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

    def cargar_historial(self):
        """Carga el historial de movimientos de stock."""
        self.tree_historial.delete(*self.tree_historial.get_children())

        tipo   = self.var_filtro_tipo.get()
        buscar = self.entry_buscar_hist.get().strip().lower()

        where_parts = []
        params = []

        if tipo == 'Entradas':
            where_parts.append("m.tipo = 'entrada'")
        elif tipo == 'Salidas':
            where_parts.append("m.tipo = 'salida'")

        if buscar:
            where_parts.append("(LOWER(p.nombre) LIKE ? OR LOWER(p.codigo) LIKE ?)")
            params += [f'%{buscar}%', f'%{buscar}%']

        where = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

        self.cursor.execute(f"""
            SELECT m.fecha, m.tipo, p.nombre, m.motivo,
                   m.cantidad, m.stock_antes, m.stock_despues, m.referencia
            FROM movimientos_stock m
            JOIN productos p ON m.producto_id = p.id
            {where}
            ORDER BY m.fecha DESC
            LIMIT 500
        """, params)

        for row in self.cursor.fetchall():
            fecha, tipo_mov, nombre, motivo, cant, s_antes, s_desp, ref = row
            icono = '⬆' if tipo_mov == 'entrada' else '⬇'
            self.tree_historial.insert('', 'end', values=(
                fecha,
                f'{icono} {tipo_mov.capitalize()}',
                nombre,
                motivo or '—',
                f'{cant:g}',
                f'{s_antes:g}',
                f'{s_desp:g}',
                ref or '—',
            ), tags=(tipo_mov,))

    # ── Tab: Análisis ABC ─────────────────────────────────────────────────────
    def _construir_tab_abc(self, parent):
        # Header explicativo
        info = tk.Frame(parent, bg='#eaf0fb', pady=8)
        info.pack(fill='x', padx=8, pady=(8, 4))
        tk.Label(info,
                 text='El análisis ABC clasifica tu inventario por valor económico.\n'
                      'A = 20% de productos que representan el 80% del valor  |  '
                      'B = siguiente 15%  |  C = restante 5%',
                 font=('Arial', 9), bg='#eaf0fb', fg='#1a3a6b',
                 justify='center').pack()

        # Botón calcular
        tk.Button(parent, text='🔄  Calcular Análisis ABC Ahora',
                  font=('Arial', 11, 'bold'),
                  bg='#8e44ad', fg='white', bd=0, padx=20, pady=8,
                  cursor='hand2', command=self._calcular_y_mostrar_abc
                  ).pack(pady=8)

        # Resumen por categoría (3 tarjetas)
        self.frame_tarjetas_abc = tk.Frame(parent, bg=self.C['content_bg'])
        self.frame_tarjetas_abc.pack(fill='x', padx=8, pady=4)
        self.lbl_tarjetas = {}
        for cat, color_fg, color_bg in [
            ('A', COLOR_A, COLOR_A_BG),
            ('B', COLOR_B, COLOR_B_BG),
            ('C', COLOR_C, COLOR_C_BG),
        ]:
            card = tk.LabelFrame(self.frame_tarjetas_abc,
                                 text=f'  Categoría {cat}  ',
                                 font=('Arial', 10, 'bold'),
                                 fg=color_fg, bg=color_bg,
                                 padx=14, pady=8)
            card.pack(side='left', padx=8, fill='x', expand=True)
            lbl = tk.Label(card, text='—\n—\n—',
                           font=('Arial', 9), bg=color_bg, fg='#333',
                           justify='left')
            lbl.pack()
            self.lbl_tarjetas[cat] = lbl

        # Tabla detalle ABC
        ft = tk.Frame(parent, bg=self.C['content_bg'])
        ft.pack(fill='both', expand=True, padx=8, pady=6)

        cols = ('Cat.', 'Código', 'Producto', 'Stock',
                'Costo Prom.', 'Valor Inv.', '% Acumulado')
        self.tree_abc = ttk.Treeview(ft, columns=cols,
                                     show='headings', selectmode='browse')
        anchos = {'Cat.': 50, 'Código': 90, 'Producto': 280, 'Stock': 90,
                  'Costo Prom.': 100, 'Valor Inv.': 110, '% Acumulado': 100}
        for col in cols:
            anchor = 'e' if col not in ('Cat.', 'Código', 'Producto') else 'w'
            self.tree_abc.heading(col, text=col)
            self.tree_abc.column(col, width=anchos[col], anchor=anchor)

        self.tree_abc.tag_configure('cat_a', background=COLOR_A_BG,
                                             foreground=COLOR_A)
        self.tree_abc.tag_configure('cat_b', background=COLOR_B_BG,
                                             foreground=COLOR_B)
        self.tree_abc.tag_configure('cat_c', background=COLOR_C_BG,
                                             foreground=COLOR_C)

        sc_y = ttk.Scrollbar(ft, orient='vertical',
                              command=self.tree_abc.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal',
                              command=self.tree_abc.xview)
        self.tree_abc.configure(yscrollcommand=sc_y.set,
                                xscrollcommand=sc_x.set)
        self.tree_abc.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

    def _calcular_y_mostrar_abc(self):
        """Calcula el ABC y actualiza tanto la tabla ABC como la vista de stock."""
        self.cursor.execute("""
            SELECT p.id, p.codigo, p.nombre, p.stock_actual,
                   COALESCE((SELECT AVG(cd.costo_unitario)
                              FROM compra_detalle cd
                              WHERE cd.producto_id = p.id), 0)
            FROM productos p
            WHERE p.stock_actual > 0
            ORDER BY p.stock_actual * COALESCE(
                   (SELECT AVG(cd.costo_unitario)
                    FROM compra_detalle cd
                    WHERE cd.producto_id = p.id), 0) DESC
        """)
        rows = self.cursor.fetchall()

        if not rows:
            messagebox.showinfo('ABC', 'No hay productos con stock para clasificar.')
            return

        total_valor = sum(r[3] * r[4] for r in rows)
        if total_valor == 0:
            messagebox.showinfo(
                'Sin costos',
                'No hay costos de compra registrados para calcular el valor.\n'
                'El análisis usará las cantidades en stock como criterio.')
            total_valor = sum(r[3] for r in rows)
            usar_cantidad = True
        else:
            usar_cantidad = False

        # Calcular y guardar en cache
        self._abc = {}
        self.tree_abc.delete(*self.tree_abc.get_children())

        conteo = {'A': 0, 'B': 0, 'C': 0}
        valor_cat = {'A': 0.0, 'B': 0.0, 'C': 0.0}
        acum = 0.0

        for pid, codigo, nombre, stock, costo in rows:
            val = stock if usar_cantidad else stock * costo
            acum += val
            pct = (acum / total_valor) * 100 if total_valor else 100

            cat = 'A' if pct <= 80 else ('B' if pct <= 95 else 'C')

            self._abc[pid] = {
                'categoria': cat,
                'valor': val,
                'porcentaje_acum': round(pct, 1),
            }
            conteo[cat] += 1
            valor_cat[cat] += val

            self.tree_abc.insert('', 'end', values=(
                cat,
                codigo or '',
                nombre,
                f'{stock:,.2f}',
                f'${costo:,.2f}',
                f'${val:,.2f}',
                f'{pct:.1f}%',
            ), tags=(f'cat_{cat.lower()}',))

        # Actualizar tarjetas resumen
        total_prods = sum(conteo.values())
        for cat in ('A', 'B', 'C'):
            pct_prods = (conteo[cat] / total_prods * 100) if total_prods else 0
            pct_valor = (valor_cat[cat] / total_valor * 100) if total_valor else 0
            self.lbl_tarjetas[cat].config(
                text=f'{conteo[cat]} productos ({pct_prods:.0f}%)\n'
                     f'Valor: ${valor_cat[cat]:,.2f}\n'
                     f'({pct_valor:.0f}% del total)'
            )

        # Refrescar la vista de stock también
        self.cargar_vista_stock()

        messagebox.showinfo(
            'Análisis ABC completado',
            f'Clasificación actualizada para {total_prods} productos.\n\n'
            f'A: {conteo["A"]} productos  |  '
            f'B: {conteo["B"]} productos  |  '
            f'C: {conteo["C"]} productos'
        )

    # ── Callbacks de pestaña ──────────────────────────────────────────────────
    def _on_tab_cambio(self, event=None):
        tab = self._nb.index(self._nb.select())
        if tab == 0:
            self.cargar_vista_stock()
        elif tab == 1:
            self.cargar_historial()



# ─────────────────────────────────────────────────────────────────────────────
#  VENTANA DE SALIDA DE STOCK (mismo diseño que VentanaCompra)
# ─────────────────────────────────────────────────────────────────────────────

class VentanaSalida:
    """
    Ventana para registrar salidas de stock.
    Diseño y flujo idéntico a VentanaCompra.
    """

    MOTIVOS = [
        'Merma / Daño',
        'Uso interno',
        'Devolución a proveedor',
        'Ajuste de inventario',
        'Muestra / Demo',
        'Pérdida',
        'Otro',
    ]

    def __init__(self, parent, conn, cursor, on_guardar=None):
        self.parent     = parent
        self.conn       = conn
        self.cursor     = cursor
        self.on_guardar = on_guardar
        self.productos_salida = []   # lista de dicts igual que VentanaCompra

        self.ventana = tk.Toplevel(parent)
        self.ventana.title('Nueva Salida de Stock')
        self.ventana.geometry('1000x650')
        self.ventana.transient(parent)
        self.ventana.grab_set()

        self._crear_interfaz()

    # ── Interfaz ──────────────────────────────────────────────────────────────
    def _crear_interfaz(self):
        # ── Frame superior ────────────────────────────────────────────
        frame_sup = tk.LabelFrame(
            self.ventana, text='Información de Salida',
            font=('Arial', 10, 'bold'))
        frame_sup.pack(fill='x', padx=10, pady=10)

        # Fila 1 — Motivo
        fila1 = tk.Frame(frame_sup)
        fila1.pack(fill='x', padx=10, pady=5)

        tk.Label(fila1, text='Motivo:*',
                 font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        self.combo_motivo = ttk.Combobox(
            fila1, values=self.MOTIVOS, width=28,
            state='readonly', font=('Arial', 10))
        self.combo_motivo.current(0)
        self.combo_motivo.pack(side='left', padx=5)

        # Fila 2 — Fecha y Referencia
        fila2 = tk.Frame(frame_sup)
        fila2.pack(fill='x', padx=10, pady=5)

        tk.Label(fila2, text='Fecha y Hora:*',
                 font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        self.entry_fecha = tk.Entry(fila2, width=18, font=('Arial', 10))
        self.entry_fecha.pack(side='left', padx=5)
        self.entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M'))

        tk.Label(fila2, text='Referencia (opcional):',
                 font=('Arial', 10)).pack(side='left', padx=(20, 5))
        self.entry_referencia = tk.Entry(fila2, width=28, font=('Arial', 10))
        self.entry_referencia.pack(side='left', padx=5)

        # ── Frame productos ───────────────────────────────────────────
        frame_prods = tk.LabelFrame(
            self.ventana, text='Productos a Retirar',
            font=('Arial', 10, 'bold'))
        frame_prods.pack(fill='both', expand=True, padx=10, pady=10)

        frame_btn_prod = tk.Frame(frame_prods)
        frame_btn_prod.pack(fill='x', padx=10, pady=5)

        tk.Button(
            frame_btn_prod, text='➕ Agregar Producto',
            command=self._agregar_producto,
            bg='#3498db', fg='white',
            font=('Arial', 9, 'bold'), cursor='hand2',
            padx=10, pady=5
        ).pack(side='left', padx=5)

        tk.Button(
            frame_btn_prod, text='🗑️ Quitar',
            command=self._quitar_producto,
            bg='#e74c3c', fg='white',
            font=('Arial', 9, 'bold'), cursor='hand2',
            padx=10, pady=5
        ).pack(side='left', padx=5)

        # Tabla
        frame_tabla = tk.Frame(frame_prods)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=5)

        self.tree = ttk.Treeview(
            frame_tabla,
            columns=('Código', 'Producto', 'Stock Disp.', 'Cantidad', 'Unidad'),
            show='headings', height=8)

        cfg = {'Código': 80, 'Producto': 320,
               'Stock Disp.': 100, 'Cantidad': 100, 'Unidad': 80}
        for col, w in cfg.items():
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w,
                             anchor='e' if col in ('Stock Disp.', 'Cantidad') else 'w')

        sc = ttk.Scrollbar(frame_tabla, orient='vertical',
                           command=self.tree.yview)
        self.tree.configure(yscrollcommand=sc.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sc.pack(side='right', fill='y')

        # Total de unidades
        frame_tot = tk.Frame(frame_prods, bg='#ecf0f1')
        frame_tot.pack(fill='x', padx=10, pady=10)
        tk.Label(frame_tot, text='TOTAL UNIDADES:', bg='#ecf0f1',
                 font=('Arial', 13, 'bold')).pack(side='right', padx=5)
        self.lbl_total = tk.Label(frame_tot, text='0', bg='#ecf0f1',
                                   font=('Arial', 13, 'bold'), fg='#e74c3c')
        self.lbl_total.pack(side='right', padx=5)

        # ── Notas ─────────────────────────────────────────────────────
        frame_notas = tk.Frame(self.ventana)
        frame_notas.pack(fill='x', padx=10, pady=5)
        tk.Label(frame_notas, text='Notas:',
                 font=('Arial', 10)).pack(anchor='w')
        self.text_notas = tk.Text(frame_notas, height=2, font=('Arial', 9))
        self.text_notas.pack(fill='x')

        # ── Botones ───────────────────────────────────────────────────
        frame_btn = tk.Frame(self.ventana)
        frame_btn.pack(fill='x', padx=10, pady=10)

        tk.Button(
            frame_btn, text='💾  Registrar Salida',
            command=self._guardar,
            bg='#e74c3c', fg='white',
            font=('Arial', 11, 'bold'), cursor='hand2',
            padx=20, pady=10
        ).pack(side='left', padx=5)

        tk.Button(
            frame_btn, text='❌  Cancelar',
            command=self.ventana.destroy,
            bg='#95a5a6', fg='white',
            font=('Arial', 11, 'bold'), cursor='hand2',
            padx=20, pady=10
        ).pack(side='left', padx=5)

    # ── Agregar producto ──────────────────────────────────────────────────────
    def _agregar_producto(self):
        win = tk.Toplevel(self.ventana)
        win.title('Seleccionar Producto')
        win.geometry('800x500')
        win.transient(self.ventana)
        win.grab_set()

        # Búsqueda
        fb = tk.Frame(win)
        fb.pack(fill='x', padx=10, pady=10)
        tk.Label(fb, text='Buscar:', font=('Arial', 10)).pack(side='left', padx=5)
        entry_buscar = tk.Entry(fb, width=40, font=('Arial', 10))
        entry_buscar.pack(side='left', padx=5)

        # Tabla
        ft = tk.Frame(win)
        ft.pack(fill='both', expand=True, padx=10, pady=5)
        tree = ttk.Treeview(
            ft,
            columns=('ID', 'Código', 'Nombre', 'Stock Actual', 'Unidad'),
            show='headings', selectmode='browse')
        for col, w in [('ID',50),('Código',100),
                       ('Nombre',360),('Stock Actual',110),('Unidad',80)]:
            tree.heading(col, text=col)
            tree.column(col, width=w,
                        anchor='e' if col == 'Stock Actual' else 'w')
        sc = ttk.Scrollbar(ft, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sc.set)
        tree.pack(side='left', fill='both', expand=True)
        sc.pack(side='right', fill='y')

        def _cargar(buscar=''):
            tree.delete(*tree.get_children())
            if buscar:
                self.cursor.execute("""
                    SELECT id, codigo, nombre, stock_actual, unidad_medida
                    FROM productos
                    WHERE codigo LIKE ? OR nombre LIKE ?
                    ORDER BY nombre
                """, (f'%{buscar}%', f'%{buscar}%'))
            else:
                self.cursor.execute("""
                    SELECT id, codigo, nombre, stock_actual, unidad_medida
                    FROM productos ORDER BY nombre
                """)
            for r in self.cursor.fetchall():
                tree.insert('', 'end', values=(
                    r[0], r[1] or '', r[2],
                    f'{r[3]:,.2f}', r[4] or ''))

        entry_buscar.bind('<KeyRelease>', lambda e: _cargar(entry_buscar.get()))
        _cargar()

        # Cantidad
        fd = tk.Frame(win)
        fd.pack(fill='x', padx=10, pady=10)
        tk.Label(fd, text='Cantidad a retirar:*',
                 font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        entry_cant = tk.Entry(fd, width=12, font=('Arial', 10))
        entry_cant.pack(side='left', padx=5)
        entry_cant.insert(0, '1')

        # Botones
        def _agregar():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning('Advertencia', 'Selecciona un producto.',
                                       parent=win)
                return
            try:
                cantidad = float(entry_cant.get())
                if cantidad <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning('Advertencia',
                                       'Ingresa una cantidad válida.', parent=win)
                return

            vals = tree.item(sel[0])['values']
            pid, codigo, nombre = vals[0], vals[1], vals[2]
            stock_disp = float(str(vals[3]).replace(',', ''))
            unidad     = vals[4]

            if cantidad > stock_disp:
                resp = messagebox.askyesno(
                    'Stock insuficiente',
                    f'La cantidad ({cantidad:g}) supera el stock disponible '
                    f'({stock_disp:g}).\n\n'
                    '\u00bfPermitir stock negativo?',
                    parent=win)
                if not resp:
                    return

            self.productos_salida.append({
                'producto_id': pid,
                'codigo': codigo,
                'nombre': nombre,
                'cantidad': cantidad,
                'stock_disp': stock_disp,
                'unidad': unidad,
            })
            self._actualizar_tabla()
            win.destroy()

        fb2 = tk.Frame(win)
        fb2.pack(fill='x', padx=10, pady=10)
        tk.Button(fb2, text='➕ Agregar', command=_agregar,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=8).pack(side='left', padx=5)
        tk.Button(fb2, text='❌ Cancelar', command=win.destroy,
                  bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=8).pack(side='left', padx=5)

    def _quitar_producto(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('Advertencia', 'Selecciona un producto.')
            return
        codigo = self.tree.item(sel[0])['values'][0]
        self.productos_salida = [p for p in self.productos_salida
                                  if p['codigo'] != codigo]
        self._actualizar_tabla()

    def _actualizar_tabla(self):
        self.tree.delete(*self.tree.get_children())
        total_units = 0
        for p in self.productos_salida:
            self.tree.insert('', 'end', values=(
                p['codigo'], p['nombre'],
                f"{p['stock_disp']:,.2f}",
                f"{p['cantidad']:,.2f}",
                p['unidad']))
            total_units += p['cantidad']
        self.lbl_total.config(text=f'{total_units:,.2f}')

    # ── Guardar ───────────────────────────────────────────────────────────────
    def _guardar(self):
        if not self.productos_salida:
            messagebox.showwarning('Advertencia', 'Agrega al menos un producto.')
            return

        motivo     = self.combo_motivo.get()
        fecha      = self.entry_fecha.get().strip()
        referencia = self.entry_referencia.get().strip()
        notas      = self.text_notas.get('1.0', 'end-1c').strip()

        resumen = '\n'.join(
            f"  • {p['nombre']}: {p['cantidad']:g} {p['unidad']}"
            for p in self.productos_salida)
        if not messagebox.askyesno(
            'Confirmar salida',
            f'Motivo: {motivo}\n\nProductos a retirar:\n{resumen}\n\n'
                '¿Confirmar salida de stock?'):
            return

        try:
            for p in self.productos_salida:
                self.cursor.execute(
                    'SELECT stock_actual FROM productos WHERE id = ?',
                    (p['producto_id'],))
                row = self.cursor.fetchone()
                stock_antes = row[0] if row else 0
                stock_nuevo = stock_antes - p['cantidad']

                # Actualizar stock
                self.cursor.execute(
                    'UPDATE productos SET stock_actual = ? WHERE id = ?',
                    (stock_nuevo, p['producto_id']))

                # Registrar movimiento
                self.cursor.execute("""
                    INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad,
                     stock_antes, stock_despues, referencia, notas, fecha)
                    VALUES (?, 'salida', ?, ?, ?, ?, ?, ?, ?)
                """, (p['producto_id'], motivo, p['cantidad'],
                      stock_antes, stock_nuevo,
                      referencia or None, notas or None, fecha))

            self.conn.commit()
            messagebox.showinfo('Éxito', 'Salida registrada y stock actualizado.')

            if self.on_guardar:
                self.on_guardar()
            self.ventana.destroy()

        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror('Error', f'No se pudo guardar:\n{e}')

# ─────────────────────────────────────────────────────────────────────────────
#  REGISTRO AUTOMÁTICO DE ENTRADAS (hook para compras)
# ─────────────────────────────────────────────────────────────────────────────

def registrar_entrada_movimiento(cursor, conn, producto_id, cantidad,
                                  stock_antes, folio_compra=''):
    """
    Registra automáticamente una entrada en movimientos_stock.
    Llamar desde compras.py después de actualizar el stock.
    """
    stock_despues = stock_antes + cantidad
    cursor.execute("""
        INSERT INTO movimientos_stock
        (producto_id, tipo, motivo, cantidad,
         stock_antes, stock_despues, referencia)
        VALUES (?, 'entrada', 'Compra', ?, ?, ?, ?)
    """, (producto_id, cantidad, stock_antes, stock_despues,
          folio_compra or None))
    conn.commit()
