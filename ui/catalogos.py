#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/catalogos.py
Componente Catálogos — orquesta los tabs de Clientes, Productos, Proveedores y Compras.
La lógica de cada sección está en los mixins correspondientes.

Uso:
    from ui.catalogos import Catalogos
    self.catalogos = Catalogos(self)
    self.catalogos.crear_seccion()
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

from ui.utils import centrar_ventana as _centrar

from ui.catalogos_clientes_mixin     import _CatalogosClientesMixin
from ui.catalogos_productos_mixin    import _CatalogosProductosMixin
from ui.catalogos_proveedores_mixin  import _CatalogosProveedoresMixin
from ui.catalogos_exportar_mixin     import _CatalogosExportarMixin
from ui.catalogos_categorias_mixin   import _CatalogosCategoriassMixin
from ui.catalogos_compras_mixin      import _CatalogosComprasMixin


class Catalogos(
    _CatalogosClientesMixin,
    _CatalogosProductosMixin,
    _CatalogosProveedoresMixin,
    _CatalogosExportarMixin,
    _CatalogosCategoriassMixin,
    _CatalogosComprasMixin,
):
    """
    Componente de UI que encapsula los catálogos del sistema.
    Recibe `sistema` (instancia de SistemaGestion) como única dependencia.
    """
    def __init__(self, sistema):
        self.sistema = sistema
        self.conn    = sistema.conn
        self.cursor  = sistema.cursor
        self.root    = sistema.root
        self.C       = sistema.C

        # Widgets internos — creados en crear_seccion()
        self.tree_clientes        = None
        self.tree_productos       = None
        self.tree_proveedores     = None
        self.tree_compras         = None
        self.entry_buscar_cliente   = None
        self.entry_buscar_producto  = None
        self.entry_buscar_proveedor = None
        self.entry_buscar_compra    = None
        self.listbox_categorias     = None
        self.listbox_subcategorias  = None
        self.categorias_dict        = {}
        self.subcategorias_dict     = {}

    def _ventana_producto_prefill(self, datos, callback=None):
        """Abre la ventana de nuevo producto pre-llenada con datos del XML."""
        import tkinter as tk
        from tkinter import ttk, messagebox
        ventana = tk.Toplevel(self.root)
        ventana.title('Nuevo Producto (desde XML)')
        ventana.geometry('520x480')
        _centrar(ventana, self.root)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

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

    # ── Historial de precios ─────────────────────────────────────────────────
    def _registrar_precio_historial(self, producto_id, precio_nuevo,
                                     precio_anterior=None, motivo=None, fuente='manual'):
        """Registra un cambio de precio en producto_precio_historial.
        Solo inserta si el precio realmente cambió respecto al último registrado.
        """
        from datetime import date
        # Verificar si el precio cambió
        if precio_anterior is not None and abs(float(precio_nuevo) - float(precio_anterior)) < 0.001:
            return  # Sin cambio, no registrar

        self.cursor.execute("""
            INSERT INTO producto_precio_historial
                (producto_id, precio, fecha, motivo, fuente)
            VALUES (?, ?, ?, ?, ?)
        """, (producto_id, float(precio_nuevo), date.today().isoformat(),
              motivo, fuente))

    def crear_seccion(self):
        sec = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['catalogos'] = sec

        nb = ttk.Notebook(sec)
        nb.pack(fill='both', expand=True)
        self._notebook = nb

        def _actualizar_tabs():
            """Actualiza los contadores en los títulos de los tabs."""
            try:
                counts = {}
                self.cursor.execute("SELECT COUNT(*) FROM clientes")
                counts['cli'] = self.cursor.fetchone()[0]
                self.cursor.execute("SELECT COUNT(*) FROM productos")
                counts['prod'] = self.cursor.fetchone()[0]
                self.cursor.execute("SELECT COUNT(*) FROM proveedores")
                counts['prov'] = self.cursor.fetchone()[0]
                self.cursor.execute("SELECT COUNT(*) FROM compras")
                counts['comp'] = self.cursor.fetchone()[0]
                labels = [
                    f"👥  Clientes  [{counts['cli']}]",
                    f"📦  Productos  [{counts['prod']}]",
                    f"🏭  Proveedores  [{counts['prov']}]",
                    f"🛒  Compras  [{counts['comp']}]",
                ]
                for i, lbl in enumerate(labels):
                    try: nb.tab(i, text=lbl)
                    except Exception: pass
            except Exception:
                pass
        self._actualizar_tabs_catalogos = _actualizar_tabs

        # ── Tab Clientes ──────────────────────────────────────────────────
        tab_cli = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_cli, text='👥  Clientes')

        tb_cli = tk.Frame(tab_cli, bg=self.C['toolbar_bg'])
        tb_cli.pack(fill='x')
        tk.Frame(tab_cli, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self.sistema._toolbar_btn(tb_cli, '➕ Nuevo',    self.nuevo_cliente,   color=self.C['accent'], tip='Registrar nuevo cliente')
        self.sistema._toolbar_btn(tb_cli, '✏️ Editar',   self.editar_cliente)
        self.sistema._toolbar_btn(tb_cli, '🗑️ Eliminar', self.eliminar_cliente, peligro=True)

        ff_cli = tk.Frame(tab_cli, bg=self.C['toolbar_bg'], pady=4)
        ff_cli.pack(fill='x')
        tk.Label(ff_cli, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_cliente = tk.Entry(ff_cli, font=('Arial', 9), width=30)
        self.entry_buscar_cliente.pack(side='left', padx=4)
        self.entry_buscar_cliente.bind('<KeyRelease>', lambda e: self.cargar_clientes())
        self.sistema._toolbar_btn(ff_cli, '🔍', self.cargar_clientes)
        self.sistema._toolbar_sep(ff_cli)
        self.sistema._toolbar_btn(ff_cli, '📊 CSV', self.exportar_csv_clientes, color='#065f46')

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
        self.sistema._configurar_sorting_treeview(self.tree_clientes)
        # Barra de estado del tab
        self._status_cli = tk.Label(tab_cli, text='',
            font=('Arial', 8), bg='#dde3ec', fg='#6b7280', anchor='w', padx=8, pady=3)
        self._status_cli.pack(fill='x', side='bottom')
        self.cargar_clientes()

        # ── Tab Productos ─────────────────────────────────────────────────
        tab_prod = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_prod, text='📦  Productos')

        tb_prod = tk.Frame(tab_prod, bg=self.C['toolbar_bg'])
        tb_prod.pack(fill='x')
        tk.Frame(tab_prod, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self.sistema._toolbar_btn(tb_prod, '➕ Nuevo',      self.nuevo_producto,    color=self.C['accent'])
        self.sistema._toolbar_btn(tb_prod, '✏️ Editar',     self.editar_producto)
        self.sistema._toolbar_btn(tb_prod, '🗑️ Eliminar',   self.eliminar_producto,  peligro=True)
        self.sistema._toolbar_sep(tb_prod)
        self.sistema._toolbar_btn(tb_prod, '📋 Categorías', self.gestionar_categorias, tip='Gestionar categorías y subcategorías de productos')

        ff_prod = tk.Frame(tab_prod, bg=self.C['toolbar_bg'], pady=4)
        ff_prod.pack(fill='x')
        tk.Label(ff_prod, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_producto = tk.Entry(ff_prod, font=('Arial', 9), width=30)
        self.entry_buscar_producto.pack(side='left', padx=4)
        self.entry_buscar_producto.bind('<KeyRelease>', lambda e: self.cargar_productos())
        self.sistema._toolbar_btn(ff_prod, '🔍', self.cargar_productos)
        self.sistema._toolbar_sep(ff_prod)
        self.sistema._toolbar_btn(ff_prod, '📊 CSV', self.exportar_csv_productos, color='#065f46')
        self.sistema._toolbar_sep(ff_prod)
        tk.Label(ff_prod, text='Usados en:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=(6, 2))
        self._precio_revision_periodo = ttk.Combobox(ff_prod, values=[
            'Últimos 3 meses', 'Últimos 6 meses', 'Últimos 12 meses', 'Todo el tiempo'
        ], state='readonly', width=16, font=('Arial', 9))
        self._precio_revision_periodo.set('Últimos 6 meses')
        self._precio_revision_periodo.pack(side='left', padx=(0, 4))
        self.sistema._toolbar_btn(ff_prod, '⚠ Precios por revisar', self.filtrar_precios_desactualizados,
            color='#d97706', tip='Solo productos usados en cotizaciones recientes con precio desactualizado.')

        ft_prod = tk.Frame(tab_prod, bg=self.C['content_bg'])
        ft_prod.pack(fill='both', expand=True, padx=8, pady=8)
        cols_prod = ('ID', 'Código', 'Nombre', 'Categoría',
                     'Unidad', 'Precio Base', 'IVA', 'P.Venta',
                     'Stock', 'Mín', 'Proveedor ⭐', 'Precio actualizado')
        self.tree_productos = ttk.Treeview(
            ft_prod, columns=cols_prod, show='headings', selectmode='browse')
        widths_prod = {'ID': 0, 'Código': 82, 'Nombre': 210, 'Categoría': 105,
                       'Unidad': 55, 'Precio Base': 88, 'IVA': 38, 'P.Venta': 88,
                       'Stock': 58, 'Mín': 44, 'Proveedor ⭐': 140,
                       'Precio actualizado': 110}
        for col in cols_prod:
            anchor = 'e' if col in ('Precio Base', 'P.Venta', 'Stock', 'Mín') else 'w'
            self.tree_productos.heading(col, text=col, anchor=anchor)
            self.tree_productos.column(col, width=widths_prod[col],
                                       minwidth=widths_prod[col],
                                       stretch=(col == 'Nombre'), anchor=anchor)
        self.tree_productos.column('ID', stretch=False)
        # Tags de frescura de precio
        self.tree_productos.tag_configure('precio_ok',   foreground='#16a34a')
        self.tree_productos.tag_configure('precio_warn', foreground='#d97706')
        self.tree_productos.tag_configure('precio_old',  foreground='#dc2626')
        # Tag de stock bajo
        self.tree_productos.tag_configure('stock_bajo',
            background='#fef3c7', foreground='#92400e')
        sc = ttk.Scrollbar(ft_prod, orient='vertical',   command=self.tree_productos.yview)
        sx = ttk.Scrollbar(ft_prod, orient='horizontal', command=self.tree_productos.xview)
        self.tree_productos.configure(yscrollcommand=sc.set, xscrollcommand=sx.set)
        self.tree_productos.grid(row=0, column=0, sticky='nsew')
        sc.grid(row=0, column=1, sticky='ns')
        sx.grid(row=1, column=0, sticky='ew')
        ft_prod.grid_rowconfigure(0, weight=1)
        ft_prod.grid_columnconfigure(0, weight=1)
        self.tree_productos.bind('<Double-1>', lambda e: self.editar_producto())
        self.sistema._configurar_sorting_treeview(self.tree_productos,
            columnas_numericas=['Precio Base', 'P.Venta', 'Stock', 'Mín'])
        self._status_prod = tk.Label(tab_prod, text='',
            font=('Arial', 8), bg='#dde3ec', fg='#6b7280', anchor='w', padx=8, pady=3)
        self._status_prod.pack(fill='x', side='bottom')
        self.cargar_productos()

        # ── Tab Proveedores ───────────────────────────────────────────────
        tab_prov = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_prov, text='🏭  Proveedores')

        tb_prov = tk.Frame(tab_prov, bg=self.C['toolbar_bg'])
        tb_prov.pack(fill='x')
        tk.Frame(tab_prov, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self.sistema._toolbar_btn(tb_prov, '➕ Nuevo',    self.nuevo_proveedor,   color=self.C['accent'])
        self.sistema._toolbar_btn(tb_prov, '✏️ Editar',   self.editar_proveedor)
        self.sistema._toolbar_btn(tb_prov, '🗑️ Eliminar', self.eliminar_proveedor, peligro=True)
        self.sistema._toolbar_sep(tb_prov)
        self.sistema._toolbar_btn(tb_prov, '🛒 Presupuesto Compra', self.generar_presupuesto_compra, tip='Generar presupuesto de compra basado en stock mínimo y órdenes pendientes')

        ff_prov = tk.Frame(tab_prov, bg=self.C['toolbar_bg'], pady=4)
        ff_prov.pack(fill='x')
        tk.Label(ff_prov, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_proveedor = tk.Entry(ff_prov, font=('Arial', 9), width=30)
        self.entry_buscar_proveedor.pack(side='left', padx=4)
        self.entry_buscar_proveedor.bind('<KeyRelease>', lambda e: self.cargar_proveedores())
        self.sistema._toolbar_btn(ff_prov, '🔍', self.cargar_proveedores)
        self.sistema._toolbar_sep(ff_prov)
        self.sistema._toolbar_btn(ff_prov, '📊 CSV', self.exportar_csv_proveedores, color='#065f46')

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
        self.sistema._configurar_sorting_treeview(self.tree_proveedores)
        self.cargar_proveedores()

        # ── Tab Compras ───────────────────────────────────────────────────
        tab_comp = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_comp, text='🛒  Compras')

        tb_comp = tk.Frame(tab_comp, bg=self.C['toolbar_bg'])
        tb_comp.pack(fill='x')
        tk.Frame(tab_comp, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self.sistema._toolbar_btn(tb_comp, '➕ Nueva',       self.sistema.nueva_compra, color=self.C['accent'])
        self.sistema._toolbar_btn(tb_comp, '🔍 Ver Detalle',  self.sistema.ver_compra)
        self.sistema._toolbar_btn(tb_comp, '✏️ Editar',       self.sistema.editar_compra)

        ff_comp = tk.Frame(tab_comp, bg=self.C['toolbar_bg'], pady=4)
        ff_comp.pack(fill='x')
        tk.Label(ff_comp, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_compra = tk.Entry(ff_comp, font=('Arial', 9), width=30)
        self.entry_buscar_compra.pack(side='left', padx=4)
        self.entry_buscar_compra.bind('<KeyRelease>', lambda e: self.sistema.cargar_compras())
        self.sistema._toolbar_btn(ff_comp, '🔍', self.sistema.cargar_compras)
        self.sistema._toolbar_sep(ff_comp)
        self.sistema._toolbar_btn(ff_comp, '📊 CSV', self.exportar_csv_compras, color='#065f46')

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
        self.tree_compras.bind('<Double-1>', lambda e: self.sistema.ver_compra())
        self.sistema._configurar_sorting_treeview(self.tree_compras,
            columnas_numericas=['Total'])
        self.sistema.cargar_compras()

