#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/catalogos.py
Componente Catálogos — Clientes, Productos, Proveedores, Categorías.

Uso:
    from ui.catalogos import Catalogos
    self.catalogos = Catalogos(self)     # self = SistemaGestion
    self.catalogos.crear_seccion()       # construye el frame
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import os
from datetime import datetime
from modules.compras import VentanaCompra
from ui.generador_pdf_cly import GeneradorPDFCLY



def _campo_error(entry, msg_label, mensaje):
    """Marca un Entry con borde rojo y muestra mensaje de error en msg_label.
    Devuelve False para usar en: if not _campo_error(...): return
    """
    entry.configure(highlightbackground='#dc2626', highlightcolor='#dc2626',
                    highlightthickness=2)
    if msg_label:
        msg_label.configure(text=mensaje, fg='#dc2626')
    entry.focus()
    return False


def _campo_ok(entry, msg_label=None):
    """Limpia el estado de error de un Entry."""
    entry.configure(highlightthickness=0)
    if msg_label:
        msg_label.configure(text='')


def _centrar(win, padre=None, ancho=None, alto=None):
    """Centra una ventana respecto a su padre o pantalla."""
    if ancho and alto:
        win.geometry(f"{ancho}x{alto}")
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    if padre:
        x = padre.winfo_rootx() + (padre.winfo_width()  - w) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - h) // 2
    else:
        x = (win.winfo_screenwidth()  - w) // 2
        y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"+{max(0,x)}+{max(0,y)}")


