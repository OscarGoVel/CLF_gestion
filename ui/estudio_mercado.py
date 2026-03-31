#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/estudio_mercado.py
Módulo de Estudio de Mercado: comparación de precios entre proveedores.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date as _date
import itertools
import os


# ─────────────────────────────────────────────────────────────────────────────
# SECCIÓN PRINCIPAL (listado de estudios)
# ─────────────────────────────────────────────────────────────────────────────
class SeccionEstudioMercado:
    """Sección del sistema que lista todos los estudios de mercado."""

    def __init__(self, sistema):
        self.sistema = sistema
        self.conn    = sistema.conn
        self.cursor  = sistema.cursor
        self.root    = sistema.root
        self.C       = sistema.C
        self.tree    = None

    # ── Tablas ────────────────────────────────────────────────────────────
    def _ensure_tables(self):
        """Crea las tablas en PostgreSQL si no existen."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS estudios_mercado (
                id             SERIAL PRIMARY KEY,
                nombre         TEXT NOT NULL,
                fecha          TEXT NOT NULL,
                descripcion    TEXT,
                estado         TEXT DEFAULT 'abierto',
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS estudio_mercado_items (
                id              SERIAL PRIMARY KEY,
                estudio_id      INTEGER NOT NULL
                                    REFERENCES estudios_mercado(id) ON DELETE CASCADE,
                producto_id     INTEGER REFERENCES productos(id),
                nombre_articulo TEXT NOT NULL,
                cantidad        REAL DEFAULT 1,
                unidad          TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS estudio_mercado_cotizaciones (
                id               SERIAL PRIMARY KEY,
                item_id          INTEGER NOT NULL
                                     REFERENCES estudio_mercado_items(id) ON DELETE CASCADE,
                proveedor_id     INTEGER REFERENCES proveedores(id),
                nombre_proveedor TEXT NOT NULL,
                precio_unitario  REAL NOT NULL,
                notas            TEXT
            )
        """)
        self.conn.commit()

    # ── Construcción de UI ────────────────────────────────────────────────
    def crear_seccion(self):
        self._ensure_tables()
        sec = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['estudio_mercado'] = sec

        # Toolbar
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], pady=4)
        tb.pack(fill='x')
        self.sistema._toolbar_btn(tb, '➕  Nuevo Estudio', self.nuevo_estudio,
                                  color=self.C['accent'])
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '✏  Editar', self.editar_estudio)
        self.sistema._toolbar_btn(tb, '🗑  Eliminar', self.eliminar_estudio,
                                  peligro=True)
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '🔄  Actualizar', self.cargar_estudios)

        # Treeview
        cols = ('id', 'Nombre', 'Fecha', 'Artículos', 'Total estimado', 'Estado')
        ft = tk.Frame(sec, bg=self.C['content_bg'])
        ft.pack(fill='both', expand=True, padx=8, pady=8)

        self.tree = ttk.Treeview(ft, columns=cols, show='headings')
        self.tree.column('id',             width=0,   stretch=False)
        self.tree.column('Nombre',         width=300)
        self.tree.column('Fecha',          width=90,  anchor='center')
        self.tree.column('Artículos',      width=80,  anchor='center')
        self.tree.column('Total estimado', width=140, anchor='e')
        self.tree.column('Estado',         width=90,  anchor='center')
        for c in cols[1:]:
            self.tree.heading(c, text=c)

        sb = ttk.Scrollbar(ft, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda e: self.editar_estudio())

        self.cargar_estudios()

    # ── Datos ─────────────────────────────────────────────────────────────
    def cargar_estudios(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.cursor.execute("""
            SELECT em.id, em.nombre, em.fecha,
                   COUNT(DISTINCT emi.id),
                   COALESCE(SUM(
                       CASE WHEN emi.id IS NOT NULL THEN
                           emi.cantidad * (
                               SELECT MIN(c2.precio_unitario)
                               FROM estudio_mercado_cotizaciones c2
                               WHERE c2.item_id = emi.id
                           )
                       ELSE 0 END
                   ), 0),
                   em.estado
            FROM estudios_mercado em
            LEFT JOIN estudio_mercado_items emi ON emi.estudio_id = em.id
            GROUP BY em.id
            ORDER BY em.fecha DESC, em.id DESC
        """)
        for row in self.cursor.fetchall():
            eid, nombre, fecha, n_items, total, estado = row
            total_fmt = f'${total:,.2f}' if total else '—'
            self.tree.insert('', 'end',
                             values=(eid, nombre, fecha or '', n_items,
                                     total_fmt, estado or 'abierto'))

    def _id_sel(self):
        sel = self.tree.selection()
        return self.tree.item(sel[0])['values'][0] if sel else None

    # ── Acciones ──────────────────────────────────────────────────────────
    def nuevo_estudio(self):
        VentanaEstudioMercado(self.root, self.conn, self.cursor,
                              modo='nuevo', on_guardado=self.cargar_estudios)

    def editar_estudio(self):
        eid = self._id_sel()
        if not eid:
            messagebox.showinfo('Selección', 'Selecciona un estudio para editar.',
                                parent=self.root)
            return
        VentanaEstudioMercado(self.root, self.conn, self.cursor,
                              modo='editar', estudio_id=eid,
                              on_guardado=self.cargar_estudios)

    def eliminar_estudio(self):
        eid = self._id_sel()
        if not eid:
            messagebox.showinfo('Selección', 'Selecciona un estudio para eliminar.',
                                parent=self.root)
            return
        nombre = self.tree.item(self.tree.selection()[0])['values'][1]
        if not messagebox.askyesno(
                'Confirmar eliminación',
                f'¿Eliminar el estudio "{nombre}"?\n'
                'Se eliminarán todos sus artículos y cotizaciones.',
                parent=self.root):
            return
        self.cursor.execute('DELETE FROM estudios_mercado WHERE id=?', (eid,))
        self.conn.commit()
        self.cargar_estudios()


# ─────────────────────────────────────────────────────────────────────────────
# DIÁLOGO DE ESTUDIO
# ─────────────────────────────────────────────────────────────────────────────
class VentanaEstudioMercado:
    """Diálogo para crear / editar un estudio de mercado."""

    _ITEM_GEN = itertools.count(1)
    _COT_GEN  = itertools.count(1)

    def __init__(self, parent, conn, cursor, modo='nuevo',
                 estudio_id=None, on_guardado=None):
        self.parent      = parent
        self.conn        = conn
        self.cursor      = cursor
        self.modo        = modo
        self.estudio_id  = estudio_id
        self.on_guardado = on_guardado

        # Datos en memoria: lista de items, cada uno con sus cotizaciones
        self._items = []          # [item_dict, ...]
        self._item_sel_key = None # key del item seleccionado en el panel izq.

        self._ventana = tk.Toplevel(parent)
        titulo = 'Nuevo Estudio de Mercado' if modo == 'nuevo' else 'Editar Estudio de Mercado'
        self._ventana.title(titulo)
        self._ventana.geometry('1150x700')
        self._ventana.minsize(900, 560)
        self._ventana.resizable(True, True)
        self._ventana.transient(parent)
        self._ventana.grab_set()
        self._ventana.bind('<Escape>', lambda e: self._ventana.destroy())

        try:
            from ui.utils import centrar_ventana
            centrar_ventana(self._ventana, parent)
        except Exception:
            pass

        self._crear_interfaz()

        if modo == 'editar' and estudio_id:
            self._cargar_datos()

    # ── Interfaz ──────────────────────────────────────────────────────────
    def _crear_interfaz(self):
        v = self._ventana

        # ── Cabecera del diálogo ──────────────────────────────────────────
        hdr = tk.Frame(v, bg='#1a4b8c', pady=6)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🔍  Estudio de Mercado',
                 font=('Arial', 11, 'bold'), bg='#1a4b8c', fg='white'
                 ).pack(side='left', padx=14)

        # ── Formulario de cabecera (nombre, fecha, descripción) ───────────
        hf = tk.Frame(v, bg='#f1f5f9', pady=6, padx=12)
        hf.pack(fill='x')

        # Nombre
        tk.Label(hf, text='Nombre del estudio *', font=('Arial', 9, 'bold'),
                 bg='#f1f5f9', fg='#374151').grid(row=0, column=0, sticky='w', padx=(0, 8))
        self._e_nombre = tk.Entry(hf, font=('Arial', 9), width=40, relief='solid', bd=1)
        self._e_nombre.grid(row=0, column=1, sticky='ew', padx=(0, 16))

        # Fecha
        tk.Label(hf, text='Fecha *', font=('Arial', 9, 'bold'),
                 bg='#f1f5f9', fg='#374151').grid(row=0, column=2, sticky='w', padx=(0, 8))
        self._e_fecha = tk.Entry(hf, font=('Arial', 9), width=12, relief='solid', bd=1)
        self._e_fecha.insert(0, str(_date.today()))
        self._e_fecha.grid(row=0, column=3, sticky='w', padx=(0, 16))

        # Descripción
        tk.Label(hf, text='Descripción', font=('Arial', 9),
                 bg='#f1f5f9', fg='#374151').grid(row=0, column=4, sticky='w', padx=(0, 8))
        self._e_desc = tk.Entry(hf, font=('Arial', 9), width=32, relief='solid', bd=1)
        self._e_desc.grid(row=0, column=5, sticky='ew')
        hf.columnconfigure(5, weight=1)

        # ── Panel dividido (artículos | cotizaciones) ─────────────────────
        paned = tk.PanedWindow(v, orient='horizontal', sashwidth=5,
                               sashrelief='flat', bg='#cbd5e1')
        paned.pack(fill='both', expand=True, padx=0, pady=0)

        self._crear_panel_items(paned)
        self._crear_panel_cots(paned)

        # ── Footer ────────────────────────────────────────────────────────
        foot = tk.Frame(v, bg='#e2e8f0', pady=6)
        foot.pack(fill='x', side='bottom')

        self._lbl_total = tk.Label(foot, text='Total estimado: —',
                                   font=('Arial', 10, 'bold'),
                                   bg='#e2e8f0', fg='#1e293b')
        self._lbl_total.pack(side='left', padx=16)

        tk.Button(foot, text='📄  Generar PDF', command=self._generar_pdf,
                  font=('Arial', 9), bg='#0f7b5e', fg='white',
                  cursor='hand2', padx=12, pady=4, relief='flat'
                  ).pack(side='right', padx=6)
        tk.Button(foot, text='💾  Guardar', command=self.guardar,
                  font=('Arial', 10, 'bold'), bg='#1a4b8c', fg='white',
                  cursor='hand2', padx=14, pady=4, relief='flat'
                  ).pack(side='right', padx=6)
        tk.Button(foot, text='Cerrar', command=self._ventana.destroy,
                  font=('Arial', 9), bg='#6b7280', fg='white',
                  cursor='hand2', padx=10, pady=4, relief='flat'
                  ).pack(side='right', padx=6)

    def _crear_panel_items(self, paned):
        """Panel izquierdo: lista de artículos del estudio."""
        frm = tk.Frame(paned, bg='#f8fafc')
        paned.add(frm, minsize=320)

        # Toolbar del panel
        tb = tk.Frame(frm, bg='#e2e8f0', pady=3)
        tb.pack(fill='x')
        tk.Label(tb, text='  Artículos a cotizar',
                 font=('Arial', 9, 'bold'), bg='#e2e8f0', fg='#374151'
                 ).pack(side='left')
        tk.Button(tb, text='+ Catálogo', command=self._agregar_item_catalogo,
                  font=('Arial', 8), bg='#1a4b8c', fg='white',
                  cursor='hand2', relief='flat', padx=6
                  ).pack(side='right', padx=4)
        tk.Button(tb, text='+ Libre', command=self._agregar_item_libre,
                  font=('Arial', 8), bg='#374151', fg='white',
                  cursor='hand2', relief='flat', padx=6
                  ).pack(side='right')
        tk.Button(tb, text='✕', command=self._quitar_item,
                  font=('Arial', 8), bg='#dc2626', fg='white',
                  cursor='hand2', relief='flat', padx=6
                  ).pack(side='left', padx=(6, 0))

        # Treeview de artículos
        cols = ('_key', 'Artículo', 'Cant.', 'Unidad', 'Mejor precio', 'Proveedor')
        self._tree_items = ttk.Treeview(frm, columns=cols, show='headings',
                                        selectmode='browse')
        self._tree_items.column('_key',         width=0,  stretch=False)
        self._tree_items.column('Artículo',      width=170)
        self._tree_items.column('Cant.',         width=55, anchor='e')
        self._tree_items.column('Unidad',        width=50, anchor='center')
        self._tree_items.column('Mejor precio',  width=95, anchor='e')
        self._tree_items.column('Proveedor',     width=110)
        for c in cols[1:]:
            self._tree_items.heading(c, text=c)

        sb = ttk.Scrollbar(frm, orient='vertical', command=self._tree_items.yview)
        self._tree_items.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._tree_items.pack(fill='both', expand=True)
        self._tree_items.bind('<<TreeviewSelect>>', self._on_item_select)

    def _crear_panel_cots(self, paned):
        """Panel derecho: cotizaciones del artículo seleccionado."""
        frm = tk.Frame(paned, bg='#f8fafc')
        paned.add(frm, minsize=400)

        # Toolbar
        tb = tk.Frame(frm, bg='#e2e8f0', pady=3)
        tb.pack(fill='x')
        self._lbl_cots_titulo = tk.Label(
            tb, text='  Selecciona un artículo',
            font=('Arial', 9, 'bold'), bg='#e2e8f0', fg='#374151')
        self._lbl_cots_titulo.pack(side='left')
        tk.Button(tb, text='+ Catálogo', command=self._agregar_cot_catalogo,
                  font=('Arial', 8), bg='#0f7b5e', fg='white',
                  cursor='hand2', relief='flat', padx=6
                  ).pack(side='right', padx=4)
        tk.Button(tb, text='+ Libre', command=self._agregar_cot_libre,
                  font=('Arial', 8), bg='#374151', fg='white',
                  cursor='hand2', relief='flat', padx=6
                  ).pack(side='right')
        tk.Button(tb, text='✕', command=self._quitar_cot,
                  font=('Arial', 8), bg='#dc2626', fg='white',
                  cursor='hand2', relief='flat', padx=6
                  ).pack(side='left', padx=(6, 0))

        # Treeview de cotizaciones
        cols = ('_key', 'Proveedor', 'Precio unit.', 'Total', 'Notas')
        self._tree_cots = ttk.Treeview(frm, columns=cols, show='headings',
                                       selectmode='browse')
        self._tree_cots.column('_key',        width=0,  stretch=False)
        self._tree_cots.column('Proveedor',   width=180)
        self._tree_cots.column('Precio unit.', width=100, anchor='e')
        self._tree_cots.column('Total',        width=100, anchor='e')
        self._tree_cots.column('Notas',        width=200)
        for c in cols[1:]:
            self._tree_cots.heading(c, text=c)
        self._tree_cots.tag_configure('mejor', background='#d1fae5', foreground='#065f46')

        sb = ttk.Scrollbar(frm, orient='vertical', command=self._tree_cots.yview)
        self._tree_cots.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self._tree_cots.pack(fill='both', expand=True)

    # ── Gestión de items ──────────────────────────────────────────────────
    def _nuevo_item(self, producto_id, nombre, cantidad, unidad):
        key = f'i{next(self._ITEM_GEN)}'
        return {'_key': key, 'db_id': None, 'producto_id': producto_id,
                'nombre_articulo': nombre, 'cantidad': cantidad,
                'unidad': unidad, 'cotizaciones': []}

    def _refrescar_tree_items(self):
        self._tree_items.delete(*self._tree_items.get_children())
        for item in self._items:
            mejor_p, mejor_prov = self._mejor_cotizacion(item)
            mejor_fmt = f'${mejor_p:,.2f}' if mejor_p is not None else '—'
            self._tree_items.insert('', 'end', iid=item['_key'],
                                    values=(item['_key'],
                                            item['nombre_articulo'],
                                            f"{item['cantidad']:g}",
                                            item['unidad'] or '',
                                            mejor_fmt,
                                            mejor_prov or '—'))
        self._actualizar_total()

    def _on_item_select(self, event=None):
        sel = self._tree_items.selection()
        if not sel:
            return
        self._item_sel_key = sel[0]
        item = self._item_por_key(self._item_sel_key)
        if item:
            nombre = item['nombre_articulo']
            cant   = item['cantidad']
            self._lbl_cots_titulo.config(
                text=f'  Cotizaciones — {nombre} (cant: {cant:g})')
            self._refrescar_tree_cots(item)

    def _item_por_key(self, key):
        return next((i for i in self._items if i['_key'] == key), None)

    def _agregar_item_catalogo(self):
        self.cursor.execute(
            'SELECT id, nombre, unidad_medida FROM productos ORDER BY nombre')
        prods = self.cursor.fetchall()
        if not prods:
            messagebox.showinfo('Sin productos',
                                'No hay productos en el catálogo.',
                                parent=self._ventana)
            return
        _DlgSeleccion(
            self._ventana,
            titulo='Seleccionar producto del catálogo',
            opciones=[(f'{p[1]}', p[0], p[2]) for p in prods],
            on_ok=lambda pid, unidad: self._confirmar_item_catalogo(pid, prods, unidad)
        )

    def _confirmar_item_catalogo(self, prod_id, prods, unidad_default):
        prod = next((p for p in prods if p[0] == prod_id), None)
        if not prod:
            return
        _DlgCantidad(
            self._ventana,
            nombre=prod[1],
            unidad_default=prod[2] or '',
            on_ok=lambda cant, unid: self._items.append(
                self._nuevo_item(prod[0], prod[1], cant, unid)
            ) or self._refrescar_tree_items()
        )

    def _agregar_item_libre(self):
        _DlgItemLibre(
            self._ventana,
            on_ok=lambda nombre, cant, unid: self._items.append(
                self._nuevo_item(None, nombre, cant, unid)
            ) or self._refrescar_tree_items()
        )

    def _quitar_item(self):
        sel = self._tree_items.selection()
        if not sel:
            return
        key = sel[0]
        self._items = [i for i in self._items if i['_key'] != key]
        if self._item_sel_key == key:
            self._item_sel_key = None
            self._tree_cots.delete(*self._tree_cots.get_children())
            self._lbl_cots_titulo.config(text='  Selecciona un artículo')
        self._refrescar_tree_items()

    # ── Gestión de cotizaciones ───────────────────────────────────────────
    def _nueva_cot(self, proveedor_id, nombre_prov, precio, notas):
        key = f'c{next(self._COT_GEN)}'
        return {'_key': key, 'db_id': None, 'proveedor_id': proveedor_id,
                'nombre_proveedor': nombre_prov,
                'precio_unitario': precio, 'notas': notas}

    def _item_activo(self):
        if not self._item_sel_key:
            messagebox.showinfo('Sin selección',
                                'Primero selecciona un artículo en el panel izquierdo.',
                                parent=self._ventana)
            return None
        return self._item_por_key(self._item_sel_key)

    def _refrescar_tree_cots(self, item):
        self._tree_cots.delete(*self._tree_cots.get_children())
        if not item['cotizaciones']:
            return
        min_p = min(c['precio_unitario'] for c in item['cotizaciones'])
        for cot in item['cotizaciones']:
            total = cot['precio_unitario'] * item['cantidad']
            tag   = ('mejor',) if cot['precio_unitario'] == min_p else ()
            self._tree_cots.insert('', 'end', iid=cot['_key'],
                                   values=(cot['_key'],
                                           cot['nombre_proveedor'],
                                           f"${cot['precio_unitario']:,.4f}",
                                           f'${total:,.2f}',
                                           cot['notas'] or ''),
                                   tags=tag)
        self._refrescar_tree_items()  # actualiza "mejor precio" en el item

    def _agregar_cot_catalogo(self):
        item = self._item_activo()
        if not item:
            return
        self.cursor.execute(
            'SELECT id, nombre FROM proveedores ORDER BY nombre')
        provs = self.cursor.fetchall()
        if not provs:
            messagebox.showinfo('Sin proveedores',
                                'No hay proveedores en el catálogo.',
                                parent=self._ventana)
            return
        _DlgSeleccion(
            self._ventana,
            titulo='Seleccionar proveedor del catálogo',
            opciones=[(p[1], p[0], None) for p in provs],
            on_ok=lambda pid, _: self._pedir_precio_cot(item, pid,
                next((p[1] for p in provs if p[0] == pid), ''))
        )

    def _pedir_precio_cot(self, item, proveedor_id, nombre_prov):
        _DlgCotizacion(
            self._ventana,
            proveedor_nombre=nombre_prov,
            on_ok=lambda precio, notas: (
                item['cotizaciones'].append(
                    self._nueva_cot(proveedor_id, nombre_prov, precio, notas)),
                self._refrescar_tree_cots(item)
            )
        )

    def _agregar_cot_libre(self):
        item = self._item_activo()
        if not item:
            return
        _DlgCotLibre(
            self._ventana,
            on_ok=lambda nombre, precio, notas: (
                item['cotizaciones'].append(
                    self._nueva_cot(None, nombre, precio, notas)),
                self._refrescar_tree_cots(item)
            )
        )

    def _quitar_cot(self):
        item = self._item_activo()
        if not item:
            return
        sel = self._tree_cots.selection()
        if not sel:
            return
        key = sel[0]
        item['cotizaciones'] = [c for c in item['cotizaciones']
                                if c['_key'] != key]
        self._refrescar_tree_cots(item)

    # ── Cálculos ──────────────────────────────────────────────────────────
    def _mejor_cotizacion(self, item):
        """Retorna (precio_min, nombre_proveedor) o (None, None) si no hay cotizaciones."""
        if not item['cotizaciones']:
            return None, None
        mejor = min(item['cotizaciones'], key=lambda c: c['precio_unitario'])
        return mejor['precio_unitario'], mejor['nombre_proveedor']

    def _actualizar_total(self):
        total = 0.0
        for item in self._items:
            p, _ = self._mejor_cotizacion(item)
            if p is not None:
                total += p * item['cantidad']
        self._lbl_total.config(
            text=f'Total estimado: ${total:,.2f}' if total else 'Total estimado: —')

    # ── Cargar datos existentes (modo editar) ─────────────────────────────
    def _cargar_datos(self):
        self.cursor.execute(
            'SELECT nombre, fecha, descripcion, estado FROM estudios_mercado WHERE id=?',
            (self.estudio_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        nombre, fecha, desc, estado = row
        self._e_nombre.delete(0, 'end')
        self._e_nombre.insert(0, nombre or '')
        self._e_fecha.delete(0, 'end')
        self._e_fecha.insert(0, fecha or '')
        self._e_desc.delete(0, 'end')
        self._e_desc.insert(0, desc or '')

        # Cargar items
        self.cursor.execute(
            'SELECT id, producto_id, nombre_articulo, cantidad, unidad '
            'FROM estudio_mercado_items WHERE estudio_id=? ORDER BY id',
            (self.estudio_id,))
        for irow in self.cursor.fetchall():
            iid, prod_id, nombre, cantidad, unidad = irow
            item = self._nuevo_item(prod_id, nombre, cantidad or 1, unidad)
            item['db_id'] = iid

            # Cotizaciones del item
            self.cursor.execute(
                'SELECT id, proveedor_id, nombre_proveedor, precio_unitario, notas '
                'FROM estudio_mercado_cotizaciones WHERE item_id=? ORDER BY id',
                (iid,))
            for crow in self.cursor.fetchall():
                cid, prov_id, nombre_prov, precio, notas = crow
                cot = self._nueva_cot(prov_id, nombre_prov, precio, notas)
                cot['db_id'] = cid
                item['cotizaciones'].append(cot)
            self._items.append(item)

        self._refrescar_tree_items()

    # ── Guardar ───────────────────────────────────────────────────────────
    def guardar(self):
        nombre = self._e_nombre.get().strip()
        fecha  = self._e_fecha.get().strip()
        if not nombre:
            messagebox.showwarning('Campos requeridos',
                                   'El nombre del estudio es obligatorio.',
                                   parent=self._ventana)
            self._e_nombre.focus_set()
            return
        if not fecha:
            messagebox.showwarning('Campos requeridos',
                                   'La fecha es obligatoria.',
                                   parent=self._ventana)
            self._e_fecha.focus_set()
            return

        desc = self._e_desc.get().strip() or None
        try:
            if self.modo == 'nuevo':
                self.cursor.execute(
                    'INSERT INTO estudios_mercado (nombre, fecha, descripcion) VALUES (?,?,?)',
                    (nombre, fecha, desc))
                self.estudio_id = self.cursor.lastrowid
            else:
                self.cursor.execute(
                    'UPDATE estudios_mercado SET nombre=?, fecha=?, descripcion=? WHERE id=?',
                    (nombre, fecha, desc, self.estudio_id))
                # Eliminar items y cotizaciones existentes (se reinsertarán)
                self.cursor.execute(
                    'DELETE FROM estudio_mercado_items WHERE estudio_id=?',
                    (self.estudio_id,))

            # Insertar items y cotizaciones
            for item in self._items:
                self.cursor.execute(
                    'INSERT INTO estudio_mercado_items '
                    '(estudio_id, producto_id, nombre_articulo, cantidad, unidad) '
                    'VALUES (?,?,?,?,?)',
                    (self.estudio_id, item['producto_id'],
                     item['nombre_articulo'], item['cantidad'],
                     item['unidad']))
                item_db_id = self.cursor.lastrowid
                for cot in item['cotizaciones']:
                    self.cursor.execute(
                        'INSERT INTO estudio_mercado_cotizaciones '
                        '(item_id, proveedor_id, nombre_proveedor, precio_unitario, notas) '
                        'VALUES (?,?,?,?,?)',
                        (item_db_id, cot['proveedor_id'],
                         cot['nombre_proveedor'], cot['precio_unitario'],
                         cot['notas']))
            self.conn.commit()
            if self.on_guardado:
                self.on_guardado()
            self._ventana.destroy()
        except Exception as e:
            messagebox.showerror('Error al guardar', str(e), parent=self._ventana)

    # ── PDF ───────────────────────────────────────────────────────────────
    def _generar_pdf(self):
        if not self._items:
            messagebox.showinfo('Sin datos',
                                'Agrega al menos un artículo antes de generar el PDF.',
                                parent=self._ventana)
            return
        nombre_estudio = self._e_nombre.get().strip() or 'Estudio de Mercado'
        fecha = self._e_fecha.get().strip()
        ruta = filedialog.asksaveasfilename(
            parent=self._ventana,
            defaultextension='.pdf',
            filetypes=[('PDF', '*.pdf')],
            initialfile=f'EstudioMercado_{nombre_estudio[:30]}.pdf',
            title='Guardar PDF del estudio de mercado')
        if not ruta:
            return
        try:
            import app_config, sesion
            empresa = getattr(app_config, 'EMPRESA_NOMBRE', '') or ''
        except Exception:
            empresa = ''
        try:
            _generar_pdf_estudio(
                empresa_nombre=empresa,
                estudio_nombre=nombre_estudio,
                fecha=fecha,
                descripcion=self._e_desc.get().strip(),
                items=self._items,
                ruta=ruta
            )
            messagebox.showinfo('PDF generado',
                                f'Reporte guardado en:\n{ruta}',
                                parent=self._ventana)
            try:
                os.startfile(ruta)
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror('Error al generar PDF', str(e),
                                 parent=self._ventana)


# ─────────────────────────────────────────────────────────────────────────────
# MINI-DIÁLOGOS AUXILIARES
# ─────────────────────────────────────────────────────────────────────────────
class _DlgSeleccion:
    """Diálogo genérico para seleccionar un elemento de una lista."""

    def __init__(self, parent, titulo, opciones, on_ok):
        # opciones = [(label, id, extra), ...]
        self._opciones = opciones
        self._on_ok    = on_ok

        dlg = tk.Toplevel(parent)
        dlg.title(titulo)
        dlg.geometry('380x340')
        dlg.transient(parent)
        dlg.grab_set()
        dlg.bind('<Escape>', lambda e: dlg.destroy())

        tk.Label(dlg, text=titulo, font=('Arial', 9, 'bold'),
                 pady=8).pack()

        # Búsqueda
        frb = tk.Frame(dlg)
        frb.pack(fill='x', padx=8, pady=(0, 4))
        tk.Label(frb, text='Buscar:', font=('Arial', 8)).pack(side='left')
        e_buscar = tk.Entry(frb, font=('Arial', 9))
        e_buscar.pack(side='left', fill='x', expand=True, padx=4)

        lb = tk.Listbox(dlg, font=('Arial', 9), activestyle='dotbox')
        sb = ttk.Scrollbar(dlg, orient='vertical', command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y', padx=(0, 8))
        lb.pack(fill='both', expand=True, padx=(8, 0))

        def _poblar(filtro=''):
            lb.delete(0, 'end')
            for label, _, __ in opciones:
                if filtro.lower() in label.lower():
                    lb.insert('end', label)

        _poblar()

        def _filtrar(e=None):
            _poblar(e_buscar.get())

        e_buscar.bind('<KeyRelease>', _filtrar)
        e_buscar.focus_set()

        def _ok(e=None):
            sel = lb.curselection()
            if not sel:
                return
            label_sel = lb.get(sel[0])
            op = next((o for o in opciones if o[0] == label_sel), None)
            if op:
                dlg.destroy()
                on_ok(op[1], op[2])

        lb.bind('<Double-1>', _ok)
        tk.Button(dlg, text='Seleccionar', command=_ok,
                  bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', pady=4).pack(fill='x', padx=8, pady=6)


class _DlgCantidad:
    """Diálogo para ingresar cantidad y unidad de un producto del catálogo."""

    def __init__(self, parent, nombre, unidad_default, on_ok):
        dlg = tk.Toplevel(parent)
        dlg.title('Cantidad')
        dlg.geometry('300x160')
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        tk.Label(dlg, text=nombre, font=('Arial', 9, 'bold'),
                 wraplength=280, pady=8).pack()

        fr = tk.Frame(dlg)
        fr.pack(padx=16, pady=4, fill='x')
        tk.Label(fr, text='Cantidad:', font=('Arial', 9), width=10,
                 anchor='w').grid(row=0, column=0, pady=4)
        e_cant = tk.Entry(fr, font=('Arial', 9), width=12, relief='solid', bd=1)
        e_cant.insert(0, '1')
        e_cant.grid(row=0, column=1, sticky='w')

        tk.Label(fr, text='Unidad:', font=('Arial', 9), width=10,
                 anchor='w').grid(row=1, column=0, pady=4)
        e_unid = tk.Entry(fr, font=('Arial', 9), width=12, relief='solid', bd=1)
        e_unid.insert(0, unidad_default)
        e_unid.grid(row=1, column=1, sticky='w')

        def _ok(e=None):
            try:
                cant = float(e_cant.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Error', 'Cantidad inválida.', parent=dlg)
                return
            unid = e_unid.get().strip()
            dlg.destroy()
            on_ok(cant, unid)

        tk.Button(dlg, text='Agregar', command=_ok,
                  bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', pady=4).pack(fill='x', padx=16, pady=8)
        dlg.bind('<Return>', _ok)
        e_cant.focus_set()
        e_cant.select_range(0, 'end')


class _DlgItemLibre:
    """Diálogo para ingresar un artículo libre (no en catálogo)."""

    def __init__(self, parent, on_ok):
        dlg = tk.Toplevel(parent)
        dlg.title('Artículo libre')
        dlg.geometry('320x200')
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        tk.Label(dlg, text='Nuevo artículo (entrada libre)',
                 font=('Arial', 9, 'bold'), pady=8).pack()

        fr = tk.Frame(dlg)
        fr.pack(padx=16, pady=4, fill='x')
        tk.Label(fr, text='Artículo *:', font=('Arial', 9), width=12,
                 anchor='w').grid(row=0, column=0, pady=4)
        e_nombre = tk.Entry(fr, font=('Arial', 9), width=24, relief='solid', bd=1)
        e_nombre.grid(row=0, column=1, sticky='ew')

        tk.Label(fr, text='Cantidad *:', font=('Arial', 9), width=12,
                 anchor='w').grid(row=1, column=0, pady=4)
        e_cant = tk.Entry(fr, font=('Arial', 9), width=24, relief='solid', bd=1)
        e_cant.insert(0, '1')
        e_cant.grid(row=1, column=1, sticky='ew')

        tk.Label(fr, text='Unidad:', font=('Arial', 9), width=12,
                 anchor='w').grid(row=2, column=0, pady=4)
        e_unid = tk.Entry(fr, font=('Arial', 9), width=24, relief='solid', bd=1)
        e_unid.grid(row=2, column=1, sticky='ew')

        def _ok(e=None):
            nombre = e_nombre.get().strip()
            if not nombre:
                messagebox.showwarning('Error', 'El nombre es obligatorio.', parent=dlg)
                return
            try:
                cant = float(e_cant.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Error', 'Cantidad inválida.', parent=dlg)
                return
            unid = e_unid.get().strip()
            dlg.destroy()
            on_ok(nombre, cant, unid)

        tk.Button(dlg, text='Agregar', command=_ok,
                  bg='#374151', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', pady=4).pack(fill='x', padx=16, pady=8)
        dlg.bind('<Return>', _ok)
        e_nombre.focus_set()


class _DlgCotizacion:
    """Diálogo para ingresar precio y notas de la cotización de un proveedor."""

    def __init__(self, parent, proveedor_nombre, on_ok):
        dlg = tk.Toplevel(parent)
        dlg.title(f'Precio — {proveedor_nombre}')
        dlg.geometry('300x160')
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        tk.Label(dlg, text=proveedor_nombre, font=('Arial', 9, 'bold'),
                 pady=6).pack()

        fr = tk.Frame(dlg)
        fr.pack(padx=16, fill='x')
        tk.Label(fr, text='Precio unit. *:', font=('Arial', 9), width=13,
                 anchor='w').grid(row=0, column=0, pady=4)
        e_precio = tk.Entry(fr, font=('Arial', 9), width=16, relief='solid', bd=1)
        e_precio.grid(row=0, column=1, sticky='ew')

        tk.Label(fr, text='Notas:', font=('Arial', 9), width=13,
                 anchor='w').grid(row=1, column=0, pady=4)
        e_notas = tk.Entry(fr, font=('Arial', 9), width=16, relief='solid', bd=1)
        e_notas.grid(row=1, column=1, sticky='ew')

        def _ok(e=None):
            try:
                precio = float(e_precio.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Error', 'Precio inválido.', parent=dlg)
                return
            notas = e_notas.get().strip()
            dlg.destroy()
            on_ok(precio, notas)

        tk.Button(dlg, text='Agregar cotización', command=_ok,
                  bg='#0f7b5e', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', pady=4).pack(fill='x', padx=16, pady=8)
        dlg.bind('<Return>', _ok)
        e_precio.focus_set()


class _DlgCotLibre(_DlgCotizacion):
    """Diálogo para cotización de proveedor libre (no en catálogo)."""

    def __init__(self, parent, on_ok):
        dlg = tk.Toplevel(parent)
        dlg.title('Cotización — proveedor libre')
        dlg.geometry('320x200')
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()

        tk.Label(dlg, text='Cotización de proveedor libre',
                 font=('Arial', 9, 'bold'), pady=6).pack()

        fr = tk.Frame(dlg)
        fr.pack(padx=16, fill='x')
        tk.Label(fr, text='Proveedor *:', font=('Arial', 9), width=13,
                 anchor='w').grid(row=0, column=0, pady=4)
        e_prov = tk.Entry(fr, font=('Arial', 9), width=20, relief='solid', bd=1)
        e_prov.grid(row=0, column=1, sticky='ew')

        tk.Label(fr, text='Precio unit. *:', font=('Arial', 9), width=13,
                 anchor='w').grid(row=1, column=0, pady=4)
        e_precio = tk.Entry(fr, font=('Arial', 9), width=20, relief='solid', bd=1)
        e_precio.grid(row=1, column=1, sticky='ew')

        tk.Label(fr, text='Notas:', font=('Arial', 9), width=13,
                 anchor='w').grid(row=2, column=0, pady=4)
        e_notas = tk.Entry(fr, font=('Arial', 9), width=20, relief='solid', bd=1)
        e_notas.grid(row=2, column=1, sticky='ew')

        def _ok(e=None):
            nombre = e_prov.get().strip()
            if not nombre:
                messagebox.showwarning('Error', 'El nombre del proveedor es obligatorio.',
                                       parent=dlg)
                return
            try:
                precio = float(e_precio.get().replace(',', '.'))
            except ValueError:
                messagebox.showwarning('Error', 'Precio inválido.', parent=dlg)
                return
            notas = e_notas.get().strip()
            dlg.destroy()
            on_ok(nombre, precio, notas)

        tk.Button(dlg, text='Agregar cotización', command=_ok,
                  bg='#374151', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', pady=4).pack(fill='x', padx=16, pady=8)
        dlg.bind('<Return>', _ok)
        e_prov.focus_set()


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE PDF
# ─────────────────────────────────────────────────────────────────────────────
def _generar_pdf_estudio(empresa_nombre, estudio_nombre, fecha,
                         descripcion, items, ruta):
    """Genera un PDF de comparación de precios del estudio de mercado."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    COLOR_HEADER  = colors.HexColor('#1a4b8c')
    COLOR_MEJOR   = colors.HexColor('#d1fae5')
    COLOR_GRIS    = colors.HexColor('#f1f5f9')
    COLOR_TEXTO   = colors.HexColor('#1e293b')

    doc = SimpleDocTemplate(
        ruta, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.5*inch,  bottomMargin=0.5*inch,
    )
    estilos = getSampleStyleSheet()
    ancho = doc.width

    st_titulo = ParagraphStyle('titulo', fontSize=14, textColor=COLOR_HEADER,
                               spaceAfter=2, fontName='Helvetica-Bold')
    st_sub    = ParagraphStyle('sub', fontSize=9, textColor=colors.HexColor('#374151'),
                               spaceAfter=6)
    st_item   = ParagraphStyle('item', fontSize=10, textColor=COLOR_TEXTO,
                               spaceBefore=10, spaceAfter=3,
                               fontName='Helvetica-Bold')
    st_nota   = ParagraphStyle('nota', fontSize=8, textColor=colors.gray,
                               spaceAfter=2)

    story = []

    # ── Encabezado ────────────────────────────────────────────────────────
    story.append(Paragraph(empresa_nombre or 'Estudio de Mercado', st_titulo))
    story.append(Paragraph(f'Estudio: {estudio_nombre}', st_sub))
    story.append(Paragraph(f'Fecha: {fecha}', st_sub))
    if descripcion:
        story.append(Paragraph(f'Descripción: {descripcion}', st_nota))
    story.append(Spacer(1, 8))

    # ── Tabla por artículo ────────────────────────────────────────────────
    total_general = 0.0

    for item in items:
        nombre = item['nombre_articulo']
        cant   = item['cantidad']
        unidad = item['unidad'] or ''
        cots   = item['cotizaciones']

        story.append(Paragraph(
            f'▸ {nombre}  —  Cantidad: {cant:g} {unidad}', st_item))

        if not cots:
            story.append(Paragraph('Sin cotizaciones registradas.', st_nota))
            story.append(Spacer(1, 4))
            continue

        min_precio = min(c['precio_unitario'] for c in cots)
        # Calcular mejor total para el total general
        total_general += min_precio * cant

        # Encabezado de tabla
        data = [['Proveedor', 'Precio unit.', f'Total (x{cant:g})', 'Notas', '★']]
        estilos_tabla = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 8),
            ('FONTSIZE',   (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_GRIS]),
            ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
            ('ALIGN',      (1, 0), (2, -1), 'RIGHT'),
            ('ALIGN',      (4, 0), (4, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]

        for idx, cot in enumerate(sorted(cots, key=lambda c: c['precio_unitario']), 1):
            precio = cot['precio_unitario']
            total  = precio * cant
            mejor  = precio == min_precio
            estrella = '★' if mejor else ''
            data.append([
                cot['nombre_proveedor'],
                f'${precio:,.4f}',
                f'${total:,.2f}',
                cot['notas'] or '',
                estrella,
            ])
            if mejor:
                row_idx = len(data) - 1
                estilos_tabla.append(
                    ('BACKGROUND', (0, row_idx), (-1, row_idx), COLOR_MEJOR))
                estilos_tabla.append(
                    ('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))

        col_ws = [ancho*0.35, ancho*0.15, ancho*0.15, ancho*0.30, ancho*0.05]
        tbl = Table(data, colWidths=col_ws)
        tbl.setStyle(TableStyle(estilos_tabla))
        story.append(tbl)
        story.append(Spacer(1, 6))

    # ── Resumen final ─────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    resumen_data = [['Artículo', 'Cant.', 'Unidad', 'Mejor proveedor',
                     'Precio unit.', 'Total']]
    for item in items:
        cots = item['cotizaciones']
        if cots:
            mejor = min(cots, key=lambda c: c['precio_unitario'])
            total = mejor['precio_unitario'] * item['cantidad']
            resumen_data.append([
                item['nombre_articulo'],
                f"{item['cantidad']:g}",
                item['unidad'] or '',
                mejor['nombre_proveedor'],
                f"${mejor['precio_unitario']:,.4f}",
                f'${total:,.2f}',
            ])
        else:
            resumen_data.append([
                item['nombre_articulo'],
                f"{item['cantidad']:g}",
                item['unidad'] or '',
                '—', '—', '—',
            ])

    # Fila de total general
    resumen_data.append(['', '', '', '', 'TOTAL ESTIMADO', f'${total_general:,.2f}'])

    tbl_resumen = Table(resumen_data,
                        colWidths=[ancho*0.30, ancho*0.07, ancho*0.08,
                                   ancho*0.25, ancho*0.15, ancho*0.15])
    n = len(resumen_data)
    tbl_resumen.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), COLOR_HEADER),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1), (-1, n-2), [colors.white, COLOR_GRIS]),
        ('BACKGROUND',    (0, n-1), (-1, n-1), colors.HexColor('#1e293b')),
        ('TEXTCOLOR',     (0, n-1), (-1, n-1), colors.white),
        ('FONTNAME',      (0, n-1), (-1, n-1), 'Helvetica-Bold'),
        ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
        ('GRID',          (0, 0), (-1, -1), 0.3, colors.HexColor('#cbd5e1')),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    story.append(Paragraph('Resumen comparativo', ParagraphStyle(
        'resumen_hdr', fontSize=11, textColor=COLOR_HEADER,
        fontName='Helvetica-Bold', spaceAfter=4)))
    story.append(tbl_resumen)

    doc.build(story)
