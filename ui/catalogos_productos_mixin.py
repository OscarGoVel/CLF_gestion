# -*- coding: utf-8 -*-
"""
ui/catalogos_productos_mixin.py
Mixin: métodos de gestión de productos, precios e inventario.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import os
from datetime import datetime
from ui.utils import centrar_ventana as _centrar, campo_error as _campo_error, campo_ok as _campo_ok


class _CatalogosProductosMixin:
    def cargar_productos(self):
        """Carga la lista de productos en la tabla"""
        # Limpiar tabla
        for item in self.tree_productos.get_children():
            self.tree_productos.delete(item)
        
        # Obtener término de búsqueda
        buscar = self.entry_buscar_producto.get().strip().lower()

        # Consultar base de datos
        if buscar:
            self.cursor.execute("""
                SELECT p.id, p.codigo, p.nombre, c.nombre, s.nombre, p.unidad_medida,
                       p.precio_base, p.aplica_iva, p.precio_venta, p.stock_actual, p.stock_minimo,
                       p.clave_sat
                FROM productos p
                LEFT JOIN categorias c ON p.categoria_id = c.id
                LEFT JOIN subcategorias s ON p.subcategoria_id = s.id
                WHERE LOWER(p.codigo) LIKE ? OR LOWER(p.nombre) LIKE ?
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
        """Filtra la tabla mostrando solo productos usados recientemente con precio desactualizado."""
        from datetime import date as _d
        hoy = _d.today()

        # Calcular fecha_desde según el período seleccionado
        periodo = self._precio_revision_periodo.get() \
            if hasattr(self, '_precio_revision_periodo') else 'Últimos 6 meses'
        if periodo == 'Últimos 3 meses':
            fecha_desde = hoy.replace(day=1)
            for _ in range(3):
                fecha_desde = (fecha_desde.replace(day=1) -
                               __import__('datetime').timedelta(days=1)).replace(day=1)
            fecha_desde = fecha_desde.isoformat()
        elif periodo == 'Últimos 12 meses':
            fecha_desde = hoy.replace(year=hoy.year - 1).isoformat()
        elif periodo == 'Todo el tiempo':
            fecha_desde = '2000-01-01'
        else:  # Últimos 6 meses (default)
            m = hoy.month - 6
            y = hoy.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            fecha_desde = hoy.replace(year=y, month=m, day=1).isoformat()

        self.tree_productos.delete(*self.tree_productos.get_children())

        # Solo productos que aparecen en cotizaciones no canceladas dentro del período
        self.cursor.execute("""
            SELECT p.id, p.codigo, p.nombre, c.nombre, s.nombre, p.unidad_medida,
                   p.precio_base, p.aplica_iva, p.precio_venta, p.stock_actual,
                   p.stock_minimo, p.clave_sat, p.precio_base_fecha
            FROM productos p
            LEFT JOIN categorias c    ON p.categoria_id    = c.id
            LEFT JOIN subcategorias s ON p.subcategoria_id = s.id
            WHERE p.id IN (
                SELECT DISTINCT cd.producto_id
                FROM cotizacion_detalle cd
                JOIN cotizaciones cot ON cot.id = cd.cotizacion_id
                WHERE cot.estado NOT IN ('Cancelada')
                  AND cot.fecha >= ?
            )
            ORDER BY p.nombre
        """, (fecha_desde,))
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

        # Flag: True mientras el código fue puesto por auto-generación (no por el usuario)
        _sku_auto = [modo == 'nuevo']

        def _generar_sku():
            """Genera y rellena el SKU solo si el campo está vacío o fue auto-generado."""
            if modo != 'nuevo' or not _sku_auto[0]:
                return
            cat_sel = combo_categoria.get()
            sub_sel = combo_subcat.get()
            if not cat_sel:
                return
            prefix = cat_sel[:3].upper()
            prefix += sub_sel[:3].upper() if sub_sel else 'GEN'
            self.cursor.execute(
                "SELECT codigo FROM productos WHERE codigo LIKE ? ORDER BY codigo DESC LIMIT 1",
                (f'{prefix}%',))
            ultimo = self.cursor.fetchone()
            if ultimo:
                try:
                    num = int(ultimo[0][len(prefix):]) + 1
                except Exception:
                    num = 1
            else:
                num = 1
            nuevo_sku = f"{prefix}{num:04d}"
            entry_codigo.delete(0, 'end')
            entry_codigo.insert(0, nuevo_sku)

        def _on_codigo_edit(e=None):
            """Si el usuario escribe manualmente, desactiva la auto-generación."""
            _sku_auto[0] = False

        entry_codigo.bind('<Key>', _on_codigo_edit)

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
                    if rs and rs[0] in subs:
                        combo_subcat.set(rs[0])
                    else:
                        combo_subcat.set('')
                else:
                    combo_subcat.set('')
            else:
                combo_subcat['values'] = []
                combo_subcat.set('')
            _generar_sku()

        def _on_subcat_change(e=None):
            _generar_sku()

        combo_categoria.bind('<<ComboboxSelected>>', _on_cat_change)
        combo_subcat.bind('<<ComboboxSelected>>', _on_subcat_change)
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

        # Período de uso reciente (mismo que el selector del toolbar)
        periodo = self._precio_revision_periodo.get() \
            if hasattr(self, '_precio_revision_periodo') else 'Últimos 6 meses'
        if periodo == 'Últimos 3 meses':
            fd = hoy.replace(day=1)
            for _ in range(3):
                fd = (fd.replace(day=1) -
                      __import__('datetime').timedelta(days=1)).replace(day=1)
            fecha_desde = fd.isoformat()
        elif periodo == 'Últimos 12 meses':
            fecha_desde = hoy.replace(year=hoy.year - 1).isoformat()
        elif periodo == 'Todo el tiempo':
            fecha_desde = '2000-01-01'
        else:
            m = hoy.month - 6
            y = hoy.year + (m - 1) // 12
            m = ((m - 1) % 12) + 1
            fecha_desde = hoy.replace(year=y, month=m, day=1).isoformat()

        # Solo productos usados en el período, con su última fecha de cotización
        self.cursor.execute("""
            SELECT p.id, p.codigo, p.nombre, p.precio_base, c.nombre AS cat,
                   MAX(cot.fecha) AS ultima_cot
            FROM productos p
            LEFT JOIN categorias c ON c.id = p.categoria_id
            JOIN cotizacion_detalle cd  ON cd.producto_id = p.id
            JOIN cotizaciones cot       ON cot.id = cd.cotizacion_id
            WHERE cot.estado NOT IN ('Cancelada')
              AND cot.fecha >= ?
            GROUP BY p.id
            ORDER BY p.nombre
        """, (fecha_desde,))
        todos = self.cursor.fetchall()

        pendientes = []  # (pid, codigo, nombre, precio_actual, cat, dias, ultima_cot)
        for pid, codigo, nombre, precio_base, cat, ultima_cot in todos:
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
                                   precio_base or 0, cat or '', dias,
                                   ultima_cot or ''))

        if not pendientes:
            messagebox.showinfo('✅ Precios al día',
                f'Todos los productos usados en "{periodo}" tienen precios actualizados.',
                parent=self.sistema.root)
            self.cargar_productos()
            return

        # ── Ventana ───────────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f'Revisión de precios — {len(pendientes)} producto(s) ({periodo})')
        win.geometry('940x540')
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
        tk.Label(hdr, text=f'{len(pendientes)} productos requieren revisión  ·  {periodo}',
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
        for txt, w in [('Producto', 260), ('Cat.', 80), ('Precio actual', 100),
                        ('Nuevo precio', 100), ('Días sin act.', 70),
                        ('Última cot.', 85), ('', 80)]:
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
        for i, (pid, codigo, nombre, precio_actual, cat, dias, ultima_cot) in enumerate(pendientes):
            bg = '#ffffff' if i % 2 == 0 else '#f8fafc'
            row = tk.Frame(inner, bg=bg)
            row.pack(fill='x')

            dias_color = '#dc2626' if dias > 60 else '#d97706'
            nombre_short = f'{nombre[:28]}…' if len(nombre) > 28 else nombre
            # Formatear última cotización como dd/mm/yy
            try:
                from datetime import date as _d2
                ult_cot_fmt = _d2.fromisoformat(str(ultima_cot)[:10]).strftime('%d/%m/%y')
            except Exception:
                ult_cot_fmt = '—'

            tk.Label(row, text=nombre_short, font=('Arial', 9), bg=bg,
                     fg='#374151', anchor='w', padx=6).pack(side='left', fill='x', expand=True)
            tk.Label(row, text=(cat or '')[:10], font=('Arial', 8), bg=bg,
                     fg='#6b7280', width=9, anchor='w').pack(side='left')
            tk.Label(row, text=f'${precio_actual:,.2f}', font=('Arial', 9), bg=bg,
                     fg='#374151', width=10, anchor='e').pack(side='left', padx=(0,4))
            e = tk.Entry(row, font=('Arial', 9), width=10,
                         relief='solid', bd=1, bg='white')
            e.insert(0, f'{precio_actual:.2f}')
            e.pack(side='left', padx=4)
            tk.Label(row, text=f'{dias}d', font=('Arial', 8, 'bold'), bg=bg,
                     fg=dias_color, width=6, anchor='w').pack(side='left')
            tk.Label(row, text=ult_cot_fmt, font=('Arial', 8), bg=bg,
                     fg='#6b7280', width=8, anchor='w').pack(side='left')
            lbl_e = tk.Label(row, text='—', font=('Arial', 9), bg=bg,
                             fg='#9ca3af', width=4)
            lbl_e.pack(side='left', padx=2)
            btn = tk.Button(row, text='✓',
                            font=('Arial', 8, 'bold'), bg='#0f7b5e', fg='white',
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
                 "Usa la columna PDF (☑/☐) para elegir qué productos se imprimen.",
            font=('Arial', 9), bg='#16a085', fg='#d5f5ef'
        ).pack()

        # ── Tabla editable ─────────────────────────────────────────────────
        frame_tabla = tk.Frame(ventana)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=8)

        cols = ('_key', 'PDF', 'Cotización', 'O.C.', 'Producto', 'Unidad',
                'Stock\nActual', 'Pendiente\nEntregar', 'Faltante\nStock',
                'A Comprar\n(editable)', 'Costo Máx.', 'Subtotal Est.',
                'Proveedor Principal')
        tree = ttk.Treeview(frame_tabla, columns=cols, show='headings', selectmode='browse')

        anchos = [0, 42, 110, 100, 220, 60, 75, 90, 80, 100, 95, 95, 140]
        for col, ancho in zip(cols, anchos):
            tree.heading(col, text=col)
            tree.column(col, width=ancho, minwidth=ancho)
        tree.column('_key', stretch=False, width=0)
        tree.column('PDF',  stretch=False, anchor='center')

        scroll_y = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        scroll_x = ttk.Scrollbar(frame_tabla, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        frame_tabla.grid_rowconfigure(0, weight=1)
        frame_tabla.grid_columnconfigure(0, weight=1)

        # Colores por estado de stock / inclusión en PDF
        tree.tag_configure('faltante',  background='#fde8e8')
        tree.tag_configure('ok',        background='#eafaf1')
        tree.tag_configure('excluido',  background='#e5e7eb', foreground='#9ca3af')

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
                '☑',
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
                'incluir':   True,
                '_tag_base': tag,
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

        lbl_conteo = tk.Label(
            frame_totales,
            text="",
            font=('Arial', 9), bg='#f1f5f9', fg='#6b7280'
        )
        lbl_conteo.pack(side='right', padx=15)

        def recalcular_total():
            incluidos = [d for d in datos_filas.values() if d['incluir'] and d['a_comprar'] > 0]
            total = sum(d['a_comprar'] * d['costo_max'] for d in incluidos)
            lbl_total_est.config(text=f"Total estimado: ${total:,.2f}")
            total_filas = len(datos_filas)
            inc = sum(1 for d in datos_filas.values() if d['incluir'])
            lbl_conteo.config(text=f"{inc} de {total_filas} productos en PDF")

        recalcular_total()

        # ── Toggle incluir/excluir al hacer clic en columna PDF ────────────
        def _toggle_incluir(event):
            col = tree.identify_column(event.x)
            iid = tree.identify_row(event.y)
            if not iid or col != '#2':   # '#2' = columna PDF
                return
            d = datos_filas[iid]
            d['incluir'] = not d['incluir']
            vals = list(tree.item(iid)['values'])
            vals[1] = '☑' if d['incluir'] else '☐'
            tag = d['_tag_base'] if d['incluir'] else 'excluido'
            tree.item(iid, values=vals, tags=(tag,))
            recalcular_total()

        tree.bind('<ButtonRelease-1>', _toggle_incluir)

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
            vals[9]  = f"{nueva:.2f}"
            vals[11] = f"${subtotal:,.2f}"
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

        tk.Button(
            frame_btn, text="☑ Todos",
            command=lambda: _marcar_todos(True),
            bg='#374151', fg='white', font=('Arial', 9, 'bold'),
            cursor='hand2', padx=10, pady=6
        ).pack(side='left', padx=5)

        tk.Button(
            frame_btn, text="☐ Ninguno",
            command=lambda: _marcar_todos(False),
            bg='#374151', fg='white', font=('Arial', 9, 'bold'),
            cursor='hand2', padx=10, pady=6
        ).pack(side='left', padx=5)

        def _restablecer_todo():
            for iid, d in datos_filas.items():
                d['a_comprar'] = d['faltante']
                vals = list(tree.item(iid)['values'])
                vals[9]  = f"{d['faltante']:.2f}"
                vals[11] = f"${d['faltante'] * d['costo_max']:,.2f}"
                tree.item(iid, values=vals)
            recalcular_total()

        def _marcar_todos(incluir: bool):
            for iid, d in datos_filas.items():
                d['incluir'] = incluir
                vals = list(tree.item(iid)['values'])
                vals[1] = '☑' if incluir else '☐'
                tag = d['_tag_base'] if incluir else 'excluido'
                tree.item(iid, values=vals, tags=(tag,))
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
                d for d in datos_filas.values() if d['incluir'] and d['a_comprar'] > 0
            ]
            if not productos_pdf:
                messagebox.showwarning(
                    "Sin productos",
                    "No hay productos para exportar.\n\n"
                    "Verifica que:\n"
                    "• Al menos un producto tenga ☑ marcado en la columna PDF.\n"
                    "• La cantidad a comprar sea mayor a 0.",
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

