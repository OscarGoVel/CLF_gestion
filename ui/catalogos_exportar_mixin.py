# -*- coding: utf-8 -*-
"""
ui/catalogos_exportar_mixin.py
Mixin: exportación a CSV.
"""

from tkinter import messagebox


class _CatalogosExportarMixin:
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

