#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Gestión Comercial
Comercializadora, Logística y Fuerza Yucateca
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
from datetime import datetime
import os
from modules.cotizaciones import VentanaCotizacion
from modules.entregas import VentanaEntregaParcial
from ui.generador_pdf_cly import GeneradorPDFCLY
from ui.dialogo_impresion import DialogoImpresion
from modules.stock import SeccionStock
from modules.compras import VentanaCompra
from modules.estado_de_cuenta import VentanaEstadoCuenta
from modules.facturacion import SeccionFacturacion
from modules.vinculacion import PanelVinculacion, detectar_pendientes
from selector_empresa import mostrar_selector, cargar_config, guardar_config
from db_init import inicializar_bd
from ui.dashboard import Dashboard

# Información de la empresa activa (se llena al seleccionar empresa al arrancar)
EMPRESA = {
    'nombre': '',
    'rfc':    '',
    'email':  '',
    'telefono': '',
    'direccion': '',
}

# Porcentajes de utilidad por tipo de cliente
UTILIDAD = {
    'Gobierno': 40,
    'Hotel': 35
}

class SistemaGestion:
    def __init__(self, root, empresa=None):
        self.root    = root
        self.empresa = empresa or {}

        # Actualizar dict global EMPRESA con los datos de la empresa activa
        global EMPRESA
        if empresa:
            EMPRESA.update({
                'nombre':    empresa.get('nombre', ''),
                'rfc':       empresa.get('rfc', ''),
                'email':     empresa.get('email', ''),
                'telefono':  empresa.get('telefono', ''),
                'direccion': empresa.get('direccion', ''),
            })

        titulo = f"Sistema de Gestión — {empresa['nombre']}" if empresa else "Sistema de Gestión - CLF"
        self.root.title(titulo)
        self.root.geometry("1200x700")

        # Inicializar base de datos (usa la ruta de la empresa seleccionada)
        self.init_database(empresa.get('db_path') if empresa else None)

        # Crear interfaz
        self.crear_interfaz()
    
    def _configurar_sorting_treeview(self, tree, columnas_numericas=None):
        """
        Configura ordenamiento por click en headers de columnas.
        
        Args:
            tree: ttk.Treeview widget
            columnas_numericas: lista de nombres de columnas que contienen números/montos
                                (se ordenarán numéricamente, no alfabéticamente)
        """
        if columnas_numericas is None:
            columnas_numericas = []
        
        # Estado de ordenamiento por columna (False=ascendente, True=descendente)
        self._sort_states = {}
        
        def ordenar_por_columna(col):
            # Alternar entre ascendente/descendente
            reverse = self._sort_states.get(col, False)
            self._sort_states[col] = not reverse
            
            # Obtener todos los items
            items = [(tree.set(k, col), k) for k in tree.get_children('')]
            
            # Ordenar
            if col in columnas_numericas:
                # Ordenamiento numérico
                def extraer_numero(texto):
                    try:
                        # Quitar símbolos de moneda, comas, espacios
                        limpio = str(texto).replace('$', '').replace(',', '').replace(' ', '')
                        # Extraer el primer número que encuentre
                        import re
                        match = re.search(r'-?\d+\.?\d*', limpio)
                        if match:
                            return float(match.group())
                        return 0
                    except:
                        return 0
                
                items.sort(key=lambda t: extraer_numero(t[0]), reverse=reverse)
            else:
                # Ordenamiento alfabético (case-insensitive)
                items.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)
            
            # Reordenar items en el tree
            for index, (val, k) in enumerate(items):
                tree.move(k, '', index)
            
            # Actualizar indicador visual en header
            indicador = ' ▼' if reverse else ' ▲'
            
            # Limpiar indicadores de otras columnas
            for c in tree['columns']:
                texto_actual = str(tree.heading(c)['text'])
                texto_limpio = texto_actual.replace(' ▲', '').replace(' ▼', '')
                if c == col:
                    tree.heading(c, text=texto_limpio + indicador)
                else:
                    tree.heading(c, text=texto_limpio)
        
        # Configurar click en cada header
        for col in tree['columns']:
            tree.heading(col, command=lambda c=col: ordenar_por_columna(c))
        
        return tree
    
    def init_database(self, db_path=None):
        """Inicializa la base de datos SQLite.
        Delega la creación de tablas a db_init.inicializar_bd() para que
        main.py y selector_empresa compartan exactamente el mismo esquema.
        """
        ruta = db_path or 'gestion_comercial.db'
        self.conn, self.cursor = inicializar_bd(ruta)

    def crear_interfaz(self):
        """Crea la interfaz principal estilo ERP compacto"""

        # ── Paleta de colores ──────────────────────────────────────────────
        self.C = {
            'nav_bg':     '#1e2d45',
            'nav_active': '#eceff4',
            'nav_hover':  '#2b3a55',
            'nav_text':   '#94a3b8',
            'nav_active_text': '#1e2d45',
            'kpi_bg':     '#f7f9fc',
            'kpi_border': '#d0d7e4',
            'toolbar_bg': '#d8dde8',
            'toolbar_border': '#c5ccd8',
            'content_bg': '#eceff4',
            'card_bg':    'white',
            'accent':     '#0f7b5e',
            'accent2':    '#1a4b8c',
            'warn':       '#d97706',
            'danger':     '#c0392b',
            'text_dark':  '#1e2d45',
            'text_muted': '#6b7e99',
        }

        # ── Barra de navegación superior ───────────────────────────────────
        nav = tk.Frame(self.root, bg=self.C['nav_bg'], height=38)
        nav.pack(fill='x')
        nav.pack_propagate(False)

        # Logo / marca
        logo_frame = tk.Frame(nav, bg='#141f30', padx=14)
        logo_frame.pack(side='left', fill='y')
        tk.Label(logo_frame, text='⚙  GESTIÓN', font=('Arial', 10, 'bold'),
                 bg='#141f30', fg='#1aab82').pack(side='left', anchor='center')

        # Separador
        tk.Frame(nav, bg='#141f30', width=1).pack(side='left', fill='y')

        # Botones de navegación
        self._nav_botones = {}
        self._seccion_actual = tk.StringVar(value='dashboard')

        secciones = [
            ('dashboard',   '📊  Dashboard'),
            ('cotizaciones','📄  Cotizaciones'),
            ('facturacion', '🧾  Facturación'),
            ('catalogos',   '📚  Catálogos'),
            ('stock',       '📦  Stock'),
        ]

        for key, texto in secciones:
            btn = tk.Button(
                nav, text=texto,
                font=('Arial', 9, 'bold'),
                bg=self.C['nav_bg'], fg=self.C['nav_text'],
                activebackground=self.C['nav_hover'], activeforeground='white',
                bd=0, padx=14, pady=0,
                cursor='hand2', relief='flat',
                command=lambda k=key: self._navegar(k)
            )
            btn.pack(side='left', fill='y')
            self._nav_botones[key] = btn

        # Badge de alertas en nav
        self._badge_cot = tk.Label(nav, text='', font=('Arial', 8, 'bold'),
                                    bg='#c0392b', fg='white',
                                    padx=4, pady=0)
        # se posiciona dinámicamente junto al botón cotizaciones

        # ── Lado derecho: empresa activa + botón cambiar ───────────────────
        btn_cambiar = tk.Button(
            nav, text='⇄  Cambiar empresa',
            font=('Arial', 8), bg='#141f30', fg='#64748b',
            activebackground='#1e2d45', activeforeground='#94a3b8',
            bd=0, padx=10, pady=0, cursor='hand2', relief='flat',
            command=self._cambiar_empresa
        )
        btn_cambiar.pack(side='right', fill='y', padx=(0, 4))

        nombre_emp = self.empresa.get('nombre', '') if self.empresa else ''
        if nombre_emp:
            # Truncar si es muy largo
            display = nombre_emp if len(nombre_emp) <= 32 else nombre_emp[:30] + '…'
            tk.Label(nav, text=f'🏢  {display}',
                     font=('Arial', 8), bg=self.C['nav_bg'],
                     fg='#475569').pack(side='right', padx=(0, 6), pady=0)

        # ── Área de contenido ──────────────────────────────────────────────
        self._content_area = tk.Frame(self.root, bg=self.C['content_bg'])
        self._content_area.pack(fill='both', expand=True)

        # Crear todas las secciones (frames apilados)
        self._secciones = {}
        self.dashboard = Dashboard(self)
        self.dashboard.crear_seccion()
        self._crear_seccion_cotizaciones()
        self._crear_seccion_catalogos()
        self._facturacion = SeccionFacturacion(self)
        self._stock = SeccionStock(self)

        # Mostrar dashboard al inicio
        self._navegar('dashboard')
        self.actualizar_dashboard()

    def actualizar_dashboard(self):
        """Delega al componente Dashboard."""
        if hasattr(self, 'dashboard'):
            self.dashboard.actualizar_dashboard()

    def _navegar(self, seccion):
        """Muestra la sección seleccionada, actualiza botones y refresca datos"""
        self._seccion_actual.set(seccion)

        # Ocultar todas las secciones
        for f in self._secciones.values():
            f.pack_forget()

        # Mostrar la seleccionada
        self._secciones[seccion].pack(fill='both', expand=True)

        # Actualizar estilos de botones
        for key, btn in self._nav_botones.items():
            if key == seccion:
                btn.config(bg=self.C['nav_active'],
                           fg=self.C['nav_active_text'])
            else:
                btn.config(bg=self.C['nav_bg'],
                           fg=self.C['nav_text'])

        # ── Refrescar datos de la sección al navegar ───────────────────────
        try:
            if seccion == 'dashboard':
                self.actualizar_dashboard()
            elif seccion == 'cotizaciones':
                self.cargar_cotizaciones()
                self.actualizar_dashboard()
            elif seccion == 'facturacion':
                if hasattr(self, '_facturacion'):
                    self._facturacion.cargar_facturas()
            elif seccion == 'catalogos':
                self.cargar_clientes()
                self.cargar_productos()
                self.cargar_proveedores()
                self.cargar_compras()
            elif seccion == 'stock':
                # SeccionStock tiene su propio Notebook con evento de cambio de pestaña;
                # actualizamos la vista de stock y el historial directamente.
                if hasattr(self, '_stock'):
                    self._stock.cargar_vista_stock()
                    self._stock.cargar_historial()
        except Exception:
            pass  # Nunca bloquear la navegación por un error de recarga

    def _toolbar_sep(self, parent):
        """Inserta un separador vertical en el toolbar"""
        tk.Frame(parent, bg=self.C['toolbar_border'],
                 width=1).pack(side='left', fill='y', pady=4, padx=4)

    def _toolbar_btn(self, parent, texto, comando, color=None, peligro=False):
        """Botón estilo toolbar ERP"""
        bg = color or self.C['toolbar_bg']
        fg = 'white' if color else self.C['text_dark']
        if peligro:
            bg, fg = self.C['danger'], 'white'
        b = tk.Button(
            parent, text=texto,
            command=comando,
            font=('Arial', 9),
            bg=bg, fg=fg,
            activebackground=self.C['nav_hover'], activeforeground='white',
            bd=1, relief='raised',
            cursor='hand2', padx=8, pady=3
        )
        b.pack(side='left', padx=2, pady=3)
        return b

    def _toolbar_menu(self, parent, texto, opciones, color=None):
        """Menubutton estilo toolbar"""
        bg = color or self.C['toolbar_bg']
        fg = 'white' if color else self.C['text_dark']
        mb = tk.Menubutton(
            parent, text=texto,
            font=('Arial', 9),
            bg=bg, fg=fg,
            activebackground=self.C['nav_hover'], activeforeground='white',
            bd=1, relief='raised',
            cursor='hand2', padx=8, pady=3
        )
        mb.pack(side='left', padx=2, pady=3)
        menu = tk.Menu(mb, tearoff=0)
        mb['menu'] = menu
        for item in opciones:
            if item is None:
                menu.add_separator()
            else:
                lbl, cmd = item
                menu.add_command(label=lbl, command=cmd)
        return mb

    # ── SECCIÓN: COTIZACIONES ──────────────────────────────────────────────
    def _crear_seccion_cotizaciones(self):
        sec = tk.Frame(self._content_area, bg=self.C['content_bg'])
        self._secciones['cotizaciones'] = sec

        # Toolbar principal
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], relief='flat', bd=0)
        tb.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        self._toolbar_btn(tb, '➕ Nueva', self.nueva_cotizacion, color=self.C['accent'])
        self._toolbar_btn(tb, '✏️ Editar', self.editar_cotizacion)
        self._toolbar_sep(tb)
        self._toolbar_menu(tb, '📄 PDF ▾', [
            ('Cotización PDF', self.generar_pdf_cotizacion_nueva),
            ('Nota de Remisión', self.generar_nota_remision),
        ])
        self._toolbar_sep(tb)
        self._toolbar_menu(tb, '📋 Estado ▾', [
            ('Pendiente',               lambda: self.cambiar_estado_rapido('Pendiente')),
            ('Programada',              lambda: self.cambiar_estado_rapido('Programada')),
            ('Entregada (completa)',     self.marcar_entregada_completa),
            ('Entrega parcial',          self.marcar_entregada_parcial),
            None,
            ('Cancelar',                self.cancelar_cotizacion),
        ])
        self._toolbar_sep(tb)
        self._toolbar_btn(tb, '📋 Seguimiento', self.ver_seguimiento_cotizacion, color='#7c3aed')
        self._toolbar_sep(tb)
        self._toolbar_btn(tb, '📊 Estado de Cuenta', self.ver_estado_cuenta, color='#0e7490')
        self._toolbar_sep(tb)
        self._btn_vincular = self._toolbar_btn(tb, '🔗 Vincular', self._abrir_centro_vinculacion, color='#7c3aed')
        self._actualizar_badge_vinculacion()

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
        self._toolbar_btn(ff, '🔄', self.cargar_cotizaciones)

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
        self._configurar_sorting_treeview(
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
            self._panel_vinculacion = PanelVinculacion(self)
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

    def _ventana_producto_prefill(self, datos, callback=None):
        """Abre la ventana de nuevo producto pre-llenada con datos del XML."""
        import tkinter as tk
        from tkinter import ttk, messagebox
        ventana = tk.Toplevel(self.root)
        ventana.title('Nuevo Producto (desde XML)')
        ventana.geometry('520x480')
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()

        hdr = tk.Frame(ventana, bg='#065f46', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='📦  Nuevo Producto — Datos pre-llenados desde XML',
                 font=('Arial', 10, 'bold'), bg='#065f46', fg='white').pack(side='left', padx=12)

        frame = tk.Frame(ventana, padx=20, pady=16, bg='#f1f5f9')
        frame.pack(fill='both', expand=True)
        frame.grid_columnconfigure(1, weight=1)

        def lrow(r, lbl, entry_w):
            tk.Label(frame, text=lbl, font=('Arial', 9, 'bold'),
                     bg='#f1f5f9', fg='#374151', anchor='e').grid(
                row=r, column=0, sticky='e', padx=(0, 8), pady=5)
            entry_w.grid(row=r, column=1, sticky='ew', pady=5)

        e_codigo = tk.Entry(frame, font=('Arial', 9))
        e_codigo.insert(0, datos.get('codigo', ''))
        lrow(0, 'Código:', e_codigo)

        e_nombre = tk.Entry(frame, font=('Arial', 9))
        e_nombre.insert(0, datos.get('nombre', ''))
        lrow(1, 'Nombre:', e_nombre)

        e_precio = tk.Entry(frame, font=('Arial', 9))
        precio_val = datos.get('precio_venta', 0)
        e_precio.insert(0, f'{precio_val:.2f}' if precio_val else '')
        lrow(2, 'Precio Venta:', e_precio)

        # Unidad
        try:
            self.cursor.execute('SELECT nombre FROM unidades_medida ORDER BY nombre')
            unids = [r[0] for r in self.cursor.fetchall()]
        except Exception:
            unids = []
        unids = unids or ['PZA', 'KG', 'LT', 'M2', 'SERVICIO', 'H', 'M', 'ML']
        c_unidad = ttk.Combobox(frame, values=unids, font=('Arial', 9), width=18)
        lrow(3, 'Unidad:', c_unidad)

        e_clave_sat = tk.Entry(frame, font=('Arial', 9))
        e_clave_sat.insert(0, datos.get('clave_sat', ''))
        lrow(4, 'Clave SAT:', e_clave_sat)

        e_clave_uni = tk.Entry(frame, font=('Arial', 9))
        e_clave_uni.insert(0, datos.get('clave_unidad_sat', ''))
        lrow(5, 'Clave Unidad SAT:', e_clave_uni)

        # Categoria
        self.cursor.execute('SELECT id, nombre FROM categorias ORDER BY nombre')
        cats = self.cursor.fetchall()
        cat_opts = [f"{cid}|{cn}" for cid, cn in cats]
        c_cat = ttk.Combobox(frame, values=[cn for _, cn in cats],
                              font=('Arial', 9), state='readonly')
        lrow(6, 'Categoría:', c_cat)

        tk.Label(frame, text='IVA %:', font=('Arial', 9, 'bold'),
                 bg='#f1f5f9', fg='#374151', anchor='e').grid(
            row=7, column=0, sticky='e', padx=(0, 8), pady=5)
        c_iva = ttk.Combobox(frame, values=['0', '8', '16'],
                              font=('Arial', 9), state='readonly', width=8)
        c_iva.set('16')
        c_iva.grid(row=7, column=1, sticky='w', pady=5)

        foot = tk.Frame(ventana, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')

        def guardar(event=None):
            codigo = e_codigo.get().strip()
            nombre = e_nombre.get().strip()
            if not codigo or not nombre:
                messagebox.showwarning('Advertencia',
                    'Código y Nombre son obligatorios.', parent=ventana)
                return
            try:
                precio = float(e_precio.get().strip() or 0)
            except ValueError:
                precio = 0
            iva_pct = float(c_iva.get() or 16) / 100
            precio_base = round(precio / (1 + iva_pct), 2) if iva_pct else precio

            # Obtener categoria_id
            cat_nombre = c_cat.get()
            cat_id = None
            if cat_nombre:
                self.cursor.execute('SELECT id FROM categorias WHERE nombre=?', (cat_nombre,))
                cr = self.cursor.fetchone()
                cat_id = cr[0] if cr else None

            try:
                self.cursor.execute("""
                    INSERT INTO productos
                    (codigo, nombre, categoria_id, unidad_medida, precio_base,
                     aplica_iva, precio_venta, clave_sat, clave_unidad_sat)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (codigo, nombre, cat_id, c_unidad.get(),
                      precio_base, 1 if float(c_iva.get() or 0) > 0 else 0,
                      precio, e_clave_sat.get().strip() or None,
                      e_clave_uni.get().strip() or None))
                self.conn.commit()
                new_id = self.cursor.lastrowid
                self.cargar_productos()
                ventana.destroy()
                if callback:
                    callback(new_id)
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror('Error', str(e), parent=ventana)

        ventana.bind('<Return>', guardar)
        tk.Button(foot, text='💾 Guardar', command=guardar,
                  bg='#065f46', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=12)
        tk.Button(foot, text='Cancelar', command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='right', padx=12)
        e_nombre.focus()

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
    def _crear_seccion_catalogos(self):
        sec = tk.Frame(self._content_area, bg=self.C['content_bg'])
        self._secciones['catalogos'] = sec

        nb = ttk.Notebook(sec)
        nb.pack(fill='both', expand=True)

        # ── Tab Clientes ──────────────────────────────────────────────────
        tab_cli = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_cli, text='👥  Clientes')

        tb_cli = tk.Frame(tab_cli, bg=self.C['toolbar_bg'])
        tb_cli.pack(fill='x')
        tk.Frame(tab_cli, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self._toolbar_btn(tb_cli, '➕ Nuevo',    self.nuevo_cliente,   color=self.C['accent'])
        self._toolbar_btn(tb_cli, '✏️ Editar',   self.editar_cliente)
        self._toolbar_btn(tb_cli, '🗑️ Eliminar', self.eliminar_cliente, peligro=True)

        ff_cli = tk.Frame(tab_cli, bg=self.C['toolbar_bg'], pady=4)
        ff_cli.pack(fill='x')
        tk.Label(ff_cli, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_cliente = tk.Entry(ff_cli, font=('Arial', 9), width=30)
        self.entry_buscar_cliente.pack(side='left', padx=4)
        self.entry_buscar_cliente.bind('<Return>', lambda e: self.cargar_clientes())
        self._toolbar_btn(ff_cli, '🔍', self.cargar_clientes)

        ft_cli = tk.Frame(tab_cli, bg=self.C['content_bg'])
        ft_cli.pack(fill='both', expand=True, padx=8, pady=8)
        cols_cli = ('ID', 'Nombre Comercial', 'Razón Social', 'Tipo',
                    'RFC', 'Régimen Fiscal', 'Uso CFDI', 'CP Fiscal',
                    'Contacto', 'Teléfono', 'Email')
        self.tree_clientes = ttk.Treeview(
            ft_cli, columns=cols_cli, show='headings', selectmode='browse')
        for col, w in zip(cols_cli, [0, 180, 160, 80, 110, 160, 80, 75, 120, 100, 160]):
            self.tree_clientes.heading(col, text=col)
            self.tree_clientes.column(col, width=w, minwidth=w)
        self.tree_clientes.column('ID', stretch=False)
        sc = ttk.Scrollbar(ft_cli, orient='vertical',   command=self.tree_clientes.yview)
        sx = ttk.Scrollbar(ft_cli, orient='horizontal', command=self.tree_clientes.xview)
        self.tree_clientes.configure(yscrollcommand=sc.set, xscrollcommand=sx.set)
        self.tree_clientes.grid(row=0, column=0, sticky='nsew')
        sc.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        ft_cli.grid_rowconfigure(0, weight=1)
        ft_cli.grid_columnconfigure(0, weight=1)
        self.tree_clientes.bind('<Double-1>', lambda e: self.editar_cliente())
        self._configurar_sorting_treeview(self.tree_clientes)
        self.cargar_clientes()

        # ── Tab Productos ─────────────────────────────────────────────────
        tab_prod = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_prod, text='📦  Productos')

        tb_prod = tk.Frame(tab_prod, bg=self.C['toolbar_bg'])
        tb_prod.pack(fill='x')
        tk.Frame(tab_prod, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self._toolbar_btn(tb_prod, '➕ Nuevo',      self.nuevo_producto,    color=self.C['accent'])
        self._toolbar_btn(tb_prod, '✏️ Editar',     self.editar_producto)
        self._toolbar_btn(tb_prod, '🗑️ Eliminar',   self.eliminar_producto,  peligro=True)
        self._toolbar_sep(tb_prod)
        self._toolbar_btn(tb_prod, '📋 Categorías', self.gestionar_categorias)

        ff_prod = tk.Frame(tab_prod, bg=self.C['toolbar_bg'], pady=4)
        ff_prod.pack(fill='x')
        tk.Label(ff_prod, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_producto = tk.Entry(ff_prod, font=('Arial', 9), width=30)
        self.entry_buscar_producto.pack(side='left', padx=4)
        self.entry_buscar_producto.bind('<Return>', lambda e: self.cargar_productos())
        self._toolbar_btn(ff_prod, '🔍', self.cargar_productos)

        ft_prod = tk.Frame(tab_prod, bg=self.C['content_bg'])
        ft_prod.pack(fill='both', expand=True, padx=8, pady=8)
        cols_prod = ('ID', 'Código', 'Nombre', 'Categoría', 'Subcategoría',
                     'Unidad', 'Precio Base', 'IVA', 'Precio Venta',
                     'Stock', 'Stock Mín', 'Clave SAT', 'Proveedores')
        self.tree_productos = ttk.Treeview(
            ft_prod, columns=cols_prod, show='headings', selectmode='browse')
        for col, w in zip(cols_prod,
                          [0, 80, 200, 110, 110, 60, 90, 50, 90, 70, 70, 90, 140]):
            self.tree_productos.heading(col, text=col)
            self.tree_productos.column(col, width=w, minwidth=w)
        self.tree_productos.column('ID', stretch=False)
        sc = ttk.Scrollbar(ft_prod, orient='vertical',   command=self.tree_productos.yview)
        sx = ttk.Scrollbar(ft_prod, orient='horizontal', command=self.tree_productos.xview)
        self.tree_productos.configure(yscrollcommand=sc.set, xscrollcommand=sx.set)
        self.tree_productos.grid(row=0, column=0, sticky='nsew')
        sc.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        ft_prod.grid_rowconfigure(0, weight=1)
        ft_prod.grid_columnconfigure(0, weight=1)
        self.tree_productos.bind('<Double-1>', lambda e: self.editar_producto())
        self._configurar_sorting_treeview(self.tree_productos,
            columnas_numericas=['Precio Base', 'Precio Venta', 'Stock', 'Stock Mín'])
        self.cargar_productos()

        # ── Tab Proveedores ───────────────────────────────────────────────
        tab_prov = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_prov, text='🏭  Proveedores')

        tb_prov = tk.Frame(tab_prov, bg=self.C['toolbar_bg'])
        tb_prov.pack(fill='x')
        tk.Frame(tab_prov, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self._toolbar_btn(tb_prov, '➕ Nuevo',    self.nuevo_proveedor,   color=self.C['accent'])
        self._toolbar_btn(tb_prov, '✏️ Editar',   self.editar_proveedor)
        self._toolbar_btn(tb_prov, '🗑️ Eliminar', self.eliminar_proveedor, peligro=True)
        self._toolbar_sep(tb_prov)
        self._toolbar_btn(tb_prov, '🛒 Presupuesto Compra', self.generar_presupuesto_compra)

        ff_prov = tk.Frame(tab_prov, bg=self.C['toolbar_bg'], pady=4)
        ff_prov.pack(fill='x')
        tk.Label(ff_prov, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_proveedor = tk.Entry(ff_prov, font=('Arial', 9), width=30)
        self.entry_buscar_proveedor.pack(side='left', padx=4)
        self.entry_buscar_proveedor.bind('<Return>', lambda e: self.cargar_proveedores())
        self._toolbar_btn(ff_prov, '🔍', self.cargar_proveedores)

        ft_prov = tk.Frame(tab_prov, bg=self.C['content_bg'])
        ft_prov.pack(fill='both', expand=True, padx=8, pady=8)
        cols_prov = ('ID', 'Nombre', 'RFC', 'Régimen Fiscal', 'C.P. Fiscal',
                     'Contacto', 'Teléfono', 'Email', 'Notas')
        self.tree_proveedores = ttk.Treeview(
            ft_prov, columns=cols_prov, show='headings', selectmode='browse')
        for col, w in zip(cols_prov, [0, 180, 110, 160, 75, 120, 100, 160, 180]):
            self.tree_proveedores.heading(col, text=col)
            self.tree_proveedores.column(col, width=w, minwidth=w)
        self.tree_proveedores.column('ID', stretch=False)
        sc = ttk.Scrollbar(ft_prov, orient='vertical',   command=self.tree_proveedores.yview)
        sx = ttk.Scrollbar(ft_prov, orient='horizontal', command=self.tree_proveedores.xview)
        self.tree_proveedores.configure(yscrollcommand=sc.set, xscrollcommand=sx.set)
        self.tree_proveedores.grid(row=0, column=0, sticky='nsew')
        sc.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        ft_prov.grid_rowconfigure(0, weight=1)
        ft_prov.grid_columnconfigure(0, weight=1)
        self.tree_proveedores.bind('<Double-1>', lambda e: self.editar_proveedor())
        self._configurar_sorting_treeview(self.tree_proveedores)
        self.cargar_proveedores()

        # ── Tab Compras ───────────────────────────────────────────────────
        tab_comp = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_comp, text='🛒  Compras')

        tb_comp = tk.Frame(tab_comp, bg=self.C['toolbar_bg'])
        tb_comp.pack(fill='x')
        tk.Frame(tab_comp, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self._toolbar_btn(tb_comp, '➕ Nueva',       self.nueva_compra, color=self.C['accent'])
        self._toolbar_btn(tb_comp, '🔍 Ver Detalle',  self.ver_compra)
        self._toolbar_btn(tb_comp, '✏️ Editar',       self.editar_compra)

        ff_comp = tk.Frame(tab_comp, bg=self.C['toolbar_bg'], pady=4)
        ff_comp.pack(fill='x')
        tk.Label(ff_comp, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_compra = tk.Entry(ff_comp, font=('Arial', 9), width=30)
        self.entry_buscar_compra.pack(side='left', padx=4)
        self.entry_buscar_compra.bind('<Return>', lambda e: self.cargar_compras())
        self._toolbar_btn(ff_comp, '🔍', self.cargar_compras)

        ft_comp = tk.Frame(tab_comp, bg=self.C['content_bg'])
        ft_comp.pack(fill='both', expand=True, padx=8, pady=8)
        cols_comp = ('ID', 'Folio', 'Fecha', 'Proveedor',
                     'Ticket/Ref', 'Total', 'Método Pago')
        self.tree_compras = ttk.Treeview(
            ft_comp, columns=cols_comp, show='headings', selectmode='browse')
        for col, w in zip(cols_comp, [0, 100, 130, 180, 120, 90, 120]):
            self.tree_compras.heading(col, text=col)
            self.tree_compras.column(col, width=w, minwidth=w)
        self.tree_compras.column('ID', stretch=False)
        sc = ttk.Scrollbar(ft_comp, orient='vertical',   command=self.tree_compras.yview)
        sx = ttk.Scrollbar(ft_comp, orient='horizontal', command=self.tree_compras.xview)
        self.tree_compras.configure(yscrollcommand=sc.set, xscrollcommand=sx.set)
        self.tree_compras.grid(row=0, column=0, sticky='nsew')
        sc.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        ft_comp.grid_rowconfigure(0, weight=1)
        ft_comp.grid_columnconfigure(0, weight=1)
        self.tree_compras.bind('<Double-1>', lambda e: self.ver_compra())
        self._configurar_sorting_treeview(self.tree_compras,
            columnas_numericas=['Total'])
        self.cargar_compras()

    # ── SECCIÓN: DASHBOARD ─────────────────────────────────────────────────
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
            self._facturacion._mostrar_detalle_por_id(row[0])

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
                            self._facturacion._mostrar_detalle_por_id(fid)
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
            self.actualizar_dashboard()

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
                self.actualizar_dashboard()

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
        """Sincroniza cotizaciones.estado cuando se edita una etapa de seguimiento.
        
        Solo sincroniza estados de entrega (Entregada). Las etapas de Facturada/Pagada/OC
        son ahora solo de seguimiento y no cambian el estado de la cotización.
        """
        if not completada:
            return False
        # Solo Entregada tiene correspondencia con estado (Facturada/Pagada ya no son estados)
        if etapa != 'Entregada':
            return False
        nuevo_estado = 'Entregada'
        # Evitar degradar un estado más avanzado
        orden = ['Pendiente', 'Programada', 'Parcialmente Entregada', 'Entregada', 'Cancelada']
        self.cursor.execute("SELECT estado FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        row = self.cursor.fetchone()
        if not row:
            return False
        estado_actual = row[0]
        idx_actual   = orden.index(estado_actual) if estado_actual in orden else 0
        idx_nuevo    = orden.index(nuevo_estado)  if nuevo_estado  in orden else 0
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

    def cargar_clientes(self):
        """Carga la lista de clientes en la tabla"""
        # Limpiar tabla
        for item in self.tree_clientes.get_children():
            self.tree_clientes.delete(item)
        
        # Obtener término de búsqueda
        buscar = self.entry_buscar_cliente.get().strip()
        
        # Consultar base de datos
        if buscar:
            self.cursor.execute("""
                SELECT id, nombre_comercial, razon_social, tipo, rfc,
                       regimen_fiscal, uso_cfdi, cp_fiscal,
                       contacto, telefono, email
                FROM clientes
                WHERE nombre_comercial LIKE ? OR razon_social LIKE ? OR rfc LIKE ?
                ORDER BY nombre_comercial
            """, (f'%{buscar}%', f'%{buscar}%', f'%{buscar}%'))
        else:
            self.cursor.execute("""
                SELECT id, nombre_comercial, razon_social, tipo, rfc,
                       regimen_fiscal, uso_cfdi, cp_fiscal,
                       contacto, telefono, email
                FROM clientes
                ORDER BY nombre_comercial
            """)
        
        # Insertar datos
        for row in self.cursor.fetchall():
            self.tree_clientes.insert('', 'end', values=row)
    
    def nuevo_cliente(self):
        """Abre ventana para crear nuevo cliente"""
        self.ventana_cliente(modo='nuevo')
    
    def editar_cliente(self):
        """Abre ventana para editar cliente seleccionado"""
        seleccion = self.tree_clientes.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona un cliente para editar")
            return
        
        item = self.tree_clientes.item(seleccion[0])
        cliente_id = item['values'][0]
        self.ventana_cliente(modo='editar', cliente_id=cliente_id)
    
    def eliminar_cliente(self):
        """Elimina el cliente seleccionado"""
        seleccion = self.tree_clientes.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona un cliente para eliminar")
            return
        
        item = self.tree_clientes.item(seleccion[0])
        cliente_id = item['values'][0]
        nombre = item['values'][1]
        
        respuesta = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Estás seguro de eliminar al cliente '{nombre}'?\n\nEsta acción no se puede deshacer."
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
                self.conn.commit()
                messagebox.showinfo("Éxito", "Cliente eliminado correctamente")
                self.cargar_clientes()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar el cliente:\n{str(e)}")
    
    def ventana_cliente(self, modo='nuevo', cliente_id=None, _prefill=None, _callback=None):
        """Ventana para crear o editar cliente con datos fiscales SAT."""
        # ── Catálogos SAT ──────────────────────────────────────────────────
        REGIMENES = [
            ('601', 'General de Ley Personas Morales'),
            ('603', 'Personas Morales con Fines no Lucrativos'),
            ('605', 'Sueldos y Salarios e Ingresos Asimilados'),
            ('606', 'Arrendamiento'),
            ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
            ('608', 'Demás ingresos'),
            ('610', 'Residentes en el Extranjero sin EP en México'),
            ('611', 'Ingresos por Dividendos'),
            ('612', 'Personas Físicas con Actividades Empresariales'),
            ('614', 'Ingresos por intereses'),
            ('616', 'Sin obligaciones fiscales'),
            ('620', 'Sociedades Cooperativas de Producción'),
            ('621', 'Incorporación Fiscal'),
            ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas'),
            ('623', 'Opcional para Grupos de Sociedades'),
            ('624', 'Coordinados'),
            ('625', 'Actividades Empresariales vía Plataformas Tecnológicas'),
            ('626', 'RESICO – Simplificado de Confianza'),
        ]
        USOS_CFDI = [
            ('G01', 'Adquisición de mercancias'),
            ('G02', 'Devoluciones, descuentos o bonificaciones'),
            ('G03', 'Gastos en general'),
            ('I01', 'Construcciones'),
            ('I02', 'Mobiliario y equipo de oficina'),
            ('I03', 'Equipo de transporte'),
            ('I04', 'Equipo de cómputo y accesorios'),
            ('I05', 'Dados, troqueles, moldes, matrices'),
            ('I06', 'Comunicaciones telefónicas'),
            ('I07', 'Comunicaciones satelitales'),
            ('I08', 'Otra maquinaria y equipo'),
            ('D01', 'Honorarios médicos y gastos hospitalarios'),
            ('D02', 'Gastos médicos por incapacidad'),
            ('D03', 'Gastos funerales'),
            ('D04', 'Donativos'),
            ('D10', 'Pagos por servicios educativos'),
            ('S01', 'Sin efectos fiscales'),
            ('CP01', 'Pagos'),
            ('CN01', 'Nómina'),
        ]
        reg_opts    = [f"{c} – {n}" for c, n in REGIMENES]
        uso_opts    = [f"{c} – {n}" for c, n in USOS_CFDI]

        # ── Cargar datos existentes ────────────────────────────────────────
        datos = {}
        if _prefill:
            datos.update(_prefill)
        if modo == 'editar' and cliente_id:
            self.cursor.execute("""
                SELECT nombre_comercial, razon_social, tipo, rfc, direccion,
                       contacto, telefono, email, regimen_fiscal, uso_cfdi, cp_fiscal
                FROM clientes WHERE id = ?
            """, (cliente_id,))
            row = self.cursor.fetchone()
            if row:
                keys = ['nombre_comercial', 'razon_social', 'tipo', 'rfc',
                        'direccion', 'contacto', 'telefono', 'email',
                        'regimen_fiscal', 'uso_cfdi', 'cp_fiscal']
                datos = {k: (v or '') for k, v in zip(keys, row)}

            # Auto-llenar desde facturas si faltan datos SAT
            if not datos.get('regimen_fiscal') or not datos.get('uso_cfdi'):
                rfc = datos.get('rfc', '')
                if rfc:
                    self.cursor.execute("""
                        SELECT uso_cfdi FROM facturas
                        WHERE rfc_receptor = ? AND uso_cfdi IS NOT NULL AND uso_cfdi != ''
                        ORDER BY fecha DESC LIMIT 1
                    """, (rfc,))
                    frow = self.cursor.fetchone()
                    if frow and not datos.get('uso_cfdi'):
                        datos['uso_cfdi'] = frow[0]

        # ── Ventana ────────────────────────────────────────────────────────
        ventana = tk.Toplevel(self.root)
        ventana.title('Nuevo Cliente' if modo == 'nuevo' else f"Editar Cliente — {datos.get('nombre_comercial','')}")
        ventana.geometry('580x660')
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()

        # Cabecera
        hdr = tk.Frame(ventana, bg='#1e3a5f', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='👥  ' + ('Nuevo Cliente' if modo == 'nuevo' else 'Editar Cliente'),
                 font=('Arial', 11, 'bold'), bg='#1e3a5f', fg='white').pack(side='left', padx=12)

        # Canvas + scroll
        canvas = tk.Canvas(ventana, bg='#f1f5f9', highlightthickness=0)
        sb = ttk.Scrollbar(ventana, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        inner = tk.Frame(canvas, bg='#f1f5f9')
        wid = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))

        def section(parent, titulo, color='#1e3a5f'):
            hf = tk.Frame(parent, bg=color, pady=4)
            hf.pack(fill='x', padx=12, pady=(10, 0))
            tk.Label(hf, text=titulo, font=('Arial', 9, 'bold'),
                     bg=color, fg='white').pack(side='left', padx=8)
            return tk.Frame(parent, bg='#ffffff', padx=14, pady=8,
                            highlightbackground='#e2e8f0', highlightthickness=1)

        def field(parent, row, label, widget_type='entry', width=38,
                  required=False, values=None, height=3):
            lbl = label + ('*' if required else '')
            tk.Label(parent, text=lbl,
                     font=('Arial', 9, 'bold' if required else 'normal'),
                     bg='#ffffff', fg='#374151', anchor='w').grid(
                row=row, column=0, sticky='w', padx=(0, 10), pady=4)
            if widget_type == 'combo':
                w = ttk.Combobox(parent, values=values or [], state='readonly',
                                 width=width - 2, font=('Arial', 9))
            elif widget_type == 'text':
                w = tk.Text(parent, width=width, height=height,
                            font=('Arial', 9), relief='solid', bd=1)
            else:
                w = tk.Entry(parent, width=width, font=('Arial', 9),
                             relief='solid', bd=1)
            w.grid(row=row, column=1, sticky='ew', pady=4)
            parent.grid_columnconfigure(1, weight=1)
            return w

        # ── Sección: Datos Generales ───────────────────────────────────────
        sec1 = section(inner, '📋  Datos Generales')
        sec1.pack(fill='x', padx=12)

        e_nombre   = field(sec1, 0, 'Nombre Comercial', required=True)
        e_nombre.insert(0, datos.get('nombre_comercial', ''))

        e_razon    = field(sec1, 1, 'Razón Social')
        e_razon.insert(0, datos.get('razon_social', ''))

        c_tipo = field(sec1, 2, 'Tipo de Cliente', 'combo', required=True,
                       values=['Gobierno', 'Hotel', 'Empresa', 'Persona Física', 'Otro'])
        c_tipo.set(datos.get('tipo', 'Empresa'))

        e_rfc = field(sec1, 3, 'RFC')
        e_rfc.insert(0, datos.get('rfc', ''))

        e_dir = field(sec1, 4, 'Dirección', 'text', height=2)
        e_dir.insert('1.0', datos.get('direccion', ''))

        # ── Sección: Contacto ──────────────────────────────────────────────
        sec2 = section(inner, '📞  Contacto', '#374151')
        sec2.pack(fill='x', padx=12)

        e_contacto  = field(sec2, 0, 'Persona de Contacto')
        e_contacto.insert(0, datos.get('contacto', ''))

        e_telefono  = field(sec2, 1, 'Teléfono')
        e_telefono.insert(0, datos.get('telefono', ''))

        e_email     = field(sec2, 2, 'Email')
        e_email.insert(0, datos.get('email', ''))

        # ── Sección: Datos Fiscales SAT ────────────────────────────────────
        sec3 = section(inner, '🏛️  Datos Fiscales SAT', '#7c3aed')
        sec3.pack(fill='x', padx=12, pady=(0, 10))

        tk.Label(sec3, text='Estos datos se usan al generar CFDIs para este cliente.',
                 font=('Arial', 7, 'italic'), bg='#ffffff',
                 fg='#9ca3af').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))

        c_regimen = field(sec3, 1, 'Régimen Fiscal', 'combo', values=reg_opts)
        # Pre-seleccionar por código
        cur_reg = datos.get('regimen_fiscal', '')
        if cur_reg:
            match = next((o for o in reg_opts if o.startswith(cur_reg)), '')
            if match:
                c_regimen.set(match)

        c_uso = field(sec3, 2, 'Uso de CFDI', 'combo', values=uso_opts)
        cur_uso = datos.get('uso_cfdi', '')
        if cur_uso:
            match = next((o for o in uso_opts if o.startswith(cur_uso)), '')
            if match:
                c_uso.set(match)

        e_cp = field(sec3, 3, 'C.P. Fiscal')
        e_cp.insert(0, datos.get('cp_fiscal', ''))

        # Nota de auto-llenado si se detectó dato desde factura
        if modo == 'editar' and datos.get('uso_cfdi'):
            tk.Label(sec3, text='ℹ️ Datos detectados desde facturas importadas.',
                     font=('Arial', 7), bg='#ffffff', fg='#0e7490'
                     ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(0, 2))

        # ── Pie: botones ───────────────────────────────────────────────────
        foot = tk.Frame(ventana, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')

        def guardar(event=None):
            nombre = e_nombre.get().strip()
            tipo   = c_tipo.get()
            if not nombre:
                messagebox.showwarning('Advertencia', 'El nombre comercial es obligatorio',
                                       parent=ventana)
                e_nombre.focus()
                return
            if not tipo:
                messagebox.showwarning('Advertencia', 'Selecciona un tipo de cliente',
                                       parent=ventana)
                return

            # Extraer código de régimen y uso (antes del " – ")
            reg_val = c_regimen.get().split(' – ')[0] if c_regimen.get() else ''
            uso_val = c_uso.get().split(' – ')[0]     if c_uso.get()     else ''

            datos_save = {
                'nombre_comercial': nombre,
                'razon_social':     e_razon.get().strip(),
                'tipo':             tipo,
                'rfc':              e_rfc.get().strip().upper(),
                'direccion':        e_dir.get('1.0', 'end-1c').strip(),
                'contacto':         e_contacto.get().strip(),
                'telefono':         e_telefono.get().strip(),
                'email':            e_email.get().strip(),
                'regimen_fiscal':   reg_val,
                'uso_cfdi':         uso_val,
                'cp_fiscal':        e_cp.get().strip(),
            }
            try:
                if modo == 'nuevo':
                    self.cursor.execute("""
                        INSERT INTO clientes
                        (nombre_comercial, razon_social, tipo, rfc, direccion,
                         contacto, telefono, email, regimen_fiscal, uso_cfdi, cp_fiscal)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, tuple(datos_save.values()))
                    msg = 'Cliente registrado correctamente'
                else:
                    self.cursor.execute("""
                        UPDATE clientes SET
                        nombre_comercial=?, razon_social=?, tipo=?, rfc=?,
                        direccion=?, contacto=?, telefono=?, email=?,
                        regimen_fiscal=?, uso_cfdi=?, cp_fiscal=?
                        WHERE id=?
                    """, (*datos_save.values(), cliente_id))
                    msg = 'Cliente actualizado correctamente'
                self.conn.commit()
                new_cli_id = self.cursor.lastrowid if modo == 'nuevo' else cliente_id
                messagebox.showinfo('Éxito', msg, parent=ventana)
                self.cargar_clientes()
                ventana.destroy()
                if _callback:
                    _callback(new_cli_id)
            except sqlite3.Error as e:
                messagebox.showerror('Error', str(e), parent=ventana)

        ventana.bind('<Return>', guardar)
        tk.Button(foot, text='💾 Guardar', command=guardar,
                  bg='#0f7b5e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=12)
        tk.Button(foot, text='Cancelar', command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='right', padx=12)

        e_nombre.focus()


    # (removed - rebuilt in new ERP UI)
    def cargar_productos(self):
        """Carga la lista de productos en la tabla"""
        # Limpiar tabla
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)
        
        # Obtener término de búsqueda
        buscar = self.entry_buscar_producto.get().strip()
        
        # Consultar base de datos
        if buscar:
            self.cursor.execute("""
                SELECT p.id, p.codigo, p.nombre, c.nombre, s.nombre, p.unidad_medida,
                       p.precio_base, p.aplica_iva, p.precio_venta, p.stock_actual, p.stock_minimo,
                       p.clave_sat
                FROM productos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN subcategorias s ON p.subcategoria_id = s.id
                WHERE p.codigo LIKE ? OR p.nombre LIKE ?
                ORDER BY p.nombre
            """, (f'%{buscar}%', f'%{buscar}%'))
        else:
            self.cursor.execute("""
                SELECT p.id, p.codigo, p.nombre, c.nombre, s.nombre, p.unidad_medida,
                       p.precio_base, p.aplica_iva, p.precio_venta, p.stock_actual, p.stock_minimo,
                       p.clave_sat
                FROM productos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN subcategorias s ON p.subcategoria_id = s.id
                ORDER BY p.nombre
            """)
        
        # Insertar datos
        for row in self.cursor.fetchall():
            producto_id = row[0]
            row_list = list(row)
            # Formatear precios
            row_list[6] = f"${row[6]:,.2f}" if row[6] else "$0.00"
            row_list[7] = "Sí" if row[7] else "No"
            row_list[8] = f"${row[8]:,.2f}" if row[8] else "$0.00"
            # clave_sat queda en row_list[11] como texto o vacío
            row_list[11] = row[11] or ''
            
            # Obtener info de proveedores
            self.cursor.execute("""
                SELECT prov.nombre, pp.es_principal
                FROM producto_proveedor pp
                JOIN proveedores prov ON pp.proveedor_id = prov.id
                WHERE pp.producto_id = ?
                ORDER BY pp.es_principal DESC, prov.nombre
            """, (producto_id,))
            provs = self.cursor.fetchall()
            
            if provs:
                # Mostrar proveedor principal primero (si existe) + cantidad total
                principal = next((p[0] for p in provs if p[1]), None)
                if principal:
                    info_prov = f"⭐ {principal}"
                    if len(provs) > 1:
                        info_prov += f" (+{len(provs)-1})"
                else:
                    info_prov = f"{provs[0][0]}"
                    if len(provs) > 1:
                        info_prov += f" (+{len(provs)-1})"
            else:
                info_prov = "Sin asignar"
            
            row_list.append(info_prov)
            self.tree_productos.insert('', 'end', values=row_list)
    
    def nuevo_producto(self):
        """Abre ventana para crear nuevo producto"""
        self.ventana_producto(modo='nuevo')
    
    def editar_producto(self):
        """Abre ventana para editar producto seleccionado"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona un producto para editar")
            return
        
        item = self.tree_productos.item(seleccion[0])
        producto_id = item['values'][0]
        self.ventana_producto(modo='editar', producto_id=producto_id)
    
    def eliminar_producto(self):
        """Elimina el producto seleccionado"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona un producto para eliminar")
            return
        
        item = self.tree_productos.item(seleccion[0])
        producto_id = item['values'][0]
        nombre = item['values'][2]
        
        respuesta = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Estás seguro de eliminar el producto '{nombre}'?\n\nEsta acción no se puede deshacer."
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
                self.conn.commit()
                messagebox.showinfo("Éxito", "Producto eliminado correctamente")
                self.cargar_productos()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar el producto:\n{str(e)}")
    
    def ventana_producto(self, modo='nuevo', producto_id=None):
        """Ventana para crear o editar producto"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Nuevo Producto" if modo == 'nuevo' else "Editar Producto")
        ventana.geometry("600x650")
        ventana.resizable(False, False)
        
        # Cargar categorías y subcategorías
        self.cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        categorias = self.cursor.fetchall()
        
        # Si es editar, cargar datos
        datos_producto = {}
        if modo == 'editar' and producto_id:
            self.cursor.execute("""
                SELECT codigo, nombre, descripcion, categoria_id, subcategoria_id, unidad_medida,
                       precio_base, aplica_iva, precio_venta, stock_actual, stock_minimo,
                       clave_sat, clave_unidad_sat
                FROM productos WHERE id = ?
            """, (producto_id,))
            row = self.cursor.fetchone()
            if row:
                datos_producto = {
                    'codigo': row[0] or '',
                    'nombre': row[1] or '',
                    'descripcion': row[2] or '',
                    'categoria_id': row[3],
                    'subcategoria_id': row[4],
                    'unidad_medida': row[5] or '',
                    'precio_base': row[6] or 0,
                    'aplica_iva': row[7],
                    'precio_venta': row[8] or 0,
                    'stock_actual': row[9] or 0,
                    'stock_minimo': row[10] or 0,
                    'clave_sat': row[11] or '',
                    'clave_unidad_sat': row[12] or '',
                }
        
        # Frame principal con scroll
        canvas = tk.Canvas(ventana)
        scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, padx=20, pady=20)
        
        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Variables
        var_aplica_iva = tk.BooleanVar(value=datos_producto.get('aplica_iva', 1))
        
        row = 0
        
        # Código
        tk.Label(frame, text="Código/SKU:*", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky='w', pady=5
        )
        entry_codigo = tk.Entry(frame, width=40, font=('Arial', 10))
        entry_codigo.grid(row=row, column=1, pady=5, sticky='w')
        entry_codigo.insert(0, datos_producto.get('codigo', ''))
        row += 1
        
        # Nombre
        tk.Label(frame, text="Nombre:*", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky='w', pady=5
        )
        entry_nombre = tk.Entry(frame, width=40, font=('Arial', 10))
        entry_nombre.grid(row=row, column=1, pady=5, sticky='w')
        entry_nombre.insert(0, datos_producto.get('nombre', ''))
        row += 1
        
        # Descripción
        tk.Label(frame, text="Descripción:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='nw', pady=5
        )
        text_descripcion = tk.Text(frame, width=30, height=3, font=('Arial', 10))
        text_descripcion.grid(row=row, column=1, pady=5, sticky='w')
        text_descripcion.insert('1.0', datos_producto.get('descripcion', ''))
        row += 1
        
        # Categoría
        tk.Label(frame, text="Categoría:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        combo_categoria = ttk.Combobox(
            frame,
            values=[cat[1] for cat in categorias],
            state='readonly',
            width=37,
            font=('Arial', 10)
        )
        combo_categoria.grid(row=row, column=1, pady=5, sticky='w')
        
        # Seleccionar categoría si está editando
        if datos_producto.get('categoria_id'):
            for i, cat in enumerate(categorias):
                if cat[0] == datos_producto['categoria_id']:
                    combo_categoria.current(i)
                    break
        row += 1
        
        # Subcategoría
        tk.Label(frame, text="Subcategoría:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        combo_subcategoria = ttk.Combobox(
            frame,
            state='readonly',
            width=37,
            font=('Arial', 10)
        )
        combo_subcategoria.grid(row=row, column=1, pady=5, sticky='w')
        row += 1
        
        def generar_sku_automatico():
            """Genera un SKU automático a partir de categoría y subcategoría"""
            if modo != 'nuevo':
                return
            cat_nombre = combo_categoria.get()
            sub_nombre = combo_subcategoria.get()
            if not cat_nombre or not sub_nombre:
                return
            
            # Prefijo: primeras 3 letras de categoría + primeras 3 de subcategoría
            cat_prefix = ''.join(c for c in cat_nombre.upper() if c.isalpha())[:3]
            sub_prefix = ''.join(c for c in sub_nombre.upper() if c.isalpha())[:3]
            prefijo = f"{cat_prefix}{sub_prefix}"
            
            # Buscar el siguiente consecutivo para ese prefijo
            self.cursor.execute("""
                SELECT codigo FROM productos 
                WHERE codigo LIKE ?
                ORDER BY codigo DESC
            """, (f"{prefijo}%",))
            
            existentes = [row[0] for row in self.cursor.fetchall()]
            
            # Extraer números y encontrar el máximo
            max_num = 0
            for cod in existentes:
                num_str = cod[len(prefijo):]
                try:
                    num = int(num_str)
                    if num > max_num:
                        max_num = num
                except ValueError:
                    pass
            
            nuevo_num = max_num + 1
            nuevo_sku = f"{prefijo}{nuevo_num:04d}"
            
            entry_codigo.delete(0, tk.END)
            entry_codigo.insert(0, nuevo_sku)
        
        def actualizar_subcategorias(event=None):
            """Actualiza subcategorías según categoría seleccionada"""
            categoria_nombre = combo_categoria.get()
            if not categoria_nombre:
                combo_subcategoria['values'] = []
                return
            
            # Buscar ID de categoría
            categoria_id = None
            for cat in categorias:
                if cat[1] == categoria_nombre:
                    categoria_id = cat[0]
                    break
            
            if categoria_id:
                self.cursor.execute(
                    "SELECT id, nombre FROM subcategorias WHERE categoria_id = ? ORDER BY nombre",
                    (categoria_id,)
                )
                subcats = self.cursor.fetchall()
                combo_subcategoria['values'] = [sub[1] for sub in subcats]
                
                # Seleccionar si está editando
                if datos_producto.get('subcategoria_id'):
                    for i, sub in enumerate(subcats):
                        if sub[0] == datos_producto['subcategoria_id']:
                            combo_subcategoria.current(i)
                            break
        
        combo_categoria.bind('<<ComboboxSelected>>', actualizar_subcategorias)
        combo_subcategoria.bind('<<ComboboxSelected>>', lambda e: generar_sku_automatico())
        if modo == 'editar':
            actualizar_subcategorias()
        
        # Unidad de medida
        tk.Label(frame, text="Unidad de Medida:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        combo_unidad = ttk.Combobox(
            frame,
            values=['Pieza', 'Caja', 'Kg', 'Litro', 'Paquete', 'Metro', 'Otro'],
            width=37,
            font=('Arial', 10)
        )
        combo_unidad.grid(row=row, column=1, pady=5, sticky='w')
        combo_unidad.set(datos_producto.get('unidad_medida', 'Pieza'))
        row += 1
        
        # Precio base
        tk.Label(frame, text="Precio Base:*", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky='w', pady=5
        )
        entry_precio_base = tk.Entry(frame, width=20, font=('Arial', 10))
        entry_precio_base.grid(row=row, column=1, pady=5, sticky='w')
        entry_precio_base.insert(0, str(datos_producto.get('precio_base', '0.00')))
        row += 1
        
        # Aplica IVA
        check_iva = tk.Checkbutton(
            frame,
            text="Aplica IVA (16%)",
            variable=var_aplica_iva,
            font=('Arial', 10)
        )
        check_iva.grid(row=row, column=1, pady=5, sticky='w')
        row += 1
        
        # Precio venta
        tk.Label(frame, text="Precio Venta:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        entry_precio_venta = tk.Entry(frame, width=20, font=('Arial', 10))
        entry_precio_venta.grid(row=row, column=1, pady=5, sticky='w')
        entry_precio_venta.insert(0, str(datos_producto.get('precio_venta', '0.00')))
        tk.Label(frame, text="(Opcional, se calcula automáticamente)", font=('Arial', 8), fg='gray').grid(
            row=row+1, column=1, sticky='w'
        )
        row += 2
        
        # Stock actual
        tk.Label(frame, text="Stock Actual:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        entry_stock = tk.Entry(frame, width=20, font=('Arial', 10))
        entry_stock.grid(row=row, column=1, pady=5, sticky='w')
        entry_stock.insert(0, str(datos_producto.get('stock_actual', '0')))
        row += 1
        
        # Stock mínimo
        tk.Label(frame, text="Stock Mínimo:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        entry_stock_min = tk.Entry(frame, width=20, font=('Arial', 10))
        entry_stock_min.grid(row=row, column=1, pady=5, sticky='w')
        entry_stock_min.insert(0, str(datos_producto.get('stock_minimo', '0')))
        row += 1

        # ── Separador SAT ──────────────────────────────────────────────
        tk.Frame(frame, bg='#e2e8f0', height=1).grid(
            row=row, column=0, columnspan=2, sticky='ew', pady=(10, 4))
        row += 1
        tk.Label(frame, text="🧾  Datos SAT / Facturación",
                 font=('Arial', 9, 'bold'), fg='#0e7490').grid(
            row=row, column=0, columnspan=2, sticky='w', pady=(0, 6))
        row += 1

        # Clave Producto/Servicio SAT
        tk.Label(frame, text="Clave SAT (prod/serv):", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        frame_csat = tk.Frame(frame)
        frame_csat.grid(row=row, column=1, pady=5, sticky='w')
        entry_clave_sat = tk.Entry(frame_csat, width=18, font=('Arial', 10))
        entry_clave_sat.pack(side='left')
        entry_clave_sat.insert(0, datos_producto.get('clave_sat', ''))
        tk.Label(frame_csat, text="  ej: 43211500",
                 font=('Arial', 8), fg='gray').pack(side='left')
        row += 1

        # Clave Unidad SAT
        tk.Label(frame, text="Clave Unidad SAT:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5
        )
        frame_usat = tk.Frame(frame)
        frame_usat.grid(row=row, column=1, pady=5, sticky='w')
        entry_clave_unidad_sat = tk.Entry(frame_usat, width=18, font=('Arial', 10))
        entry_clave_unidad_sat.pack(side='left')
        entry_clave_unidad_sat.insert(0, datos_producto.get('clave_unidad_sat', ''))
        tk.Label(frame_usat, text="  ej: H87 (Pieza), KGM (Kilo)",
                 font=('Arial', 8), fg='gray').pack(side='left')
        row += 1
        frame_botones = tk.Frame(frame)
        frame_botones.grid(row=row, column=0, columnspan=2, pady=20)
        
        def guardar():
            # Validar campos requeridos
            codigo = entry_codigo.get().strip()
            nombre = entry_nombre.get().strip()
            precio_base = entry_precio_base.get().strip()
            
            if not codigo:
                messagebox.showwarning("Advertencia", "El código es obligatorio")
                entry_codigo.focus()
                return
            
            if not nombre:
                messagebox.showwarning("Advertencia", "El nombre es obligatorio")
                entry_nombre.focus()
                return
            
            try:
                precio_base = float(precio_base)
                if precio_base < 0:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("Advertencia", "El precio base debe ser un número válido")
                entry_precio_base.focus()
                return
            
            # Obtener IDs de categoría y subcategoría
            categoria_id = None
            if combo_categoria.get():
                for cat in categorias:
                    if cat[1] == combo_categoria.get():
                        categoria_id = cat[0]
                        break
            
            subcategoria_id = None
            if combo_subcategoria.get() and categoria_id:
                self.cursor.execute(
                    "SELECT id FROM subcategorias WHERE nombre = ? AND categoria_id = ?",
                    (combo_subcategoria.get(), categoria_id)
                )
                result = self.cursor.fetchone()
                if result:
                    subcategoria_id = result[0]
            
            # Recopilar datos
            datos = {
                'codigo': codigo.upper(),
                'nombre': nombre,
                'descripcion': text_descripcion.get('1.0', 'end-1c').strip(),
                'categoria_id': categoria_id,
                'subcategoria_id': subcategoria_id,
                'unidad_medida': combo_unidad.get(),
                'precio_base': precio_base,
                'aplica_iva': 1 if var_aplica_iva.get() else 0,
                'precio_venta': float(entry_precio_venta.get() or 0),
                'stock_actual': float(entry_stock.get() or 0),
                'stock_minimo': float(entry_stock_min.get() or 0),
                'clave_sat': entry_clave_sat.get().strip() or None,
                'clave_unidad_sat': entry_clave_unidad_sat.get().strip() or None,
            }
            
            try:
                if modo == 'nuevo':
                    self.cursor.execute("""
                        INSERT INTO productos (codigo, nombre, descripcion, categoria_id, subcategoria_id,
                                             unidad_medida, precio_base, aplica_iva, precio_venta,
                                             stock_actual, stock_minimo, clave_sat, clave_unidad_sat)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datos['codigo'], datos['nombre'], datos['descripcion'],
                        datos['categoria_id'], datos['subcategoria_id'], datos['unidad_medida'],
                        datos['precio_base'], datos['aplica_iva'], datos['precio_venta'],
                        datos['stock_actual'], datos['stock_minimo'],
                        datos['clave_sat'], datos['clave_unidad_sat']
                    ))
                    mensaje = "Producto registrado correctamente"
                else:
                    self.cursor.execute("""
                        UPDATE productos SET
                        codigo=?, nombre=?, descripcion=?, categoria_id=?, subcategoria_id=?,
                        unidad_medida=?, precio_base=?, aplica_iva=?, precio_venta=?,
                        stock_actual=?, stock_minimo=?, clave_sat=?, clave_unidad_sat=?
                        WHERE id=?
                    """, (
                        datos['codigo'], datos['nombre'], datos['descripcion'],
                        datos['categoria_id'], datos['subcategoria_id'], datos['unidad_medida'],
                        datos['precio_base'], datos['aplica_iva'], datos['precio_venta'],
                        datos['stock_actual'], datos['stock_minimo'],
                        datos['clave_sat'], datos['clave_unidad_sat'],
                        producto_id
                    ))
                    mensaje = "Producto actualizado correctamente"
                
                self.conn.commit()
                messagebox.showinfo("Éxito", mensaje)
                self.cargar_productos()
                ventana.destroy()
                
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", f"Ya existe un producto con el código '{codigo}'")
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo guardar el producto:\n{str(e)}")
        
        tk.Button(
            frame_botones,
            text="💾 Guardar",
            command=guardar,
            bg='#27ae60',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=20,
            pady=8
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            command=ventana.destroy,
            bg='#95a5a6',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=20,
            pady=8
        ).pack(side='left', padx=5)
        
        # Botón de gestionar proveedores
        btn_proveedores = tk.Button(
            frame_botones,
            text="🏭 Gestionar Proveedores",
            command=lambda: self.gestionar_proveedores_producto(producto_id, ventana) if producto_id else None,
            bg='#16a085' if modo == 'editar' else '#95a5a6',
            fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2' if modo == 'editar' else 'arrow',
            padx=15,
            pady=8,
            state='normal' if modo == 'editar' else 'disabled'
        )
        btn_proveedores.pack(side='left', padx=5)
        
        # Tooltip para modo nuevo
        if modo == 'nuevo':
            def mostrar_tooltip(event):
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                label = tk.Label(tooltip, text="Guarda el producto primero",
                                bg='#2c3e50', fg='white', font=('Arial', 9),
                                padx=8, pady=4)
                label.pack()
                btn_proveedores._tooltip = tooltip
                tooltip.after(2000, tooltip.destroy)
            
            def ocultar_tooltip(event):
                if hasattr(btn_proveedores, '_tooltip'):
                    try:
                        btn_proveedores._tooltip.destroy()
                    except:
                        pass
            
            btn_proveedores.bind('<Enter>', mostrar_tooltip)
            btn_proveedores.bind('<Leave>', ocultar_tooltip)
        
        # Hacer modal — Enter guarda
        ventana.bind('<Return>', lambda e: guardar())
        ventana.transient(self.root)
        ventana.grab_set()
        entry_codigo.focus()
    
    def gestionar_proveedores_producto(self, producto_id, ventana_padre):
        """Gestiona los proveedores asociados a un producto"""
        # Obtener nombre del producto
        self.cursor.execute("SELECT codigo, nombre FROM productos WHERE id = ?", (producto_id,))
        prod = self.cursor.fetchone()
        if not prod:
            return
        codigo_prod, nombre_prod = prod
        
        ventana = tk.Toplevel(ventana_padre)
        ventana.title(f"Proveedores — {codigo_prod}: {nombre_prod}")
        ventana.geometry("750x500")
        
        # Header
        header = tk.Frame(ventana, bg='#16a085', pady=8)
        header.pack(fill='x')
        tk.Label(header, text=f"🏭  Proveedores del Producto",
                 font=('Arial', 11, 'bold'), bg='#16a085', fg='white').pack()
        tk.Label(header, text=f"{codigo_prod} — {nombre_prod}",
                 font=('Arial', 9), bg='#16a085', fg='#d5f5ef').pack()
        
        # Toolbar
        toolbar = tk.Frame(ventana, bg='#d8dde8', pady=6)
        toolbar.pack(fill='x')
        tk.Frame(ventana, bg='#c5ccd8', height=1).pack(fill='x')
        
        def agregar_proveedor():
            # Obtener proveedores no asociados
            self.cursor.execute("""
                SELECT p.id, p.nombre 
                FROM proveedores p
                WHERE p.id NOT IN (
                    SELECT proveedor_id FROM producto_proveedor WHERE producto_id = ?
                )
                ORDER BY p.nombre
            """, (producto_id,))
            disponibles = self.cursor.fetchall()
            
            if not disponibles:
                messagebox.showinfo("Sin proveedores",
                    "Todos los proveedores ya están asociados.\\n\\n"
                    "Crea nuevos proveedores en Catálogos → Proveedores.",
                    parent=ventana)
                return
            
            # Dialog de selección
            dlg = tk.Toplevel(ventana)
            dlg.title("Agregar Proveedor")
            dlg.geometry("450x420")
            dlg.transient(ventana)
            dlg.grab_set()
            
            tk.Label(dlg, text="Selecciona un proveedor:", font=('Arial', 10, 'bold'),
                     pady=8).pack()
            
            # Listbox
            frame_list = tk.Frame(dlg)
            frame_list.pack(fill='both', expand=True, padx=10, pady=5)
            
            listbox = tk.Listbox(frame_list, font=('Arial', 10), height=12)
            scroll = ttk.Scrollbar(frame_list, orient='vertical', command=listbox.yview)
            listbox.configure(yscrollcommand=scroll.set)
            listbox.pack(side='left', fill='both', expand=True)
            scroll.pack(side='right', fill='y')
            
            prov_dict = {}
            for prov_id, nombre in disponibles:
                listbox.insert('end', nombre)
                prov_dict[nombre] = prov_id
            
            # Principal checkbox
            var_principal = tk.BooleanVar(value=False)
            tk.Checkbutton(dlg, text="Marcar como proveedor principal",
                           variable=var_principal, font=('Arial', 9)).pack(pady=5)
            
            # Notas
            tk.Label(dlg, text="Notas (opcional):", font=('Arial', 9)).pack(anchor='w', padx=10)
            entry_notas = tk.Entry(dlg, width=40, font=('Arial', 9))
            entry_notas.pack(padx=10, pady=2)
            
            def confirmar():
                sel = listbox.curselection()
                if not sel:
                    messagebox.showwarning("Advertencia", "Selecciona un proveedor", parent=dlg)
                    return
                nombre = listbox.get(sel[0])
                prov_id = prov_dict[nombre]
                notas = entry_notas.get().strip()
                
                try:
                    # Si se marca como principal, quitar el flag de otros
                    if var_principal.get():
                        self.cursor.execute("""
                            UPDATE producto_proveedor 
                            SET es_principal = 0 
                            WHERE producto_id = ?
                        """, (producto_id,))
                    
                    self.cursor.execute("""
                        INSERT INTO producto_proveedor (producto_id, proveedor_id, es_principal, notas)
                        VALUES (?, ?, ?, ?)
                    """, (producto_id, prov_id, 1 if var_principal.get() else 0, notas))
                    self.conn.commit()
                    cargar_proveedores()
                    dlg.destroy()
                except sqlite3.Error as e:
                    messagebox.showerror("Error", str(e), parent=dlg)
            
            fb = tk.Frame(dlg, pady=8)
            fb.pack()
            tk.Button(fb, text="➕ Agregar", command=confirmar,
                      bg='#27ae60', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=12, pady=5).pack(side='left', padx=3)
            tk.Button(fb, text="❌ Cancelar", command=dlg.destroy,
                      bg='#95a5a6', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=12, pady=5).pack(side='left', padx=3)
        
        def quitar_proveedor():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un proveedor para quitar", parent=ventana)
                return
            vals = tree.item(sel[0])['values']
            pp_id = vals[0]
            nombre_prov = vals[1]
            
            if messagebox.askyesno("Confirmar",
                f"¿Quitar asociación con '{nombre_prov}'?", parent=ventana):
                try:
                    self.cursor.execute("DELETE FROM producto_proveedor WHERE id = ?", (pp_id,))
                    self.conn.commit()
                    cargar_proveedores()
                except sqlite3.Error as e:
                    messagebox.showerror("Error", str(e), parent=ventana)
        
        def editar_notas_proveedor():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un proveedor para editar",
                                       parent=ventana)
                return
            vals = tree.item(sel[0])['values']
            pp_id      = vals[0]
            prov_nombre = vals[1]
            notas_act  = vals[3] if len(vals) > 3 else ''

            dlg = tk.Toplevel(ventana)
            dlg.title(f"Editar — {prov_nombre}")
            dlg.geometry("380x170")
            dlg.resizable(False, False)
            dlg.transient(ventana)
            dlg.grab_set()
            dlg.configure(bg='#f8fafc')

            tk.Label(dlg, text=f"Notas para: {prov_nombre}",
                     font=('Arial', 10, 'bold'), bg='#f8fafc').pack(pady=(14, 4))
            entry_notas = tk.Entry(dlg, width=42, font=('Arial', 10))
            entry_notas.insert(0, notas_act)
            entry_notas.pack(padx=16)
            entry_notas.focus_set()

            def guardar_notas(event=None):
                nuevas = entry_notas.get().strip()
                try:
                    self.cursor.execute(
                        "UPDATE producto_proveedor SET notas=? WHERE id=?",
                        (nuevas or None, pp_id))
                    self.conn.commit()
                    cargar_proveedores()
                    dlg.destroy()
                except sqlite3.Error as e:
                    messagebox.showerror("Error", str(e), parent=dlg)

            entry_notas.bind('<Return>', guardar_notas)
            fb = tk.Frame(dlg, bg='#f8fafc')
            fb.pack(pady=10)
            tk.Button(fb, text="💾 Guardar", command=guardar_notas,
                      bg='#3498db', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=12, pady=4).pack(side='left', padx=5)
            tk.Button(fb, text="Cancelar", command=dlg.destroy,
                      bg='#6b7280', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=4).pack(side='left')

        def marcar_principal():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un proveedor", parent=ventana)
                return
            vals = tree.item(sel[0])['values']
            pp_id = vals[0]
            
            try:
                # Quitar principal de todos
                self.cursor.execute("""
                    UPDATE producto_proveedor 
                    SET es_principal = 0 
                    WHERE producto_id = ?
                """, (producto_id,))
                # Marcar este como principal
                self.cursor.execute("""
                    UPDATE producto_proveedor 
                    SET es_principal = 1 
                    WHERE id = ?
                """, (pp_id,))
                self.conn.commit()
                cargar_proveedores()
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e), parent=ventana)
        
        tk.Button(toolbar, text="➕ Agregar Proveedor", command=agregar_proveedor,
                  bg='#27ae60', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=10, pady=4).pack(side='left', padx=3)
        tk.Button(toolbar, text="⭐ Marcar como Principal", command=marcar_principal,
                  bg='#f39c12', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=10, pady=4).pack(side='left', padx=3)
        tk.Button(toolbar, text="✏️ Editar Notas", command=editar_notas_proveedor,
                  bg='#3498db', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=10, pady=4).pack(side='left', padx=3)
        tk.Button(toolbar, text="🗑️ Quitar", command=quitar_proveedor,
                  bg='#e74c3c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=10, pady=4).pack(side='left', padx=3)
        
        # Tabla
        frame_tabla = tk.Frame(ventana, bg='#eceff4')
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(frame_tabla,
            columns=('ID', 'Proveedor', 'Principal', 'Notas'),
            show='headings', selectmode='browse')
        
        tree.heading('ID', text='ID')
        tree.heading('Proveedor', text='Proveedor')
        tree.heading('Principal', text='Principal')
        tree.heading('Notas', text='Notas')
        
        tree.column('ID', width=0, stretch=False)
        tree.column('Proveedor', width=250)
        tree.column('Principal', width=80)
        tree.column('Notas', width=300)
        
        tree.tag_configure('principal', background='#fff9e6')
        
        scroll_y = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scroll_x = ttk.Scrollbar(frame_tabla, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        
        tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        frame_tabla.grid_rowconfigure(0, weight=1)
        frame_tabla.grid_columnconfigure(0, weight=1)
        
        def cargar_proveedores():
            tree.delete(*tree.get_children())
            self.cursor.execute("""
                SELECT pp.id, prov.nombre, pp.es_principal, pp.notas
                FROM producto_proveedor pp
                JOIN proveedores prov ON pp.proveedor_id = prov.id
                WHERE pp.producto_id = ?
                ORDER BY pp.es_principal DESC, prov.nombre
            """, (producto_id,))
            
            for row in self.cursor.fetchall():
                pp_id, nombre, es_principal, notas = row
                tag = 'principal' if es_principal else ''
                tree.insert('', 'end', values=(
                    pp_id, nombre,
                    '⭐ Sí' if es_principal else 'No',
                    notas or ''
                ), tags=(tag,))
        
        cargar_proveedores()
        
        # Nota informativa
        nota = tk.Frame(ventana, bg='#e8f4f8', pady=6)
        nota.pack(fill='x', padx=10, pady=(0, 10))
        tk.Label(nota, text="💡 El proveedor principal se usará por defecto en presupuestos de compra.",
                 font=('Arial', 8), bg='#e8f4f8', fg='#2c3e50').pack()
        
        ventana.transient(ventana_padre)
        ventana.grab_set()
    
    def generar_presupuesto_compra(self):
        """
        Genera el presupuesto de compra basado en pedidos confirmados (Programadas /
        Parcialmente Entregadas) versus stock disponible actual.
        Muestra cada producto desglosado por cotización.
        Abre una ventana de vista previa donde el usuario puede ajustar
        las cantidades antes de exportar el PDF.
        """
        # ── Consulta por (cotización, producto) ────────────────────────────
        self.cursor.execute("""
            SELECT * FROM (
                SELECT
                    c.id                                                    AS cot_id,
                    c.folio,
                    COALESCE(
                        (SELECT se.referencia FROM seguimiento_etapas se
                         WHERE se.cotizacion_id = c.id AND se.etapa = 'Orden de Compra'
                           AND se.referencia IS NOT NULL AND se.referencia != ''
                         LIMIT 1),
                        NULLIF(c.orden_compra, '')
                    )                                                       AS oc_ref,
                    p.id                                                    AS pid,
                    p.codigo,
                    p.nombre,
                    p.unidad_medida,
                    p.stock_actual,
                    cd.cantidad                                             AS total_pedido,
                    COALESCE(
                        (SELECT SUM(ep.cantidad_entregada)
                         FROM entregas_parciales ep
                         WHERE ep.cotizacion_id = cd.cotizacion_id
                           AND ep.producto_id   = cd.producto_id),
                        0
                    )                                                       AS ya_entregado,
                    (cd.cantidad - COALESCE(
                        (SELECT SUM(ep.cantidad_entregada)
                         FROM entregas_parciales ep
                         WHERE ep.cotizacion_id = cd.cotizacion_id
                           AND ep.producto_id   = cd.producto_id),
                        0
                    ))                                                      AS pendiente,
                    COALESCE(
                        (SELECT MAX(cd2.costo_unitario)
                         FROM compra_detalle cd2
                         WHERE cd2.producto_id = p.id),
                        p.precio_base
                    )                                                       AS costo_max,
                    COALESCE(
                        (SELECT pr.nombre
                         FROM producto_proveedor pp
                         JOIN proveedores pr ON pr.id = pp.proveedor_id
                         WHERE pp.producto_id = p.id AND pp.es_principal = 1
                         LIMIT 1),
                        ''
                    )                                                       AS proveedor_principal
                FROM cotizacion_detalle cd
                INNER JOIN cotizaciones c  ON cd.cotizacion_id = c.id
                INNER JOIN productos p     ON cd.producto_id   = p.id
                WHERE c.estado IN ('Programada', 'Parcialmente Entregada')
            ) sub
            WHERE sub.pendiente > 0
            ORDER BY sub.folio, sub.nombre
        """)

        filas = self.cursor.fetchall()

        if not filas:
            messagebox.showinfo(
                "Sin datos",
                "No hay productos con entrega pendiente en cotizaciones Programadas.\n\n"
                "El presupuesto se genera a partir de cotizaciones en estado "
                "'Programada' o 'Parcialmente Entregada'."
            )
            return

        # ── Ventana de vista previa / ajuste ───────────────────────────────
        ventana = tk.Toplevel(self.root)
        ventana.title("Presupuesto de Compra — Vista Previa")
        ventana.geometry("1100x640")
        ventana.transient(self.root)
        ventana.grab_set()

        # Cabecera informativa
        frame_info = tk.Frame(ventana, bg='#16a085', pady=8)
        frame_info.pack(fill='x')
        tk.Label(
            frame_info,
            text="🛒  Presupuesto de Compra  —  basado en pedidos confirmados vs. stock actual",
            font=('Arial', 11, 'bold'), bg='#16a085', fg='white'
        ).pack()
        tk.Label(
            frame_info,
            text="Revisa y ajusta las cantidades antes de exportar. "
                 "Solo se exportarán filas con cantidad a comprar > 0.",
            font=('Arial', 9), bg='#16a085', fg='#d5f5ef'
        ).pack()

        # ── Tabla editable ─────────────────────────────────────────────────
        frame_tabla = tk.Frame(ventana)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=8)

        cols = ('_key', 'Cotización', 'O.C.', 'Producto', 'Unidad',
                'Stock\nActual', 'Pendiente\nEntregar', 'Faltante\nStock',
                'A Comprar\n(editable)', 'Costo Máx.', 'Subtotal Est.',
                'Proveedor Principal')
        tree = ttk.Treeview(frame_tabla, columns=cols, show='headings', selectmode='browse')

        anchos = [0, 110, 100, 220, 60, 75, 90, 80, 100, 95, 95, 140]
        for col, ancho in zip(cols, anchos):
            tree.heading(col, text=col)
            tree.column(col, width=ancho, minwidth=ancho)
        tree.column('_key', stretch=False, width=0)

        scroll_y = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scroll_x = ttk.Scrollbar(frame_tabla, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        frame_tabla.grid_rowconfigure(0, weight=1)
        frame_tabla.grid_columnconfigure(0, weight=1)

        # Colores por estado de stock
        tree.tag_configure('faltante', background='#fde8e8')
        tree.tag_configure('ok',       background='#eafaf1')

        # Almacenamos datos en dict para edición  key = (cot_id, pid)
        datos_filas = {}

        for fila in filas:
            (cot_id, folio, oc_ref, pid, codigo, nombre, unidad, stock_actual,
             total_pedido, ya_entregado, pendiente, costo_max, proveedor) = fila

            faltante   = max(0.0, pendiente - stock_actual)
            a_comprar  = faltante
            subtotal   = a_comprar * costo_max
            tag        = 'faltante' if faltante > 0 else 'ok'
            key_str    = f"{cot_id}|{pid}"
            oc_txt     = oc_ref or 'Sin OC'

            iid = tree.insert('', 'end', tags=(tag,), values=(
                key_str,
                folio,
                oc_txt,
                nombre,
                unidad or 'Pza',
                f"{stock_actual:.2f}",
                f"{pendiente:.2f}",
                f"{faltante:.2f}",
                f"{a_comprar:.2f}",
                f"${costo_max:,.2f}",
                f"${subtotal:,.2f}",
                proveedor or 'Sin proveedor',
            ))

            datos_filas[iid] = {
                'cot_id':    cot_id,
                'folio':     folio,
                'oc':        oc_ref or '',
                'producto_id': pid,
                'codigo':    codigo,
                'nombre':    nombre,
                'unidad':    unidad or 'Pza',
                'stock_actual': stock_actual,
                'pendiente': pendiente,
                'faltante':  faltante,
                'a_comprar': a_comprar,
                'costo_max': costo_max,
                'proveedor': proveedor or '',
            }

        # Totales en pie de tabla
        frame_totales = tk.Frame(ventana, bg='#ecf0f1', pady=6)
        frame_totales.pack(fill='x', padx=10)

        lbl_total_est = tk.Label(
            frame_totales,
            text="Total estimado: $0.00",
            font=('Arial', 11, 'bold'), bg='#ecf0f1', fg='#16a085'
        )
        lbl_total_est.pack(side='right', padx=15)

        def recalcular_total():
            total = sum(
                d['a_comprar'] * d['costo_max']
                for d in datos_filas.values()
                if d['a_comprar'] > 0
            )
            lbl_total_est.config(text=f"Total estimado: ${total:,.2f}")

        recalcular_total()

        # ── Edición de cantidad a comprar ──────────────────────────────────
        def editar_a_comprar(event=None):
            sel = tree.selection()
            if not sel:
                return
            iid = sel[0]
            d = datos_filas[iid]

            nueva = simpledialog.askfloat(
                "Editar Cantidad a Comprar",
                f"Cotización: {d['folio']}  OC: {d['oc'] or 'Sin OC'}\n"
                f"Producto: {d['nombre']}\n"
                f"Stock actual: {d['stock_actual']:.2f}\n"
                f"Pendiente entregar: {d['pendiente']:.2f}\n"
                f"Faltante en stock: {d['faltante']:.2f}\n\n"
                f"Cantidad a comprar:",
                initialvalue=d['a_comprar'],
                minvalue=0.0,
                parent=ventana
            )
            if nueva is None:
                return

            d['a_comprar'] = nueva
            subtotal = nueva * d['costo_max']

            vals = list(tree.item(iid)['values'])
            vals[8]  = f"{nueva:.2f}"
            vals[10] = f"${subtotal:,.2f}"
            tree.item(iid, values=vals)
            recalcular_total()

        tree.bind('<Double-1>', editar_a_comprar)

        # ── Botones de acción ──────────────────────────────────────────────
        frame_btn = tk.Frame(ventana, pady=8)
        frame_btn.pack(fill='x', padx=10)

        tk.Button(
            frame_btn, text="✏️ Editar Cantidad (o doble clic)",
            command=editar_a_comprar,
            bg='#f39c12', fg='white', font=('Arial', 9, 'bold'),
            cursor='hand2', padx=12, pady=6
        ).pack(side='left', padx=5)

        tk.Button(
            frame_btn, text="🔄 Restablecer todo al faltante",
            command=lambda: _restablecer_todo(),
            bg='#3498db', fg='white', font=('Arial', 9, 'bold'),
            cursor='hand2', padx=12, pady=6
        ).pack(side='left', padx=5)

        def _restablecer_todo():
            for iid, d in datos_filas.items():
                d['a_comprar'] = d['faltante']
                vals = list(tree.item(iid)['values'])
                vals[8]  = f"{d['faltante']:.2f}"
                vals[10] = f"${d['faltante'] * d['costo_max']:,.2f}"
                tree.item(iid, values=vals)
            recalcular_total()

        tk.Button(
            frame_btn, text="📄 Exportar Presupuesto PDF",
            command=lambda: _exportar_pdf(modo='presupuesto'),
            bg='#16a085', fg='white', font=('Arial', 10, 'bold'),
            cursor='hand2', padx=18, pady=6
        ).pack(side='right', padx=5)

        tk.Button(
            frame_btn, text="🏭 Exportar Lista de Compras PDF",
            command=lambda: _exportar_pdf(modo='lista'),
            bg='#1a4b8c', fg='white', font=('Arial', 10, 'bold'),
            cursor='hand2', padx=18, pady=6
        ).pack(side='right', padx=5)

        tk.Button(
            frame_btn, text="❌ Cerrar",
            command=ventana.destroy,
            bg='#95a5a6', fg='white', font=('Arial', 10, 'bold'),
            cursor='hand2', padx=18, pady=6
        ).pack(side='right', padx=5)

        def _exportar_pdf(modo='presupuesto'):
            productos_pdf = [
                d for d in datos_filas.values() if d['a_comprar'] > 0
            ]
            if not productos_pdf:
                messagebox.showwarning(
                    "Sin productos",
                    "Todas las cantidades a comprar son 0.\n"
                    "Ajusta al menos una cantidad antes de exportar.",
                    parent=ventana
                )
                return

            if modo == 'presupuesto':
                nombre_default = f"Presupuesto_Compra_{datetime.now().strftime('%Y%m%d')}.pdf"
                titulo_dlg = "Guardar Presupuesto de Compra"
            else:
                nombre_default = f"Lista_Compras_{datetime.now().strftime('%Y%m%d')}.pdf"
                titulo_dlg = "Guardar Lista de Compras"

            from tkinter import filedialog
            ruta = filedialog.asksaveasfilename(
                title=titulo_dlg,
                defaultextension=".pdf",
                initialfile=nombre_default,
                filetypes=[("PDF files", "*.pdf")],
                parent=ventana
            )
            if not ruta:
                return

            try:
                gen = GeneradorPDFCLY()
                if modo == 'presupuesto':
                    ok = gen.generar_presupuesto_compra(productos_pdf, ruta)
                else:
                    ok = gen.generar_lista_compras(productos_pdf, ruta)

                if ok:
                    messagebox.showinfo("Éxito", f"PDF generado:\n{ruta}", parent=ventana)
                    if os.name == 'nt':
                        os.startfile(ruta)
                    else:
                        os.system(f'open "{ruta}"')
                else:
                    messagebox.showerror("Error", "No se pudo generar el PDF", parent=ventana)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=ventana)
    
    
    # ── PROVEEDORES ────────────────────────────────────────────────────────
    def cargar_proveedores(self):
        """Carga la lista de proveedores en la tabla"""
        for item in self.tree_proveedores.get_children():
            self.tree_proveedores.delete(item)
        buscar = self.entry_buscar_proveedor.get().strip()
        if buscar:
            self.cursor.execute("""
                SELECT id, nombre, rfc, regimen_fiscal, cp_fiscal,
                       contacto, telefono, email, notas
                FROM proveedores
                WHERE nombre LIKE ? OR rfc LIKE ? OR contacto LIKE ?
                ORDER BY nombre
            """, (f'%{buscar}%', f'%{buscar}%', f'%{buscar}%'))
        else:
            self.cursor.execute("""
                SELECT id, nombre, rfc, regimen_fiscal, cp_fiscal,
                       contacto, telefono, email, notas
                FROM proveedores ORDER BY nombre
            """)
        for row in self.cursor.fetchall():
            self.tree_proveedores.insert('', 'end', values=row)

    def nuevo_proveedor(self):
        self._ventana_proveedor(modo='nuevo')

    def editar_proveedor(self):
        sel = self.tree_proveedores.selection()
        if not sel:
            messagebox.showwarning("Advertencia", "Selecciona un proveedor para editar")
            return
        prov_id = self.tree_proveedores.item(sel[0])['values'][0]
        self._ventana_proveedor(modo='editar', prov_id=prov_id)

    def eliminar_proveedor(self):
        sel = self.tree_proveedores.selection()
        if not sel:
            messagebox.showwarning("Advertencia", "Selecciona un proveedor para eliminar")
            return
        prov_id = self.tree_proveedores.item(sel[0])['values'][0]
        nombre  = self.tree_proveedores.item(sel[0])['values'][1]
        if messagebox.askyesno("Confirmar",
                               f"¿Eliminar al proveedor '{nombre}'?"):
            try:
                self.cursor.execute("DELETE FROM proveedores WHERE id = ?", (prov_id,))
                self.conn.commit()
                self.cargar_proveedores()
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e))

    def _ventana_proveedor(self, modo='nuevo', prov_id=None, _prefill=None, _callback=None):
        """Ventana para crear o editar proveedor con datos fiscales SAT."""
        REGIMENES = [
            ('601', 'General de Ley Personas Morales'),
            ('603', 'Personas Morales con Fines no Lucrativos'),
            ('605', 'Sueldos y Salarios e Ingresos Asimilados'),
            ('606', 'Arrendamiento'),
            ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
            ('608', 'Demás ingresos'),
            ('610', 'Residentes en el Extranjero sin EP en México'),
            ('611', 'Ingresos por Dividendos'),
            ('612', 'Personas Físicas con Actividades Empresariales'),
            ('614', 'Ingresos por intereses'),
            ('616', 'Sin obligaciones fiscales'),
            ('620', 'Sociedades Cooperativas de Producción'),
            ('621', 'Incorporación Fiscal'),
            ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas'),
            ('623', 'Opcional para Grupos de Sociedades'),
            ('624', 'Coordinados'),
            ('625', 'Actividades Empresariales vía Plataformas Tecnológicas'),
            ('626', 'RESICO – Simplificado de Confianza'),
        ]
        reg_opts = [f"{c} – {n}" for c, n in REGIMENES]

        datos = {}
        if _prefill:
            datos.update(_prefill)
        if modo == 'editar' and prov_id:
            self.cursor.execute("""
                SELECT nombre, razon_social, rfc, direccion, contacto,
                       telefono, email, notas, regimen_fiscal, cp_fiscal
                FROM proveedores WHERE id = ?
            """, (prov_id,))
            row = self.cursor.fetchone()
            if row:
                keys = ['nombre', 'razon_social', 'rfc', 'direccion', 'contacto',
                        'telefono', 'email', 'notas', 'regimen_fiscal', 'cp_fiscal']
                datos = {k: (v or '') for k, v in zip(keys, row)}

        ventana = tk.Toplevel(self.root)
        ventana.title('Nuevo Proveedor' if modo == 'nuevo' else f"Editar Proveedor — {datos.get('nombre','')}")
        ventana.geometry('560x580')
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()

        hdr = tk.Frame(ventana, bg='#92400e', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🏭  ' + ('Nuevo Proveedor' if modo == 'nuevo' else 'Editar Proveedor'),
                 font=('Arial', 11, 'bold'), bg='#92400e', fg='white').pack(side='left', padx=12)

        canvas = tk.Canvas(ventana, bg='#f1f5f9', highlightthickness=0)
        sb = ttk.Scrollbar(ventana, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        inner = tk.Frame(canvas, bg='#f1f5f9')
        wid = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))

        def section(parent, titulo, color):
            hf = tk.Frame(parent, bg=color, pady=4)
            hf.pack(fill='x', padx=12, pady=(10, 0))
            tk.Label(hf, text=titulo, font=('Arial', 9, 'bold'),
                     bg=color, fg='white').pack(side='left', padx=8)
            fr = tk.Frame(parent, bg='#ffffff', padx=14, pady=8,
                          highlightbackground='#e2e8f0', highlightthickness=1)
            fr.pack(fill='x', padx=12)
            fr.grid_columnconfigure(1, weight=1)
            return fr

        def field(parent, row, label, wtype='entry', width=38, values=None,
                  required=False, height=3):
            lbl = label + ('*' if required else '')
            tk.Label(parent, text=lbl,
                     font=('Arial', 9, 'bold' if required else 'normal'),
                     bg='#ffffff', fg='#374151', anchor='w').grid(
                row=row, column=0, sticky='w', padx=(0, 10), pady=4)
            if wtype == 'combo':
                w = ttk.Combobox(parent, values=values or [], state='readonly',
                                 width=width - 2, font=('Arial', 9))
            elif wtype == 'text':
                w = tk.Text(parent, width=width, height=height,
                            font=('Arial', 9), relief='solid', bd=1)
            else:
                w = tk.Entry(parent, width=width, font=('Arial', 9),
                             relief='solid', bd=1)
            w.grid(row=row, column=1, sticky='ew', pady=4)
            return w

        # Sección General
        sec1 = section(inner, '📦  Datos Generales', '#92400e')
        e_nombre  = field(sec1, 0, 'Nombre', required=True)
        e_nombre.insert(0, datos.get('nombre', ''))
        e_razon   = field(sec1, 1, 'Razón Social')
        e_razon.insert(0, datos.get('razon_social', ''))
        e_rfc     = field(sec1, 2, 'RFC')
        e_rfc.insert(0, datos.get('rfc', ''))
        e_dir     = field(sec1, 3, 'Dirección', 'text', height=2)
        e_dir.insert('1.0', datos.get('direccion', ''))

        # Sección Contacto
        sec2 = section(inner, '📞  Contacto', '#374151')
        e_contacto = field(sec2, 0, 'Persona de Contacto')
        e_contacto.insert(0, datos.get('contacto', ''))
        e_tel      = field(sec2, 1, 'Teléfono')
        e_tel.insert(0, datos.get('telefono', ''))
        e_email    = field(sec2, 2, 'Email')
        e_email.insert(0, datos.get('email', ''))
        e_notas    = field(sec2, 3, 'Notas', 'text', height=2)
        e_notas.insert('1.0', datos.get('notas', ''))

        # Sección SAT
        sec3 = section(inner, '🏛️  Datos Fiscales SAT', '#7c3aed')
        tk.Label(sec3, text='Datos del emisor para CFDIs de compra.',
                 font=('Arial', 7, 'italic'), bg='#ffffff',
                 fg='#9ca3af').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))
        c_regimen = field(sec3, 1, 'Régimen Fiscal', 'combo', values=reg_opts)
        cur_reg = datos.get('regimen_fiscal', '')
        if cur_reg:
            match = next((o for o in reg_opts if o.startswith(cur_reg)), '')
            if match:
                c_regimen.set(match)
        e_cp = field(sec3, 2, 'C.P. Fiscal')
        e_cp.insert(0, datos.get('cp_fiscal', ''))
        tk.Label(sec3, text='',bg='#ffffff').grid(row=3, column=0, pady=(0,6))

        # Pie
        foot = tk.Frame(ventana, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')

        def guardar(event=None):
            nombre = e_nombre.get().strip()
            if not nombre:
                messagebox.showwarning('Advertencia', 'El nombre es obligatorio', parent=ventana)
                return
            reg_val = c_regimen.get().split(' – ')[0] if c_regimen.get() else ''
            vals_dict = {
                'nombre':        nombre,
                'razon_social':  e_razon.get().strip(),
                'rfc':           e_rfc.get().strip().upper(),
                'direccion':     e_dir.get('1.0', 'end-1c').strip(),
                'contacto':      e_contacto.get().strip(),
                'telefono':      e_tel.get().strip(),
                'email':         e_email.get().strip(),
                'notas':         e_notas.get('1.0', 'end-1c').strip(),
                'regimen_fiscal':reg_val,
                'cp_fiscal':     e_cp.get().strip(),
            }
            try:
                if modo == 'nuevo':
                    self.cursor.execute("""
                        INSERT INTO proveedores
                        (nombre, razon_social, rfc, direccion, contacto,
                         telefono, email, notas, regimen_fiscal, cp_fiscal)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, tuple(vals_dict.values()))
                else:
                    self.cursor.execute("""
                        UPDATE proveedores SET
                        nombre=?, razon_social=?, rfc=?, direccion=?,
                        contacto=?, telefono=?, email=?, notas=?,
                        regimen_fiscal=?, cp_fiscal=?
                        WHERE id=?
                    """, (*vals_dict.values(), prov_id))
                self.conn.commit()
                new_prov_id = self.cursor.lastrowid if modo == 'nuevo' else prov_id
                self.cargar_proveedores()
                ventana.destroy()
                if _callback:
                    _callback(new_prov_id)
            except sqlite3.Error as e:
                messagebox.showerror('Error', str(e), parent=ventana)

        ventana.bind('<Return>', guardar)
        tk.Button(foot, text='💾 Guardar', command=guardar,
                  bg='#92400e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=12)
        tk.Button(foot, text='Cancelar', command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='right', padx=12)
        e_nombre.focus()


    def gestionar_categorias(self):
        """Ventana para gestionar categorías y subcategorías"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Gestión de Categorías")
        ventana.geometry("700x500")
        
        # Frame principal
        frame_principal = tk.Frame(ventana, padx=20, pady=20)
        frame_principal.pack(fill='both', expand=True)
        
        # === CATEGORÍAS ===
        frame_cat = tk.LabelFrame(frame_principal, text="Categorías", font=('Arial', 10, 'bold'))
        frame_cat.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Lista de categorías
        self.listbox_categorias = tk.Listbox(frame_cat, font=('Arial', 10))
        self.listbox_categorias.pack(fill='both', expand=True, padx=10, pady=10)
        self.listbox_categorias.bind('<<ListboxSelect>>', self.cargar_subcategorias_de_categoria)
        
        # Botones categorías
        frame_btn_cat = tk.Frame(frame_cat)
        frame_btn_cat.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_btn_cat,
            text="➕ Nueva",
            command=lambda: self.nueva_categoria(ventana),
            bg='#27ae60',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        tk.Button(
            frame_btn_cat,
            text="✏️ Editar",
            command=lambda: self.editar_categoria(ventana),
            bg='#f39c12',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            frame_btn_cat,
            text="🗑️ Eliminar",
            command=lambda: self.eliminar_categoria(ventana),
            bg='#e74c3c',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        # === SUBCATEGORÍAS ===
        frame_subcat = tk.LabelFrame(frame_principal, text="Subcategorías", font=('Arial', 10, 'bold'))
        frame_subcat.pack(side='right', fill='both', expand=True)
        
        # Lista de subcategorías
        self.listbox_subcategorias = tk.Listbox(frame_subcat, font=('Arial', 10))
        self.listbox_subcategorias.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Botones subcategorías
        frame_btn_subcat = tk.Frame(frame_subcat)
        frame_btn_subcat.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_btn_subcat,
            text="➕ Nueva",
            command=lambda: self.nueva_subcategoria(ventana),
            bg='#27ae60',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        tk.Button(
            frame_btn_subcat,
            text="✏️ Editar",
            command=lambda: self.editar_subcategoria(ventana),
            bg='#f39c12',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            frame_btn_subcat,
            text="🗑️ Eliminar",
            command=lambda: self.eliminar_subcategoria(ventana),
            bg='#e74c3c',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        # Cargar categorías
        self.cargar_lista_categorias()
        
        ventana.transient(self.root)
        ventana.grab_set()
    
    def cargar_lista_categorias(self):
        """Carga las categorías en el listbox"""
        self.listbox_categorias.delete(0, tk.END)
        self.cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        self.categorias_dict = {}
        for cat_id, nombre in self.cursor.fetchall():
            self.listbox_categorias.insert(tk.END, nombre)
            self.categorias_dict[nombre] = cat_id
    
    def cargar_subcategorias_de_categoria(self, event=None):
        """Carga las subcategorías de la categoría seleccionada"""
        self.listbox_subcategorias.delete(0, tk.END)
        
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            return
        
        categoria_nombre = self.listbox_categorias.get(seleccion[0])
        categoria_id = self.categorias_dict.get(categoria_nombre)
        
        if categoria_id:
            self.cursor.execute(
                "SELECT id, nombre FROM subcategorias WHERE categoria_id = ? ORDER BY nombre",
                (categoria_id,)
            )
            self.subcategorias_dict = {}
            for sub_id, nombre in self.cursor.fetchall():
                self.listbox_subcategorias.insert(tk.END, nombre)
                self.subcategorias_dict[nombre] = sub_id
    
    def nueva_categoria(self, ventana_padre):
        """Crea una nueva categoría"""
        nombre = tk.simpledialog.askstring("Nueva Categoría", "Nombre de la categoría:", parent=ventana_padre)
        if nombre:
            nombre = nombre.strip()
            if nombre:
                try:
                    self.cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
                    self.conn.commit()
                    self.cargar_lista_categorias()
                    messagebox.showinfo("Éxito", "Categoría creada correctamente", parent=ventana_padre)
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Ya existe una categoría con ese nombre", parent=ventana_padre)
    
    def editar_categoria(self, ventana_padre):
        """Renombra la categoría seleccionada"""
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una categoría para editar",
                                   parent=ventana_padre)
            return

        nombre_actual = self.listbox_categorias.get(seleccion[0])
        cat_id = self.categorias_dict.get(nombre_actual)

        # Mini-formulario
        dlg = tk.Toplevel(ventana_padre)
        dlg.title("Editar Categoría")
        dlg.geometry("340x130")
        dlg.resizable(False, False)
        dlg.transient(ventana_padre)
        dlg.grab_set()
        dlg.configure(bg='#f8fafc')

        tk.Label(dlg, text="Nuevo nombre:", font=('Arial', 10, 'bold'),
                 bg='#f8fafc').pack(pady=(16, 4))
        entry = tk.Entry(dlg, width=36, font=('Arial', 10))
        entry.insert(0, nombre_actual)
        entry.pack(padx=16)
        entry.select_range(0, 'end')
        entry.focus_set()

        def guardar(event=None):
            nuevo = entry.get().strip()
            if not nuevo:
                messagebox.showwarning("Advertencia", "El nombre no puede estar vacío",
                                       parent=dlg)
                return
            if nuevo == nombre_actual:
                dlg.destroy()
                return
            try:
                self.cursor.execute("UPDATE categorias SET nombre=? WHERE id=?",
                                    (nuevo, cat_id))
                self.conn.commit()
                self.cargar_lista_categorias()
                dlg.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Ya existe una categoría con ese nombre",
                                     parent=dlg)
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        entry.bind('<Return>', guardar)
        fb = tk.Frame(dlg, bg='#f8fafc')
        fb.pack(pady=10)
        tk.Button(fb, text="💾 Guardar", command=guardar,
                  bg='#f39c12', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=4).pack(side='left', padx=5)
        tk.Button(fb, text="Cancelar", command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=10, pady=4).pack(side='left')

    def editar_subcategoria(self, ventana_padre):
        """Renombra la subcategoría seleccionada"""
        seleccion = self.listbox_subcategorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una subcategoría para editar",
                                   parent=ventana_padre)
            return

        nombre_actual = self.listbox_subcategorias.get(seleccion[0])
        sub_id = self.subcategorias_dict.get(nombre_actual)

        dlg = tk.Toplevel(ventana_padre)
        dlg.title("Editar Subcategoría")
        dlg.geometry("340x130")
        dlg.resizable(False, False)
        dlg.transient(ventana_padre)
        dlg.grab_set()
        dlg.configure(bg='#f8fafc')

        tk.Label(dlg, text="Nuevo nombre:", font=('Arial', 10, 'bold'),
                 bg='#f8fafc').pack(pady=(16, 4))
        entry = tk.Entry(dlg, width=36, font=('Arial', 10))
        entry.insert(0, nombre_actual)
        entry.pack(padx=16)
        entry.select_range(0, 'end')
        entry.focus_set()

        def guardar(event=None):
            nuevo = entry.get().strip()
            if not nuevo:
                messagebox.showwarning("Advertencia", "El nombre no puede estar vacío",
                                       parent=dlg)
                return
            if nuevo == nombre_actual:
                dlg.destroy()
                return
            try:
                self.cursor.execute("UPDATE subcategorias SET nombre=? WHERE id=?",
                                    (nuevo, sub_id))
                self.conn.commit()
                self.cargar_subcategorias_de_categoria()
                dlg.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Ya existe una subcategoría con ese nombre",
                                     parent=dlg)
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        entry.bind('<Return>', guardar)
        fb = tk.Frame(dlg, bg='#f8fafc')
        fb.pack(pady=10)
        tk.Button(fb, text="💾 Guardar", command=guardar,
                  bg='#f39c12', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=4).pack(side='left', padx=5)
        tk.Button(fb, text="Cancelar", command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=10, pady=4).pack(side='left')

    def eliminar_categoria(self, ventana_padre):
        """Elimina la categoría seleccionada"""
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una categoría para eliminar", parent=ventana_padre)
            return
        
        categoria_nombre = self.listbox_categorias.get(seleccion[0])
        categoria_id = self.categorias_dict.get(categoria_nombre)
        
        respuesta = messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la categoría '{categoria_nombre}'?\n\nSe eliminarán también sus subcategorías.",
            parent=ventana_padre
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM subcategorias WHERE categoria_id = ?", (categoria_id,))
                self.cursor.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
                self.conn.commit()
                self.cargar_lista_categorias()
                self.listbox_subcategorias.delete(0, tk.END)
                messagebox.showinfo("Éxito", "Categoría eliminada correctamente", parent=ventana_padre)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar:\n{str(e)}", parent=ventana_padre)
    
    def nueva_subcategoria(self, ventana_padre):
        """Crea una nueva subcategoría"""
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Primero selecciona una categoría", parent=ventana_padre)
            return
        
        categoria_nombre = self.listbox_categorias.get(seleccion[0])
        categoria_id = self.categorias_dict.get(categoria_nombre)
        
        nombre = tk.simpledialog.askstring(
            "Nueva Subcategoría",
            f"Nombre de la subcategoría para '{categoria_nombre}':",
            parent=ventana_padre
        )
        
        if nombre:
            nombre = nombre.strip()
            if nombre:
                try:
                    self.cursor.execute(
                        "INSERT INTO subcategorias (categoria_id, nombre) VALUES (?, ?)",
                        (categoria_id, nombre)
                    )
                    self.conn.commit()
                    self.cargar_subcategorias_de_categoria()
                    messagebox.showinfo("Éxito", "Subcategoría creada correctamente", parent=ventana_padre)
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"No se pudo crear:\n{str(e)}", parent=ventana_padre)
    
    def eliminar_subcategoria(self, ventana_padre):
        """Elimina la subcategoría seleccionada"""
        seleccion = self.listbox_subcategorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una subcategoría para eliminar", parent=ventana_padre)
            return
        
        subcategoria_nombre = self.listbox_subcategorias.get(seleccion[0])
        subcategoria_id = self.subcategorias_dict.get(subcategoria_nombre)
        
        respuesta = messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la subcategoría '{subcategoria_nombre}'?",
            parent=ventana_padre
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM subcategorias WHERE id = ?", (subcategoria_id,))
                self.conn.commit()
                self.cargar_subcategorias_de_categoria()
                messagebox.showinfo("Éxito", "Subcategoría eliminada correctamente", parent=ventana_padre)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar:\n{str(e)}", parent=ventana_padre)
    
    # (removed - rebuilt in new ERP UI)
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
            values = (
                cot_id, folio, fecha, cliente,
                f'${total:,.2f}', estado_display,
                f'${entregado:,.2f}', oc_txt, oc_icon,
                fac_txt, fac_icon,
                f'${pagado:,.2f}', obs_txt,
            )
            self.tree_cotizaciones.insert('', 'end', values=values, tags=tags_finales)
    
    def nueva_cotizacion(self):
        """Abre ventana para crear nueva cotización"""
        ventana_cot = VentanaCotizacion(self.root, self.conn, self.cursor, UTILIDAD, modo='nueva')
        # Esperar a que se cierre la ventana y actualizar
        self.root.wait_window(ventana_cot.ventana)
        # Recargar cotizaciones y dashboard
        self.cargar_cotizaciones()
        self.actualizar_dashboard()
    
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
        ventana_cot = VentanaCotizacion(
            self.root, self.conn, self.cursor, UTILIDAD, 
            modo='editar', cotizacion_id=cotizacion_id
        )
        self.root.wait_window(ventana_cot.ventana)
        self.cargar_cotizaciones()
        self.actualizar_dashboard()
    
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
                self.actualizar_dashboard()
                
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
                self.actualizar_dashboard()
                
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
    def cargar_compras(self):
        """Carga la lista de compras"""
        for item in self.tree_compras.get_children():
            self.tree_compras.delete(item)
        
        buscar = self.entry_buscar_compra.get().strip()
        
        if buscar:
            self.cursor.execute("""
                SELECT c.id, c.folio, c.fecha_compra, p.nombre, c.ticket_referencia, c.total, m.nombre
                FROM compras c
                LEFT JOIN proveedores p ON c.proveedor_id = p.id
                LEFT JOIN metodos_pago m ON c.metodo_pago_id = m.id
                WHERE c.folio LIKE ? OR p.nombre LIKE ? OR c.ticket_referencia LIKE ?
                ORDER BY c.fecha_compra DESC
            """, (f'%{buscar}%', f'%{buscar}%', f'%{buscar}%'))
        else:
            self.cursor.execute("""
                SELECT c.id, c.folio, c.fecha_compra, p.nombre, c.ticket_referencia, c.total, m.nombre
                FROM compras c
                LEFT JOIN proveedores p ON c.proveedor_id = p.id
                LEFT JOIN metodos_pago m ON c.metodo_pago_id = m.id
                ORDER BY c.fecha_compra DESC
            """)
        
        for row in self.cursor.fetchall():
            row_list = list(row)
            row_list[4] = row[4] or 'Sin ref.'
            row_list[5] = f"${row[5]:,.2f}"
            self.tree_compras.insert('', 'end', values=row_list)
    
    def nueva_compra(self):
        """Abre ventana para nueva compra"""
        def _post_guardado():
            self.cargar_compras()
            self.actualizar_dashboard()
            # Refrescar stock si el módulo está cargado
            if hasattr(self, '_stock'):
                try:
                    self._stock.cargar_vista_stock()
                    self._stock.cargar_historial()
                except Exception:
                    pass

        ventana_compra = VentanaCompra(self.root, self.conn, self.cursor,
                                       modo='nueva', on_guardado=_post_guardado)
        self.root.wait_window(ventana_compra.ventana)
        # Asegurar refresco incluso si se cerró sin guardar
        self.cargar_compras()
        self.actualizar_dashboard()
    
    def editar_compra(self):
        """Edita la compra seleccionada"""
        seleccion = self.tree_compras.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una compra para editar")
            return
        
        item = self.tree_compras.item(seleccion[0])
        compra_id = item['values'][0]
        
        messagebox.showinfo(
            "En Desarrollo",
            "La función de editar compras estará disponible próximamente.\n\n" +
            "Por ahora, si necesitas corregir una compra:\n" +
            "1. Anota los datos\n" +
            "2. Elimínala (función próximamente)\n" +
            "3. Créala de nuevo con los datos correctos"
        )
    
    def ver_compra(self):
        """Ver detalle de compra"""
        seleccion = self.tree_compras.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una compra")
            return
        
        item = self.tree_compras.item(seleccion[0])
        compra_id = item['values'][0]
        
        # Obtener datos de la compra
        self.cursor.execute("""
            SELECT c.folio, c.fecha_compra, p.nombre, c.total, c.ticket_referencia, c.notas, m.nombre
            FROM compras c
            LEFT JOIN proveedores p ON c.proveedor_id = p.id
            LEFT JOIN metodos_pago m ON c.metodo_pago_id = m.id
            WHERE c.id = ?
        """, (compra_id,))
        
        compra = self.cursor.fetchone()
        if not compra:
            return
        
        folio, fecha, proveedor, total, ticket, notas, metodo = compra
        
        # Obtener productos
        self.cursor.execute("""
            SELECT p.codigo, p.nombre, cd.cantidad, cd.costo_unitario, cd.costo_total
            FROM compra_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.compra_id = ?
        """, (compra_id,))
        
        productos = self.cursor.fetchall()
        
        # Ventana de detalle
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle de Compra - {folio}")
        ventana.geometry("700x500")
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        # Información
        info = f"""FOLIO: {folio}
FECHA: {fecha}
PROVEEDOR: {proveedor or 'N/A'}
MÉTODO DE PAGO: {metodo or 'N/A'}
TICKET REF: {ticket or 'N/A'}

PRODUCTOS:"""
        
        tk.Label(frame, text=info, font=('Courier', 10), justify='left').pack(anchor='w')
        
        # Tabla de productos
        tree = ttk.Treeview(
            frame,
            columns=('Código', 'Producto', 'Cantidad', 'Costo Unit.', 'Total'),
            show='headings',
            height=10
        )
        
        for col in ('Código', 'Producto', 'Cantidad', 'Costo Unit.', 'Total'):
            tree.heading(col, text=col)
        
        tree.column('Código', width=80)
        tree.column('Producto', width=250)
        tree.column('Cantidad', width=80)
        tree.column('Costo Unit.', width=100)
        tree.column('Total', width=100)
        
        for prod in productos:
            tree.insert('', 'end', values=(
                prod[0], prod[1], f"{prod[2]:.2f}",
                f"${prod[3]:,.2f}", f"${prod[4]:,.2f}"
            ))
        
        tree.pack(fill='both', expand=True, pady=10)
        
        tk.Label(
            frame,
            text=f"TOTAL: ${total:,.2f}",
            font=('Arial', 14, 'bold'),
            fg='#e74c3c'
        ).pack(pady=10)
        
        if notas:
            tk.Label(frame, text=f"Notas: {notas}", font=('Arial', 9), fg='gray').pack()
        
        tk.Button(
            frame,
            text="Cerrar",
            command=ventana.destroy,
            bg='#95a5a6',
            fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2',
            padx=20,
            pady=8
        ).pack(pady=10)
        
        ventana.transient(self.root)
        ventana.grab_set()
    
        ventana.transient(self.root)
        ventana.grab_set()
    
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
                self.actualizar_dashboard()
                
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
                self.actualizar_dashboard()
                
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
                nuevo_estado = 'Pagada' if nuevo_total_pagado >= total_cot else estado_actual
                
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET monto_pagado = ?,
                        fecha_pago = ?,
                        estado = ?
                    WHERE id = ?
                """, (nuevo_total_pagado, fecha, nuevo_estado, cotizacion_id))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, nuevo_estado, fecha)

                self.conn.commit()
                
                if nuevo_estado == 'Pagada':
                    msg = f"Cotización {folio} marcada como PAGADA completamente."
                else:
                    msg = f"Pago de ${monto_nuevo:,.2f} registrado.\nTotal pagado: ${nuevo_total_pagado:,.2f} de ${total_cot:,.2f}"
                
                messagebox.showinfo("Éxito", msg, parent=ventana)
                ventana.destroy()
                self.cargar_cotizaciones()
                self.actualizar_dashboard()
                
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
                self.actualizar_dashboard()
                
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
        self.actualizar_dashboard()
        # Refrescar stock si el módulo está cargado
        if hasattr(self, '_stock'):
            try:
                self._stock.cargar_vista_stock()
                self._stock.cargar_historial()
            except Exception:
                pass
    
    def _cambiar_empresa(self):
        """Cierra la sesión actual y regresa al selector de empresa."""
        if not messagebox.askyesno(
            'Cambiar empresa',
            '¿Deseas cerrar la sesión actual y regresar al selector de empresa?',
            parent=self.root
        ):
            return
        # Cerrar BD actual
        try:
            self.conn.close()
        except Exception:
            pass
        # Destruir ventana principal
        self.root.destroy()
        # Abrir selector de empresa de nuevo
        from selector_empresa import mostrar_selector
        empresa = mostrar_selector()
        if empresa is None:
            return  # Cerró sin elegir → terminar
        # Abrir sistema con la nueva empresa
        new_root = tk.Tk()
        SistemaGestion(new_root, empresa=empresa)
        new_root.mainloop()

    def __del__(self):
        """Cierra la conexión a la base de datos al cerrar la aplicación"""
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == '__main__':
    # ── Selector de empresa ───────────────────────────────────────────────────
    empresa = mostrar_selector()

    if empresa is None:
        # Usuario cerró el selector sin elegir → no arrancar
        import sys
        sys.exit(0)

    # ── Sistema principal ─────────────────────────────────────────────────────
    root = tk.Tk()
    app  = SistemaGestion(root, empresa=empresa)
    root.mainloop()
