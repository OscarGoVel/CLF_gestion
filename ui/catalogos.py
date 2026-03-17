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

        # ── Tab Clientes ──────────────────────────────────────────────────
        tab_cli = tk.Frame(nb, bg=self.C['content_bg'])
        nb.add(tab_cli, text='👥  Clientes')

        tb_cli = tk.Frame(tab_cli, bg=self.C['toolbar_bg'])
        tb_cli.pack(fill='x')
        tk.Frame(tab_cli, bg=self.C['toolbar_border'], height=1).pack(fill='x')
        self.sistema._toolbar_btn(tb_cli, '➕ Nuevo',    self.nuevo_cliente,   color=self.C['accent'])
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
        self.sistema._toolbar_btn(tb_prod, '📋 Categorías', self.gestionar_categorias)

        ff_prod = tk.Frame(tab_prod, bg=self.C['toolbar_bg'], pady=4)
        ff_prod.pack(fill='x')
        tk.Label(ff_prod, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_producto = tk.Entry(ff_prod, font=('Arial', 9), width=30)
        self.entry_buscar_producto.pack(side='left', padx=4)
        self.entry_buscar_producto.bind('<Return>', lambda e: self.cargar_productos())
        self.sistema._toolbar_btn(ff_prod, '🔍', self.cargar_productos)

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
        self.sistema._configurar_sorting_treeview(self.tree_productos,
            columnas_numericas=['Precio Base', 'Precio Venta', 'Stock', 'Stock Mín'])
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
        self.sistema._toolbar_btn(tb_prov, '🛒 Presupuesto Compra', self.generar_presupuesto_compra)

        ff_prov = tk.Frame(tab_prov, bg=self.C['toolbar_bg'], pady=4)
        ff_prov.pack(fill='x')
        tk.Label(ff_prov, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=8)
        self.entry_buscar_proveedor = tk.Entry(ff_prov, font=('Arial', 9), width=30)
        self.entry_buscar_proveedor.pack(side='left', padx=4)
        self.entry_buscar_proveedor.bind('<Return>', lambda e: self.cargar_proveedores())
        self.sistema._toolbar_btn(ff_prov, '🔍', self.cargar_proveedores)

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
        ventana.geometry("720x660")
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
                    # Registrar precio inicial en historial
                    nuevo_id = self.cursor.lastrowid
                    self._registrar_precio_historial(
                        nuevo_id, datos['precio_base'],
                        motivo='Precio inicial al crear producto', fuente='manual')
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
                    # Registrar cambio de precio si cambió
                    self.cursor.execute(
                        "SELECT precio_base FROM productos WHERE id=?", (producto_id,))
                    row_prev = self.cursor.fetchone()
                    if row_prev:
                        self._registrar_precio_historial(
                            producto_id, datos['precio_base'],
                            precio_anterior=row_prev[0],
                            motivo=None, fuente='manual')

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

        # Botón de historial de precios (solo en modo editar)
        if modo == 'editar' and producto_id:
            tk.Button(
                frame_botones,
                text='📈 Historial de Precios',
                command=lambda: self._ver_historial_precios(producto_id, ventana),
                bg='#1a4b8c', fg='white',
                font=('Arial', 10, 'bold'),
                cursor='hand2', padx=15, pady=8
            ).pack(side='left', padx=5)

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
    
    def _ver_historial_precios(self, producto_id, parent):
        """Muestra ventana con el historial completo de precios del producto."""
        self.cursor.execute(
            "SELECT nombre, precio_base FROM productos WHERE id=?", (producto_id,))
        prod = self.cursor.fetchone()
        if not prod:
            return
        nombre_prod, precio_actual = prod

        self.cursor.execute("""
            SELECT fecha, precio, motivo, fuente, fecha_registro
            FROM producto_precio_historial
            WHERE producto_id = ?
            ORDER BY fecha DESC, fecha_registro DESC
        """, (producto_id,))
        registros = self.cursor.fetchall()

        win = tk.Toplevel(parent)
        win.title(f"📈 Historial de Precios — {nombre_prod}")
        win.geometry("680x460")
        win.configure(bg="#f1f5f9")
        win.transient(parent)
        win.grab_set()

        # Header
        hdr = tk.Frame(win, bg="#1a4b8c", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"📈  Historial de Precios",
                 font=("Arial", 11, "bold"), bg="#1a4b8c", fg="white").pack()
        tk.Label(hdr, text=f"{nombre_prod}   •   Precio actual: ${precio_actual:,.2f}",
                 font=("Arial", 9), bg="#1a4b8c", fg="#bfdbfe").pack()

        # Tabla
        frame_tbl = tk.Frame(win, bg="#f1f5f9")
        frame_tbl.pack(fill="both", expand=True, padx=16, pady=12)

        cols = ("Fecha", "Precio", "Variación", "Motivo", "Fuente")
        tree = ttk.Treeview(frame_tbl, columns=cols, show="headings", height=14)
        widths = [90, 100, 90, 280, 80]
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=40,
                        anchor="e" if col in ("Precio","Variación") else "w")

        tree.tag_configure("subida",  foreground="#dc2626")
        tree.tag_configure("bajada",  foreground="#16a34a")
        tree.tag_configure("neutro",  foreground="#374151")
        tree.tag_configure("par",     background="#f8fafc")
        tree.tag_configure("impar",   background="white")

        sc = ttk.Scrollbar(frame_tbl, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sc.set)
        tree.pack(side="left", fill="both", expand=True)
        sc.pack(side="right", fill="y")

        precio_prev = None
        for i, (fecha, precio, motivo, fuente, _) in enumerate(registros):
            if precio_prev is not None:
                diff = precio - precio_prev
                var_txt = f"{'▲' if diff > 0 else '▼'} ${abs(diff):,.2f}"
                tag_var = "subida" if diff > 0 else "bajada"
            else:
                var_txt = "—"
                tag_var = "neutro"
            fila_tag = "par" if i % 2 == 0 else "impar"
            tree.insert("", "end", tags=(tag_var, fila_tag), values=(
                (fecha or "")[:10],
                f"${precio:,.2f}",
                var_txt,
                motivo or "—",
                fuente or "manual",
            ))
            precio_prev = precio

        if not registros:
            tree.insert("", "end", values=("—", "—", "—", "Sin registros aún", "—"))

        # Footer info
        foot = tk.Frame(win, bg="#e2e8f0", pady=8)
        foot.pack(fill="x")
        n = len(registros)
        tk.Label(foot, text=f"{n} registro{'s' if n!=1 else ''} en historial",
                 font=("Arial", 8), bg="#e2e8f0", fg="#6b7280").pack(side="left", padx=12)
        tk.Button(foot, text="Cerrar", command=win.destroy,
                  bg="#6b7280", fg="white", font=("Arial", 9),
                  cursor="hand2", padx=12, pady=4, relief="flat").pack(side="right", padx=12)

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
    

