# -*- coding: utf-8 -*-
"""
ui/catalogos_compras_mixin.py
Mixin: gestión de compras.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from modules.compras import VentanaCompra
from ui.utils import centrar_ventana as _centrar


class _CatalogosComprasMixin:
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