class Catalogos:
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
        self.entry_buscar_cliente.bind('<Return>', lambda e: self.cargar_clientes())
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
        self.entry_buscar_producto.bind('<Return>', lambda e: self.cargar_productos())
        self.sistema._toolbar_btn(ff_prod, '🔍', self.cargar_productos)
        self.sistema._toolbar_sep(ff_prod)
        self.sistema._toolbar_btn(ff_prod, '📊 CSV', self.exportar_csv_productos, color='#065f46')
        self.sistema._toolbar_sep(ff_prod)
        self.sistema._toolbar_btn(ff_prod, '⚠ Precios por revisar', self.filtrar_precios_desactualizados,
            color='#d97706', tip='Filtra productos cuyo precio base lleva más tiempo sin actualizarse que su umbral individual.')

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
        self.entry_buscar_proveedor.bind('<Return>', lambda e: self.cargar_proveedores())
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
        self.entry_buscar_compra.bind('<Return>', lambda e: self.sistema.cargar_compras())
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

        n = len(self.tree_clientes.get_children())
        if hasattr(self, '_status_cli'):
            self._status_cli.config(
                text=f'{n} cliente{"s" if n!=1 else ""}  ·  doble clic para editar')
        if hasattr(self, '_actualizar_tabs_catalogos'):
            self._actualizar_tabs_catalogos()

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
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

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
        lbl_err_nombre_cli = tk.Label(sec1, text='', font=('Arial', 8),
                                      fg='#dc2626', bg='white')
        lbl_err_nombre_cli.grid(row=1, column=1, sticky='w', pady=(0,2))

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
            _campo_ok(e_nombre, lbl_err_nombre_cli)
            nombre = e_nombre.get().strip()
            tipo   = c_tipo.get()
            ok = True
            if not nombre:
                _campo_error(e_nombre, lbl_err_nombre_cli, "El nombre comercial es obligatorio")
                ok = False
            if not tipo:
                messagebox.showwarning('Advertencia', 'Selecciona un tipo de cliente',
                                       parent=ventana)
                if ok: return
                return
            if not ok:
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
        
        # Insertar datos — columnas: ID, Código, Nombre, Categoría,
        # Unidad, Precio Base, IVA, P.Venta, Stock, Mín, Proveedor ⭐, Precio actualizado
        from datetime import date as _d
        hoy = _d.today()
        n_total = 0

        for row in self.cursor.fetchall():
            pid, codigo, nombre, cat, sub, unidad, precio_base, aplica_iva,             precio_venta, stock, stock_min, clave_sat = row

            # Proveedor principal
            self.cursor.execute("""
                SELECT prov.nombre, pp.es_principal
                FROM producto_proveedor pp
                JOIN proveedores prov ON pp.proveedor_id = prov.id
                WHERE pp.producto_id = ?
                ORDER BY pp.es_principal DESC, prov.nombre
            """, (pid,))
            provs = self.cursor.fetchall()
            if provs:
                ppal = next((p[0] for p in provs if p[1]), provs[0][0])
                info_prov = f"⭐ {ppal[:18]}" + (f" (+{len(provs)-1})" if len(provs) > 1 else '')
            else:
                info_prov = '—'

            # Indicador de precio actualizado
            precio_tag = ''
            try:
                self.cursor.execute("""
                    SELECT fecha FROM producto_precio_historial
                    WHERE producto_id = ? AND fuente != 'backfill'
                    ORDER BY fecha DESC LIMIT 1
                """, (pid,))
                ph = self.cursor.fetchone()
                if ph:
                    dias = (hoy - _d.fromisoformat(str(ph[0])[:10])).days
                else:
                    self.cursor.execute(
                        "SELECT precio_base_fecha FROM productos WHERE id=?", (pid,))
                    pbf = self.cursor.fetchone()
                    dias = (hoy - _d.fromisoformat(str(pbf[0])[:10])).days                            if pbf and pbf[0] else 9999

                if dias == 9999:   precio_ind, precio_tag = '❓ Sin registro', 'precio_old'
                elif dias <= 30:   precio_ind, precio_tag = f'🟢 Hace {dias}d', 'precio_ok'
                elif dias <= 60:   precio_ind, precio_tag = f'🟡 Hace {dias}d', 'precio_warn'
                else:              precio_ind, precio_tag = f'🔴 Hace {dias}d', 'precio_old'
            except Exception:
                precio_ind = '—'

            # Tag de stock bajo (tiene prioridad visual sobre precio)
            stock_bajo = stock_min and stock_min > 0 and stock <= stock_min
            if stock_bajo:
                tag_final = ('stock_bajo',)
            elif precio_tag:
                tag_final = (precio_tag,)
            else:
                tag_final = ()

            values = (
                pid,
                codigo or '',
                nombre or '',
                cat or '',
                unidad or '',
                f'${precio_base:,.2f}' if precio_base else '$0.00',
                'Sí' if aplica_iva else 'No',
                f'${precio_venta:,.2f}' if precio_venta else '—',
                f'{stock:g}' if stock is not None else '0',
                f'{stock_min:g}' if stock_min else '—',
                info_prov,
                precio_ind,
            )
            self.tree_productos.insert('', 'end', values=values, tags=tag_final)
            n_total += 1

        # Actualizar barra de estado y tabs
        if hasattr(self, '_status_prod'):
            self._status_prod.config(
                text=f'{n_total} producto{"s" if n_total!=1 else ""}  ·  doble clic para editar')
        if hasattr(self, '_actualizar_tabs_catalogos'):
            self._actualizar_tabs_catalogos()
    
    def filtrar_precios_desactualizados(self):
        """Filtra la tabla de productos mostrando solo los con precio desactualizado."""
        from datetime import date as _d
        hoy = _d.today()

        self.tree_productos.delete(*self.tree_productos.get_children())

        self.cursor.execute("""
            SELECT p.id, p.codigo, p.nombre, c.nombre, s.nombre, p.unidad_medida,
                   p.precio_base, p.aplica_iva, p.precio_venta, p.stock_actual,
                   p.stock_minimo, p.clave_sat, p.precio_base_fecha
            FROM productos p
            LEFT JOIN categorias c   ON p.categoria_id    = c.id
            LEFT JOIN subcategorias s ON p.subcategoria_id = s.id
            ORDER BY p.nombre
        """)
        rows = self.cursor.fetchall()

        n_filtrados = 0
        for row in rows:
            pid = row[0]

            # Calcular umbral igual que la alerta
            self.cursor.execute("""
                SELECT fecha FROM producto_precio_historial
                WHERE producto_id = ? AND fuente != 'backfill'
                ORDER BY fecha ASC
            """, (pid,))
            fechas = [r[0] for r in self.cursor.fetchall()]
            n = len(fechas)
            if n >= 3:
                deltas = []
                for i in range(1, n):
                    try:
                        d1 = _d.fromisoformat(fechas[i-1])
                        d2 = _d.fromisoformat(fechas[i])
                        deltas.append((d2 - d1).days)
                    except Exception:
                        pass
                umbral = max(7, int(sum(deltas)/len(deltas)*0.8)) if deltas else 30
            else:
                umbral = 30

            # Fecha último cambio real
            self.cursor.execute("""
                SELECT fecha FROM producto_precio_historial
                WHERE producto_id = ? AND fuente != 'backfill'
                ORDER BY fecha DESC LIMIT 1
            """, (pid,))
            ph = self.cursor.fetchone()
            if ph:
                try:
                    dias = (hoy - _d.fromisoformat(str(ph[0])[:10])).days
                except Exception:
                    dias = 9999
            else:
                pbf = row[12]
                if pbf:
                    try:
                        dias = (hoy - _d.fromisoformat(str(pbf)[:10])).days
                    except Exception:
                        dias = 9999
                else:
                    dias = 9999

            if dias <= umbral:
                continue  # precio fresco, no mostrar

            # Construir row para mostrar
            pid2, codigo, nombre, cat, sub, unidad, precio_base, aplica_iva,             precio_venta, stock, stock_min, clave_sat, precio_base_fecha = row

            self.cursor.execute("""
                SELECT prov.nombre, pp.es_principal FROM producto_proveedor pp
                JOIN proveedores prov ON pp.proveedor_id = prov.id
                WHERE pp.producto_id = ? ORDER BY pp.es_principal DESC
            """, (pid,))
            provs = self.cursor.fetchall()
            ppal = next((p[0] for p in provs if p[1]), provs[0][0]) if provs else None
            info_prov = f"⭐ {ppal[:18]}" if ppal else '—'

            if dias == 9999:   precio_ind = '❓ Sin registro'
            elif dias <= 60:   precio_ind = f'🟡 Hace {dias}d'
            else:              precio_ind = f'🔴 Hace {dias}d'

            tag = 'precio_warn' if dias <= 60 else 'precio_old'
            values = (
                pid, codigo or '', nombre or '', cat or '', unidad or '',
                f'${precio_base:,.2f}' if precio_base else '$0.00',
                'Sí' if aplica_iva else 'No',
                f'${precio_venta:,.2f}' if precio_venta else '—',
                f'{stock:g}' if stock is not None else '0',
                f'{stock_min:g}' if stock_min else '—',
                info_prov, precio_ind,
            )
            self.tree_productos.insert('', 'end', values=values, tags=(tag,))
            n_filtrados += 1

        # Si hay productos desactualizados, abrir ventana de revisión masiva
        if n_filtrados == 0:
            messagebox.showinfo('✅ Precios al día',
                'Todos los productos tienen precios actualizados.',
                parent=self.sistema.root)
            self.cargar_productos()
        else:
            self._ventana_revision_masiva_precios()

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
        """Ventana para crear o editar producto — layout sectioned."""
        BG  = '#f8fafc'
        BDR = '#e2e8f0'
        HDR = '#1e3a5f'

        ventana = tk.Toplevel(self.root)
        ventana.title("Nuevo Producto" if modo == 'nuevo' else "Editar Producto")
        ventana.geometry("680x600")
        ventana.minsize(600, 520)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.configure(bg=BG)

        # ── Cargar datos ───────────────────────────────────────────────────
        self.cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        categorias = self.cursor.fetchall()

        datos = {}
        if modo == 'editar' and producto_id:
            self.cursor.execute("""
                SELECT codigo, nombre, descripcion, categoria_id, subcategoria_id,
                       unidad_medida, precio_base, aplica_iva, precio_venta,
                       stock_actual, stock_minimo, clave_sat, clave_unidad_sat
                FROM productos WHERE id = ?
            """, (producto_id,))
            row = self.cursor.fetchone()
            if row:
                keys = ['codigo','nombre','descripcion','categoria_id','subcategoria_id',
                        'unidad_medida','precio_base','aplica_iva','precio_venta',
                        'stock_actual','stock_minimo','clave_sat','clave_unidad_sat']
                datos = {k: (v if v is not None else '') for k, v in zip(keys, row)}

        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(ventana, bg=HDR, pady=10)
        hdr.pack(fill='x')
        titulo = "📦  Nuevo Producto" if modo == 'nuevo' else "📦  Editar Producto"
        tk.Label(hdr, text=titulo,
                 font=('Arial', 11, 'bold'), bg=HDR, fg='white').pack(side='left', padx=14)
        if modo == 'editar' and datos.get('codigo') and datos.get('nombre'):
            tk.Label(hdr, text=f"{datos['codigo']}  ·  {str(datos['nombre'])[:38]}",
                     font=('Arial', 9), bg=HDR, fg='#93c5fd').pack(side='left')

        # ── Scrollable body ───────────────────────────────────────────────
        body_outer = tk.Frame(ventana, bg=BG)
        body_outer.pack(fill='both', expand=True)
        canvas_b = tk.Canvas(body_outer, bg=BG, highlightthickness=0)
        sc_b = ttk.Scrollbar(body_outer, orient='vertical', command=canvas_b.yview)
        canvas_b.configure(yscrollcommand=sc_b.set)
        canvas_b.pack(side='left', fill='both', expand=True)
        sc_b.pack(side='right', fill='y')
        body = tk.Frame(canvas_b, bg=BG)
        wid_b = canvas_b.create_window((0,0), window=body, anchor='nw')
        body.bind('<Configure>', lambda e: canvas_b.configure(scrollregion=canvas_b.bbox('all')))
        canvas_b.bind('<Configure>', lambda e: canvas_b.itemconfig(wid_b, width=e.width))

        def section(parent, titulo_sec, color=HDR):
            tk.Frame(parent, bg=BDR, height=1).pack(fill='x')
            hf = tk.Frame(parent, bg=color, pady=5)
            hf.pack(fill='x')
            tk.Label(hf, text=titulo_sec, font=('Arial', 9, 'bold'),
                     bg=color, fg='white').pack(side='left', padx=12)
            f = tk.Frame(parent, bg=BG, padx=14, pady=8)
            f.pack(fill='x')
            f.grid_columnconfigure(1, weight=1)
            return f

        # ── SEC 1: Datos generales ─────────────────────────────────────────
        sec1 = section(body, '📋  Datos generales')

        def _lbl(parent, text, row_n, bold=False):
            tk.Label(parent, text=text, font=('Arial', 9, 'bold' if bold else 'normal'),
                     bg=BG, fg='#374151', anchor='e', width=14
                     ).grid(row=row_n, column=0, sticky='e', padx=(0,10), pady=4)

        def _entry(parent, row_n, val='', width=38):
            e = tk.Entry(parent, font=('Arial', 9), width=width,
                         relief='solid', bd=1, bg='white')
            e.insert(0, str(val))
            e.grid(row=row_n, column=1, sticky='ew', pady=4)
            return e

        _lbl(sec1, 'Código / SKU*', 0, bold=True)
        entry_codigo = _entry(sec1, 0, datos.get('codigo',''))
        lbl_err_codigo = tk.Label(sec1, text='', font=('Arial', 8), fg='#dc2626', bg=BG)
        lbl_err_codigo.grid(row=1, column=1, sticky='w')

        _lbl(sec1, 'Nombre*', 2, bold=True)
        entry_nombre = _entry(sec1, 2, datos.get('nombre',''))
        lbl_err_nombre = tk.Label(sec1, text='', font=('Arial', 8), fg='#dc2626', bg=BG)
        lbl_err_nombre.grid(row=3, column=1, sticky='w')

        _lbl(sec1, 'Descripción', 4)
        text_desc = tk.Text(sec1, font=('Arial', 9), width=38, height=2,
                            relief='solid', bd=1, bg='white')
        text_desc.insert('1.0', datos.get('descripcion',''))
        text_desc.grid(row=4, column=1, sticky='ew', pady=4)

        try:
            self.cursor.execute("SELECT nombre FROM unidades_medida ORDER BY nombre")
            unidades = [r[0] for r in self.cursor.fetchall()]
        except Exception:
            unidades = []
        if not unidades:
            unidades = ['Caja','Kilogramo','Litro','Pieza','Servicio']
        _lbl(sec1, 'Unidad', 5)
        combo_unidad = ttk.Combobox(sec1, values=unidades, state='readonly',
                                    font=('Arial', 9), width=20)
        ud = datos.get('unidad_medida', 'Pieza')
        if ud in unidades: combo_unidad.set(ud)
        combo_unidad.grid(row=5, column=1, sticky='w', pady=4)

        # ── SEC 2: Categoría ───────────────────────────────────────────────
        sec2 = section(body, '🗂  Categoría', '#374151')

        nombres_cat = [c[1] for c in categorias]
        cat_actual = ''
        if datos.get('categoria_id'):
            for cid, cnom in categorias:
                if cid == datos['categoria_id']:
                    cat_actual = cnom
                    break

        _lbl(sec2, 'Categoría', 0)
        combo_categoria = ttk.Combobox(sec2, values=nombres_cat, state='readonly',
                                        font=('Arial', 9), width=36)
        if cat_actual in nombres_cat: combo_categoria.set(cat_actual)
        combo_categoria.grid(row=0, column=1, sticky='ew', pady=4)

        _lbl(sec2, 'Subcategoría', 1)
        combo_subcat = ttk.Combobox(sec2, values=[], state='readonly',
                                    font=('Arial', 9), width=36)
        combo_subcat.grid(row=1, column=1, sticky='ew', pady=4)

        def _on_cat_change(e=None):
            cat_sel = combo_categoria.get()
            cid = next((c[0] for c in categorias if c[1] == cat_sel), None)
            if cid:
                self.cursor.execute(
                    "SELECT nombre FROM subcategorias WHERE categoria_id=? ORDER BY nombre", (cid,))
                subs = [r[0] for r in self.cursor.fetchall()]
                combo_subcat['values'] = subs
                if datos.get('subcategoria_id'):
                    self.cursor.execute(
                        "SELECT nombre FROM subcategorias WHERE id=?", (datos['subcategoria_id'],))
                    rs = self.cursor.fetchone()
                    if rs and rs[0] in subs: combo_subcat.set(rs[0])
            else:
                combo_subcat['values'] = []
                combo_subcat.set('')

        combo_categoria.bind('<<ComboboxSelected>>', _on_cat_change)
        _on_cat_change()

        # ── SEC 3: Precios ─────────────────────────────────────────────────
        sec3 = section(body, '💲  Precios', '#065f46')
        sec3.grid_columnconfigure(3, weight=1)

        tk.Label(sec3, text='Precio base*', font=('Arial', 9, 'bold'),
                 bg=BG, fg='#374151', anchor='e', width=14
                 ).grid(row=0, column=0, sticky='e', padx=(0,10), pady=4)
        entry_precio_base = tk.Entry(sec3, font=('Arial', 9), width=14,
                                     relief='solid', bd=1, bg='white')
        entry_precio_base.insert(0, str(datos.get('precio_base','0.00')))
        entry_precio_base.grid(row=0, column=1, sticky='w', pady=4, padx=(0,20))
        lbl_err_precio = tk.Label(sec3, text='', font=('Arial', 8), fg='#dc2626', bg=BG)
        lbl_err_precio.grid(row=1, column=1, sticky='w')

        var_iva = tk.BooleanVar(value=bool(datos.get('aplica_iva', 1)))
        tk.Label(sec3, text='Aplica IVA', font=('Arial', 9),
                 bg=BG, fg='#374151', anchor='e', width=10
                 ).grid(row=0, column=2, sticky='e', padx=(0,6), pady=4)
        tk.Checkbutton(sec3, variable=var_iva, bg=BG, text='(16%)',
                       font=('Arial', 9)).grid(row=0, column=3, sticky='w', pady=4)

        tk.Label(sec3, text='Precio venta', font=('Arial', 9),
                 bg=BG, fg='#374151', anchor='e', width=14
                 ).grid(row=2, column=0, sticky='e', padx=(0,10), pady=4)
        entry_precio_venta = tk.Entry(sec3, font=('Arial', 9), width=14,
                                      relief='solid', bd=1, bg='white')
        entry_precio_venta.insert(0, str(datos.get('precio_venta','0')))
        entry_precio_venta.grid(row=2, column=1, sticky='w', pady=4)
        tk.Label(sec3, text='Opcional — se calcula automáticamente',
                 font=('Arial', 8), bg=BG, fg='#9ca3af'
                 ).grid(row=2, column=2, columnspan=2, sticky='w')

        # ── SEC 4: Stock ───────────────────────────────────────────────────
        sec4 = section(body, '📦  Stock', '#1a4b8c')
        sec4.grid_columnconfigure(3, weight=1)

        tk.Label(sec4, text='Stock actual', font=('Arial', 9),
                 bg=BG, fg='#374151', anchor='e', width=14
                 ).grid(row=0, column=0, sticky='e', padx=(0,10), pady=4)
        entry_stock = tk.Entry(sec4, font=('Arial', 9), width=10,
                               relief='solid', bd=1, bg='white')
        entry_stock.insert(0, str(datos.get('stock_actual','0')))
        entry_stock.grid(row=0, column=1, sticky='w', pady=4, padx=(0,20))

        tk.Label(sec4, text='Stock mínimo', font=('Arial', 9),
                 bg=BG, fg='#374151', anchor='e', width=12
                 ).grid(row=0, column=2, sticky='e', padx=(0,6), pady=4)
        entry_stock_min = tk.Entry(sec4, font=('Arial', 9), width=10,
                                   relief='solid', bd=1, bg='white')
        entry_stock_min.insert(0, str(datos.get('stock_minimo','0')))
        entry_stock_min.grid(row=0, column=3, sticky='w', pady=4)

        # ── SEC 5: SAT ─────────────────────────────────────────────────────
        sec5 = section(body, '🏛  Datos SAT / Facturación', '#7c3aed')
        sec5.grid_columnconfigure(3, weight=1)

        tk.Label(sec5, text='Clave SAT', font=('Arial', 9),
                 bg=BG, fg='#374151', anchor='e', width=14
                 ).grid(row=0, column=0, sticky='e', padx=(0,10), pady=4)
        entry_clave_sat = tk.Entry(sec5, font=('Arial', 9), width=14,
                                   relief='solid', bd=1, bg='white')
        entry_clave_sat.insert(0, datos.get('clave_sat',''))
        entry_clave_sat.grid(row=0, column=1, sticky='w', pady=4, padx=(0,12))
        tk.Label(sec5, text='ej: 43211500',
                 font=('Arial', 8), bg=BG, fg='#9ca3af').grid(row=0, column=2, sticky='w')

        tk.Label(sec5, text='Clave Unidad', font=('Arial', 9),
                 bg=BG, fg='#374151', anchor='e', width=14
                 ).grid(row=1, column=0, sticky='e', padx=(0,10), pady=4)
        entry_clave_unidad = tk.Entry(sec5, font=('Arial', 9), width=14,
                                      relief='solid', bd=1, bg='white')
        entry_clave_unidad.insert(0, datos.get('clave_unidad_sat',''))
        entry_clave_unidad.grid(row=1, column=1, sticky='w', pady=4, padx=(0,12))
        tk.Label(sec5, text='ej: H87 (Pieza), KGM (Kilo)',
                 font=('Arial', 8), bg=BG, fg='#9ca3af').grid(row=1, column=2, sticky='w')

        # ── Guardar ────────────────────────────────────────────────────────
        def guardar():
            _campo_ok(entry_codigo, lbl_err_codigo)
            _campo_ok(entry_nombre, lbl_err_nombre)
            _campo_ok(entry_precio_base, lbl_err_precio)

            codigo_val = entry_codigo.get().strip()
            nombre_val = entry_nombre.get().strip()
            precio_txt = entry_precio_base.get().strip()

            ok = True
            if not codigo_val:
                _campo_error(entry_codigo, lbl_err_codigo, "El código es obligatorio")
                ok = False
            if not nombre_val:
                _campo_error(entry_nombre, lbl_err_nombre, "El nombre es obligatorio")
                if ok: entry_nombre.focus()
                ok = False
            precio_val = None
            try:
                precio_val = float(precio_txt)
                if precio_val < 0: raise ValueError()
            except ValueError:
                _campo_error(entry_precio_base, lbl_err_precio, "Número mayor o igual a 0")
                if ok: entry_precio_base.focus()
                ok = False
            if not ok: return

            cat_id = next((c[0] for c in categorias if c[1] == combo_categoria.get()), None)
            sub_id = None
            if combo_subcat.get() and cat_id:
                self.cursor.execute(
                    "SELECT id FROM subcategorias WHERE nombre=? AND categoria_id=?",
                    (combo_subcat.get(), cat_id))
                rs = self.cursor.fetchone()
                if rs: sub_id = rs[0]

            d = (codigo_val.upper(), nombre_val,
                 text_desc.get('1.0','end-1c').strip(),
                 cat_id, sub_id, combo_unidad.get(),
                 precio_val, 1 if var_iva.get() else 0,
                 float(entry_precio_venta.get() or 0),
                 float(entry_stock.get() or 0),
                 float(entry_stock_min.get() or 0),
                 entry_clave_sat.get().strip() or None,
                 entry_clave_unidad.get().strip() or None)

            try:
                if modo == 'nuevo':
                    self.cursor.execute("""
                        INSERT INTO productos
                        (codigo, nombre, descripcion, categoria_id, subcategoria_id,
                         unidad_medida, precio_base, aplica_iva, precio_venta,
                         stock_actual, stock_minimo, clave_sat, clave_unidad_sat)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, d)
                    self._registrar_precio_historial(
                        self.cursor.lastrowid, precio_val,
                        motivo='Precio inicial', fuente='manual')
                    msg = "Producto registrado correctamente"
                else:
                    self.cursor.execute(
                        "SELECT precio_base FROM productos WHERE id=?", (producto_id,))
                    prev = self.cursor.fetchone()
                    if prev:
                        self._registrar_precio_historial(
                            producto_id, precio_val, precio_anterior=prev[0], fuente='manual')
                    self.cursor.execute("""
                        UPDATE productos SET
                        codigo=?, nombre=?, descripcion=?, categoria_id=?,
                        subcategoria_id=?, unidad_medida=?, precio_base=?,
                        aplica_iva=?, precio_venta=?, stock_actual=?,
                        stock_minimo=?, clave_sat=?, clave_unidad_sat=?
                        WHERE id=?
                    """, (*d, producto_id))
                    msg = "Producto actualizado correctamente"

                self.conn.commit()
                messagebox.showinfo("Éxito", msg, parent=ventana)
                self.cargar_productos()
                ventana.destroy()
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e), parent=ventana)

        # ── Footer ─────────────────────────────────────────────────────────
        tk.Frame(ventana, bg=BDR, height=1).pack(fill='x')
        foot = tk.Frame(ventana, bg='#e8edf5', pady=8, padx=12)
        foot.pack(fill='x', side='bottom')

        tk.Button(foot, text='💾 Guardar', command=guardar,
                  bg='#065f46', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=14, pady=6, relief='flat').pack(side='left', padx=(0,6))
        tk.Button(foot, text='Cancelar', command=ventana.destroy,
                  bg='#e8edf5', fg='#6b7280', font=('Arial', 9),
                  cursor='hand2', padx=10, pady=6, relief='flat', bd=1).pack(side='left')

        if modo == 'editar' and producto_id:
            tk.Button(foot, text='📈 Historial precios',
                      command=lambda: self._ver_historial_precios(producto_id, ventana),
                      bg='#1e3a5f', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=6, relief='flat').pack(side='right', padx=(6,0))
            tk.Button(foot, text='🏭 Proveedores',
                      command=lambda: self.gestionar_proveedores_producto(producto_id, ventana),
                      bg='#16a085', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=6, relief='flat').pack(side='right', padx=(6,0))
            tk.Button(foot, text='✅ Precio vigente',
                      command=lambda: self._confirmar_precio_vigente(
                          producto_id,
                          float(entry_precio_base.get() or 0),
                          parent=ventana,
                          callback=lambda: [self.cargar_productos()]),
                      bg='#0f7b5e', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=6, relief='flat').pack(side='right', padx=(6,0))

        ventana.bind('<Return>', lambda e: guardar())
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
        entry_codigo.focus()

    def _ventana_revision_masiva_precios(self):
        """Ventana de revisión masiva de precios desactualizados con edición inline."""
        from datetime import date as _d
        hoy = _d.today()

        # Recopilar productos desactualizados con sus datos
        self.cursor.execute("""
            SELECT p.id, p.codigo, p.nombre, p.precio_base, c.nombre AS cat
            FROM productos p
            LEFT JOIN categorias c ON c.id = p.categoria_id
            ORDER BY p.nombre
        """)
        todos = self.cursor.fetchall()

        pendientes = []  # (pid, codigo, nombre, precio_actual, cat, dias)
        for pid, codigo, nombre, precio_base, cat in todos:
            # Calcular días desde último registro real
            self.cursor.execute("""
                SELECT fecha FROM producto_precio_historial
                WHERE producto_id = ? AND fuente != 'backfill'
                ORDER BY fecha DESC LIMIT 1
            """, (pid,))
            ph = self.cursor.fetchone()
            if ph:
                try:   dias = (hoy - _d.fromisoformat(str(ph[0])[:10])).days
                except: dias = 9999
            else:
                self.cursor.execute(
                    "SELECT precio_base_fecha FROM productos WHERE id=?", (pid,))
                pbf = self.cursor.fetchone()
                try:   dias = (hoy - _d.fromisoformat(str(pbf[0])[:10])).days if pbf and pbf[0] else 9999
                except: dias = 9999

            # Calcular umbral dinámico
            self.cursor.execute("""
                SELECT fecha FROM producto_precio_historial
                WHERE producto_id = ? AND fuente != 'backfill'
                ORDER BY fecha ASC
            """, (pid,))
            fechas = [r[0] for r in self.cursor.fetchall()]
            n = len(fechas)
            if n >= 3:
                deltas = []
                for i in range(1, n):
                    try:
                        deltas.append((_d.fromisoformat(fechas[i]) -
                                       _d.fromisoformat(fechas[i-1])).days)
                    except: pass
                umbral = max(7, int(sum(deltas)/len(deltas)*0.8)) if deltas else 30
            else:
                umbral = 30

            if dias > umbral:
                pendientes.append((pid, codigo or '', nombre or '',
                                   precio_base or 0, cat or '', dias))

        if not pendientes:
            messagebox.showinfo('✅ Precios al día',
                'Todos los productos tienen precios actualizados.',
                parent=self.sistema.root)
            self.cargar_productos()
            return

        # ── Ventana ───────────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f'Revisión de precios — {len(pendientes)} producto(s)')
        win.geometry('820x540')
        win.minsize(700, 400)
        _centrar(win, self.root)
        win.configure(bg='#f8fafc')
        win.transient(self.root)
        win.grab_set()
        win.bind('<Escape>', lambda e: win.destroy())

        # Header
        hdr = tk.Frame(win, bg='#d97706', pady=9)
        hdr.pack(fill='x')
        tk.Label(hdr, text='⚠  Revisión masiva de precios',
                 font=('Arial', 11, 'bold'), bg='#d97706', fg='white').pack(side='left', padx=14)
        tk.Label(hdr, text=f'{len(pendientes)} productos requieren revisión',
                 font=('Arial', 9), bg='#d97706', fg='#fef3c7').pack(side='left')

        # Instrucción
        tk.Label(win,
                 text='Edita el precio si cambió, o deja el valor para confirmar que sigue vigente. '
                      'Al confirmar se registra la revisión de hoy.',
                 font=('Arial', 8), bg='#f8fafc', fg='#6b7280', padx=14, pady=6).pack(fill='x')
        tk.Frame(win, bg='#e2e8f0', height=1).pack(fill='x')

        # Tabla con entries inline
        outer = tk.Frame(win, bg='#f8fafc')
        outer.pack(fill='both', expand=True, padx=10, pady=8)

        # Cabecera
        hdr_row = tk.Frame(outer, bg='#e8edf5')
        hdr_row.pack(fill='x')
        for txt, w in [('Producto', 280), ('Cat.', 90), ('Precio actual', 110),
                        ('Nuevo precio', 110), ('Días', 55), ('', 90)]:
            tk.Label(hdr_row, text=txt, font=('Arial', 8, 'bold'),
                     bg='#e8edf5', fg='#374151', width=0, anchor='w',
                     padx=6, pady=5).pack(side='left')

        # Canvas scroll
        canvas = tk.Canvas(outer, bg='#f8fafc', highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        inner = tk.Frame(canvas, bg='#f8fafc')
        wid = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))

        entries = {}  # pid → Entry widget
        confirmados = set()
        estado_labels = {}  # pid → Label

        def _confirmar_uno(pid, precio_actual, entry_w, lbl_estado):
            from datetime import date as _d2
            nuevo_txt = entry_w.get().strip()
            try:
                nuevo = float(nuevo_txt)
                if nuevo <= 0: raise ValueError()
            except ValueError:
                entry_w.config(bg='#fee2e2')
                return
            entry_w.config(bg='#f0fdf4')
            motivo = ('Precio actualizado' if abs(nuevo - precio_actual) > 0.001
                      else 'Sin cambios — confirmado')
            fuente = 'manual' if abs(nuevo - precio_actual) > 0.001 else 'confirmacion'
            if abs(nuevo - precio_actual) > 0.001:
                self.cursor.execute(
                    "UPDATE productos SET precio_base=? WHERE id=?", (nuevo, pid))
            self.cursor.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente)
                VALUES (?, ?, ?, ?, ?)
            """, (pid, nuevo, _d2.today().isoformat(), motivo, fuente))
            self.conn.commit()
            confirmados.add(pid)
            lbl_estado.config(text='✅', fg='#16a34a')
            _actualizar_contador()

        def _confirmar_todo():
            for pid, precio_actual, entry_w, lbl_e in entry_data:
                if pid not in confirmados:
                    _confirmar_uno(pid, precio_actual, entry_w, lbl_e)

        entry_data = []
        for i, (pid, codigo, nombre, precio_actual, cat, dias) in enumerate(pendientes):
            bg = '#ffffff' if i % 2 == 0 else '#f8fafc'
            row = tk.Frame(inner, bg=bg)
            row.pack(fill='x')

            dias_color = '#dc2626' if dias > 60 else '#d97706'
            nombre_short = f'{nombre[:30]}…' if len(nombre) > 30 else nombre
            tk.Label(row, text=nombre_short, font=('Arial', 9), bg=bg,
                     fg='#374151', anchor='w', padx=6).pack(side='left', fill='x', expand=True)
            tk.Label(row, text=(cat or '')[:12], font=('Arial', 8), bg=bg,
                     fg='#6b7280', width=10, anchor='w').pack(side='left')
            tk.Label(row, text=f'${precio_actual:,.2f}', font=('Arial', 9), bg=bg,
                     fg='#374151', width=10, anchor='e').pack(side='left', padx=(0,4))
            e = tk.Entry(row, font=('Arial', 9), width=10,
                         relief='solid', bd=1, bg='white')
            e.insert(0, f'{precio_actual:.2f}')
            e.pack(side='left', padx=4)
            tk.Label(row, text=f'{dias}d', font=('Arial', 8, 'bold'), bg=bg,
                     fg=dias_color, width=5, anchor='w').pack(side='left')
            lbl_e = tk.Label(row, text='—', font=('Arial', 9), bg=bg,
                             fg='#9ca3af', width=4)
            lbl_e.pack(side='left', padx=2)
            btn = tk.Button(row, text='Confirmar',
                            font=('Arial', 8), bg='#0f7b5e', fg='white',
                            cursor='hand2', padx=6, pady=3, relief='flat',
                            command=lambda p=pid, pa=precio_actual, ew=e, le=lbl_e:
                                _confirmar_uno(p, pa, ew, le))
            btn.pack(side='left', padx=(2,6), pady=3)
            entries[pid] = e
            entry_data.append((pid, precio_actual, e, lbl_e))
            e.bind('<Return>', lambda ev, p=pid, pa=precio_actual, ew=e, le=lbl_e:
                   _confirmar_uno(p, pa, ew, le))

        # Footer
        tk.Frame(win, bg='#e2e8f0', height=1).pack(fill='x')
        foot = tk.Frame(win, bg='#eef1f8', pady=8, padx=12)
        foot.pack(fill='x')

        lbl_conteo = tk.Label(foot, text=f'0 / {len(pendientes)} confirmados',
                              font=('Arial', 9), bg='#eef1f8', fg='#6b7280')
        lbl_conteo.pack(side='left', padx=(0,12))

        def _actualizar_contador():
            n = len(confirmados)
            lbl_conteo.config(text=f'{n} / {len(pendientes)} confirmados',
                              fg='#16a34a' if n == len(pendientes) else '#6b7280')

        tk.Button(foot, text='✅ Confirmar todos sin cambios',
                  command=_confirmar_todo,
                  bg='#065f46', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5, relief='flat').pack(side='left')
        tk.Button(foot, text='Cerrar y recargar',
                  command=lambda: [win.destroy(), self.cargar_productos()],
                  bg='#1e3a5f', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=12, pady=5, relief='flat').pack(side='right')

    def _confirmar_precio_vigente(self, producto_id, precio_actual, parent=None, callback=None):
        """Registra confirmación de precio vigente sin modificarlo."""
        from datetime import date as _d
        win = tk.Toplevel(parent or self.root)
        win.title('Confirmar precio vigente')
        win.geometry('420x220')
        win.resizable(False, False)
        _centrar(win, parent or self.root)
        win.configure(bg='#f8fafc')
        win.transient(parent or self.root)
        win.grab_set()

        hdr = tk.Frame(win, bg='#065f46', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='✅  Confirmar precio vigente',
                 font=('Arial', 10, 'bold'), bg='#065f46', fg='white').pack(side='left', padx=12)

        body = tk.Frame(win, bg='#f8fafc', padx=18, pady=14)
        body.pack(fill='both', expand=True)

        tk.Label(body, text=f'Precio actual:  ${precio_actual:,.2f}',
                 font=('Arial', 10, 'bold'), bg='#f8fafc', fg='#065f46').pack(anchor='w')
        tk.Label(body, text='Este precio se marcará como revisado hoy.',
                 font=('Arial', 8), bg='#f8fafc', fg='#6b7280').pack(anchor='w', pady=(2,10))

        row_mot = tk.Frame(body, bg='#f8fafc')
        row_mot.pack(fill='x')
        tk.Label(row_mot, text='Motivo (opcional):',
                 font=('Arial', 9), bg='#f8fafc', fg='#374151').pack(side='left')
        entry_mot = tk.Entry(row_mot, font=('Arial', 9), width=28,
                             relief='solid', bd=1, bg='white')
        entry_mot.pack(side='left', padx=(8,0))

        motivos = ['Sin cambios', 'Cotización proveedor', 'Revisión mensual',
                   'Precio de mercado confirmado', 'Otro']
        combo_mot = ttk.Combobox(body, values=motivos, font=('Arial', 9), width=38)
        combo_mot.pack(fill='x', pady=(4,0))
        combo_mot.set('Sin cambios')

        tk.Frame(win, bg='#e2e8f0', height=1).pack(fill='x')
        foot = tk.Frame(win, bg='#eef1f8', pady=7, padx=12)
        foot.pack(fill='x')

        def _confirmar():
            motivo = entry_mot.get().strip() or combo_mot.get() or 'Sin cambios'
            self.cursor.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente)
                VALUES (?, ?, ?, ?, 'confirmacion')
            """, (producto_id, float(precio_actual), _d.today().isoformat(), motivo))
            self.conn.commit()
            win.destroy()
            if callback:
                callback()
            self.sistema._set_status(f'Precio confirmado — ${precio_actual:,.2f}', 'ok')

        tk.Button(foot, text='✅ Confirmar precio vigente', command=_confirmar,
                  bg='#065f46', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5, relief='flat').pack(side='left')
        tk.Button(foot, text='Cancelar', command=win.destroy,
                  bg='#eef1f8', fg='#6b7280', font=('Arial', 9),
                  cursor='hand2', padx=10, pady=5, relief='flat', bd=1).pack(side='left', padx=8)
        win.bind('<Escape>', lambda e: win.destroy())
        entry_mot.focus()

    def _ver_historial_precios(self, producto_id, parent):
        """Historial de precios mejorado: días entre movimientos, íconos fuente,
        notas editables, botón nuevo registro manual y confirmación vigente."""
        from datetime import date as _d
        self.cursor.execute(
            "SELECT nombre, precio_base FROM productos WHERE id=?", (producto_id,))
        prod = self.cursor.fetchone()
        if not prod:
            return
        nombre_prod, precio_actual = prod

        def _reload():
            self.cursor.execute("""
                SELECT id, fecha, precio, motivo, fuente, fecha_registro
                FROM producto_precio_historial
                WHERE producto_id = ?
                ORDER BY fecha DESC, fecha_registro DESC
            """, (producto_id,))
            return self.cursor.fetchall()

        BG  = "#f8fafc"
        HDR = "#1a4b8c"

        win = tk.Toplevel(parent)
        win.title(f"Historial de Precios — {nombre_prod}")
        win.geometry("780x520")
        win.minsize(660, 400)
        win.resizable(True, True)
        _centrar(win, self.root)
        win.configure(bg=BG)
        win.transient(parent)
        win.grab_set()
        win.bind("<Escape>", lambda e: win.destroy())

        # Header
        hdr = tk.Frame(win, bg=HDR, pady=9)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📈  Historial de Precios",
                 font=("Arial", 11, "bold"), bg=HDR, fg="white").pack(side="left", padx=14)
        tk.Label(hdr, text=f"{nombre_prod[:40]}   •   ${precio_actual:,.2f} actual",
                 font=("Arial", 9), bg=HDR, fg="#bfdbfe").pack(side="left")

        # Tabla
        frame_tbl = tk.Frame(win, bg=BG)
        frame_tbl.pack(fill="both", expand=True, padx=12, pady=(10,0))

        fuente_ico = {
            "manual":       "✏️",
            "compra":       "🛒",
            "confirmacion": "✅",
            "backfill":     "🔄",
        }
        cols = ("Fecha", "Precio", "Variación", "Días ant.", "Fuente", "Motivo")
        tree = ttk.Treeview(frame_tbl, columns=cols, show="headings", height=14)
        for col, w, anc in [
            ("Fecha",    88,  "w"), ("Precio",   92, "e"),
            ("Variación",88,  "e"), ("Días ant.", 70, "e"),
            ("Fuente",   90,  "w"), ("Motivo",   240,"w"),
        ]:
            tree.heading(col, text=col, anchor=anc)
            tree.column(col, width=w, minwidth=40, anchor=anc,
                        stretch=(col == "Motivo"))

        tree.tag_configure("subida",       foreground="#dc2626")
        tree.tag_configure("bajada",       foreground="#16a34a")
        tree.tag_configure("confirmacion", foreground="#0f7b5e")
        tree.tag_configure("neutro",       foreground="#374151")
        tree.tag_configure("par",          background="#f8fafc")
        tree.tag_configure("impar",        background="white")

        sc = ttk.Scrollbar(frame_tbl, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sc.set)
        tree.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        def _poblar():
            tree.delete(*tree.get_children())
            registros = _reload()
            precio_prev = None
            fecha_prev  = None
            for i, (rid, fecha, precio, motivo, fuente, _) in enumerate(registros):
                # Variación de precio
                if precio_prev is not None:
                    diff = precio - precio_prev
                    var_txt = f"{'▲' if diff > 0 else '▼'} ${abs(diff):,.2f}"
                    tag_var = "subida" if diff > 0 else ("bajada" if diff < 0 else "neutro")
                else:
                    var_txt, tag_var = "—", "neutro"

                # Días desde registro anterior
                if fecha_prev:
                    try:
                        d_ant = (_d.fromisoformat(str(fecha_prev)[:10]) -
                                 _d.fromisoformat(str(fecha)[:10])).days
                        dias_txt = f"{d_ant}d"
                    except Exception:
                        dias_txt = "—"
                else:
                    dias_txt = "—"

                fuente_txt = fuente or "manual"
                if fuente_txt == "confirmacion":
                    tag_var = "confirmacion"
                fila_tag = "par" if i % 2 == 0 else "impar"
                ico = fuente_ico.get(fuente_txt, "✏️")

                tree.insert("", "end", iid=str(rid), tags=(tag_var, fila_tag), values=(
                    (fecha or "")[:10],
                    f"${precio:,.2f}",
                    var_txt,
                    dias_txt,
                    f"{ico} {fuente_txt}",
                    motivo or "—",
                ))
                precio_prev = precio
                fecha_prev  = fecha

            if not registros:
                tree.insert("", "end", values=("—","—","—","—","—","Sin registros aún"))

        _poblar()

        # Doble clic → editar nota
        def _editar_nota(event):
            iid = tree.focus()
            if not iid:
                return
            vals = tree.item(iid)["values"]
            motivo_actual = vals[5] if vals[5] != "—" else ""
            nueva = tk.simpledialog.askstring(
                "Editar nota",
                f"Nota para registro del {vals[0]}:",
                initialvalue=motivo_actual,
                parent=win)
            if nueva is not None:
                self.cursor.execute(
                    "UPDATE producto_precio_historial SET motivo=? WHERE id=?",
                    (nueva, int(iid)))
                self.conn.commit()
                _poblar()

        tree.bind("<Double-1>", _editar_nota)

        # Footer
        tk.Frame(win, bg="#e2e8f0", height=1).pack(fill="x")
        foot = tk.Frame(win, bg="#e8edf5", pady=7, padx=12)
        foot.pack(fill="x")

        registros_n = len(_reload())
        tk.Label(foot, text=f"{registros_n} registro{'s' if registros_n!=1 else ''}  •  doble clic para editar nota",
                 font=("Arial", 8), bg="#e8edf5", fg="#6b7280").pack(side="left")

        # Nuevo registro manual con fecha pasada
        def _nuevo_manual():
            win2 = tk.Toplevel(win)
            win2.title("Nuevo registro manual")
            win2.geometry("360x210")
            win2.resizable(False, False)
            _centrar(win2, win)
            win2.configure(bg=BG)
            win2.transient(win)
            win2.grab_set()
            win2.bind("<Escape>", lambda e: win2.destroy())

            tk.Label(win2, text="Agregar precio con fecha pasada",
                     font=("Arial", 10, "bold"), bg=BG, fg="#1e3a5f"
                     ).pack(pady=(12,6))

            fr = tk.Frame(win2, bg=BG, padx=16)
            fr.pack(fill="x")
            for lbl, attr, default in [
                ("Fecha (YYYY-MM-DD)", "e_fecha", _d.today().isoformat()),
                ("Precio",             "e_precio", ""),
                ("Motivo",             "e_motivo", "Registro manual histórico"),
            ]:
                row = tk.Frame(fr, bg=BG)
                row.pack(fill="x", pady=3)
                tk.Label(row, text=lbl, font=("Arial", 9), bg=BG,
                         fg="#374151", width=18, anchor="e").pack(side="left")
                e = tk.Entry(row, font=("Arial", 9), width=20,
                             relief="solid", bd=1, bg="white")
                e.insert(0, default)
                e.pack(side="left", padx=(6,0))
                setattr(win2, attr, e)

            def _guardar_manual():
                try:
                    fecha_v = win2.e_fecha.get().strip()
                    _d.fromisoformat(fecha_v)
                    precio_v = float(win2.e_precio.get().strip())
                    if precio_v <= 0: raise ValueError()
                except ValueError:
                    messagebox.showwarning("Datos inválidos",
                        "Verifica fecha (YYYY-MM-DD) y precio.", parent=win2)
                    return
                self.cursor.execute("""
                    INSERT INTO producto_precio_historial
                        (producto_id, precio, fecha, motivo, fuente)
                    VALUES (?, ?, ?, ?, 'manual')
                """, (producto_id, precio_v, fecha_v, win2.e_motivo.get().strip()))
                self.conn.commit()
                win2.destroy()
                _poblar()

            tk.Frame(win2, bg="#e2e8f0", height=1).pack(fill="x", pady=(8,0))
            foot2 = tk.Frame(win2, bg="#eef1f8", pady=6, padx=12)
            foot2.pack(fill="x")
            tk.Button(foot2, text="💾 Guardar", command=_guardar_manual,
                      bg="#065f46", fg="white", font=("Arial", 9, "bold"),
                      cursor="hand2", padx=10, pady=4, relief="flat").pack(side="left")
            tk.Button(foot2, text="Cancelar", command=win2.destroy,
                      bg="#eef1f8", fg="#6b7280", font=("Arial", 9),
                      cursor="hand2", padx=8, pady=4, relief="flat", bd=1
                      ).pack(side="left", padx=6)

        tk.Button(foot, text="➕ Registro manual",
                  command=_nuevo_manual,
                  bg="#374151", fg="white", font=("Arial", 9),
                  cursor="hand2", padx=10, pady=4, relief="flat").pack(side="right", padx=(6,0))
        tk.Button(foot, text="✅ Confirmar precio vigente",
                  command=lambda: self._confirmar_precio_vigente(
                      producto_id, precio_actual, parent=win, callback=_poblar),
                  bg="#0f7b5e", fg="white", font=("Arial", 9),
                  cursor="hand2", padx=10, pady=4, relief="flat").pack(side="right", padx=(6,0))
        tk.Button(foot, text="Cerrar", command=win.destroy,
                  bg="#e8edf5", fg="#6b7280", font=("Arial", 9),
                  cursor="hand2", padx=10, pady=4, relief="flat", bd=1).pack(side="right", padx=(6,0))

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
        ventana.minsize(670, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        
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
            dlg.minsize(370, 340)
            dlg.resizable(True, True)
            _centrar(dlg, self.root)
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
                      bg='#6b7280', fg='white', font=('Arial', 9, 'bold'),
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
            dlg.geometry("420x200")
            dlg.minsize(340, 200)
            dlg.resizable(True, True)
            _centrar(dlg, self.root)
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
        frame_tabla = tk.Frame(ventana, bg='#f1f5f9')
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
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
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
        ventana.minsize(1020, 560)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

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
        frame_totales = tk.Frame(ventana, bg='#f1f5f9', pady=6)
        frame_totales.pack(fill='x', padx=10)

        lbl_total_est = tk.Label(
            frame_totales,
            text="Total estimado: $0.00",
            font=('Arial', 11, 'bold'), bg='#f1f5f9', fg='#16a085'
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
            bg='#6b7280', fg='white', font=('Arial', 10, 'bold'),
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
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

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
        lbl_err_prov = tk.Label(sec1, text='', font=('Arial', 8),
                                fg='#dc2626', bg='#ffffff')
        lbl_err_prov.grid(row=1, column=1, sticky='w', pady=(0,2))
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
            _campo_ok(e_nombre, lbl_err_prov)
            nombre = e_nombre.get().strip()
            if not nombre:
                _campo_error(e_nombre, lbl_err_prov, "El nombre es obligatorio")
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


    # ── Exportaciones CSV ────────────────────────────────────────────────────

    def _csv_guardar(self, nombre_base, encabezado, filas):
        """Helper compartido: pide ruta y escribe el CSV."""
        import csv as _csv
        from tkinter import filedialog as _fd
        from datetime import datetime as _dt
        if not filas:
            messagebox.showinfo('Sin datos', 'No hay registros para exportar.')
            return
        ruta = _fd.asksaveasfilename(
            title='Exportar a CSV',
            defaultextension='.csv',
            initialfile=f'{nombre_base}_{_dt.now().strftime("%Y-%m-%d")}.csv',
            filetypes=[('CSV', '*.csv')], parent=self.root)
        if not ruta:
            return
        with open(ruta, 'w', newline='', encoding='utf-8-sig') as f:
            _csv.writer(f).writerow(encabezado)
            _csv.writer(f).writerows(filas)
        n = len(filas)
        messagebox.showinfo('✅ Exportado',
            f'{n} registro{"s" if n!=1 else ""} exportado{"s" if n!=1 else ""}\n{ruta}',
            parent=self.root)

    def exportar_csv_clientes(self):
        buscar = self.entry_buscar_cliente.get().strip() if self.entry_buscar_cliente else ''
        q = """SELECT cl.nombre_comercial, cl.razon_social, cl.tipo, cl.rfc,
                      cl.direccion, cl.contacto, cl.telefono, cl.email
               FROM clientes cl WHERE 1=1"""
        params = []
        if buscar:
            q += " AND (cl.nombre_comercial LIKE ? OR cl.rfc LIKE ? OR cl.contacto LIKE ?)"
            params += [f'%{buscar}%'] * 3
        q += " ORDER BY cl.nombre_comercial"
        self.cursor.execute(q, params)
        self._csv_guardar('clientes',
            ['Nombre Comercial','Razón Social','Tipo','RFC',
             'Dirección','Contacto','Teléfono','Email'],
            self.cursor.fetchall())

    def exportar_csv_productos(self):
        buscar = self.entry_buscar_producto.get().strip() if self.entry_buscar_producto else ''
        q = """SELECT p.codigo, p.nombre, p.descripcion,
                      cat.nombre, sub.nombre, p.unidad_medida,
                      p.precio_base, p.precio_venta,
                      p.stock_actual, p.stock_minimo,
                      p.clave_sat, p.clave_unidad_sat
               FROM productos p
               LEFT JOIN categorias cat ON cat.id = p.categoria_id
               LEFT JOIN subcategorias sub ON sub.id = p.subcategoria_id
               WHERE 1=1"""
        params = []
        if buscar:
            q += " AND (p.codigo LIKE ? OR p.nombre LIKE ? OR cat.nombre LIKE ?)"
            params += [f'%{buscar}%'] * 3
        q += " ORDER BY p.nombre"
        self.cursor.execute(q, params)
        self._csv_guardar('productos',
            ['Código','Nombre','Descripción','Categoría','Subcategoría',
             'Unidad','Precio Base','Precio Venta',
             'Stock Actual','Stock Mínimo','Clave SAT','Clave Unidad SAT'],
            self.cursor.fetchall())

    def exportar_csv_proveedores(self):
        buscar = self.entry_buscar_proveedor.get().strip() if self.entry_buscar_proveedor else ''
        q = """SELECT nombre, razon_social, rfc, direccion,
                      contacto, telefono, email, notas
               FROM proveedores WHERE 1=1"""
        params = []
        if buscar:
            q += " AND (nombre LIKE ? OR rfc LIKE ? OR contacto LIKE ?)"
            params += [f'%{buscar}%'] * 3
        q += " ORDER BY nombre"
        self.cursor.execute(q, params)
        self._csv_guardar('proveedores',
            ['Nombre','Razón Social','RFC','Dirección',
             'Contacto','Teléfono','Email','Notas'],
            self.cursor.fetchall())

    def exportar_csv_compras(self):
        buscar = self.entry_buscar_compra.get().strip() if self.entry_buscar_compra else ''
        q = """SELECT c.folio, c.fecha_compra, p.nombre, c.total,
                      c.ticket_referencia, c.notas, m.nombre
               FROM compras c
               LEFT JOIN proveedores p ON c.proveedor_id = p.id
               LEFT JOIN metodos_pago m ON c.metodo_pago_id = m.id
               WHERE 1=1"""
        params = []
        if buscar:
            q += " AND (c.folio LIKE ? OR p.nombre LIKE ? OR c.ticket_referencia LIKE ?)"
            params += [f'%{buscar}%'] * 3
        q += " ORDER BY c.fecha_compra DESC"
        self.cursor.execute(q, params)
        self._csv_guardar('compras',
            ['Folio','Fecha','Proveedor','Total',
             'Referencia','Notas','Método Pago'],
            self.cursor.fetchall())

    def gestionar_categorias(self):
        """Ventana para gestionar categorías y subcategorías"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Gestión de Categorías")
        ventana.geometry("700x500")
        ventana.minsize(620, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        
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
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
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
        dlg.geometry("400x160")
        dlg.minsize(340, 200)
        dlg.resizable(True, True)
        _centrar(dlg, self.root)
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
        dlg.geometry("400x160")
        dlg.minsize(340, 200)
        dlg.resizable(True, True)
        _centrar(dlg, self.root)
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
            self.sistema.actualizar_dashboard()
            # Refrescar stock si el módulo está cargado
            if hasattr(self, '_stock'):
                try:
                    self.sistema._stock.cargar_vista_stock()
                    self.sistema._stock.cargar_historial()
                except Exception:
                    pass

        ventana_compra = VentanaCompra(self.root, self.conn, self.cursor,
                                       modo='nueva', on_guardado=_post_guardado)
        self.root.wait_window(ventana_compra.ventana)
        # Asegurar refresco incluso si se cerró sin guardar
        self.cargar_compras()
        self.sistema.actualizar_dashboard()
    
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
        ventana.minsize(620, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        
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
            bg='#6b7280',
            fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2',
            padx=20,
            pady=8
        ).pack(pady=10)
        
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    

