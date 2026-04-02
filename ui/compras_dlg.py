# -*- coding: utf-8 -*-
"""
Módulo de Compras
Maneja el registro de compras a proveedores
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
try:
    from modules.stock import registrar_entrada_movimiento as _reg_entrada
except ImportError:
    _reg_entrada = None
from datetime import datetime
from ui.utils import centrar_ventana as _centrar


class VentanaCompra:
    """Ventana para registrar compras"""
    
    def __init__(self, parent, conn, cursor, modo='nueva', compra_id=None, on_guardado=None):
        self.parent = parent
        self.conn = conn
        self.cursor = cursor
        self.modo = modo
        self.compra_id = compra_id
        self.on_guardado = on_guardado
        
        # Lista de productos en la compra
        self.productos_compra = []
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Nueva Compra" if modo == 'nueva' else "Editar Compra")
        self.ventana.geometry("1000x650")
        self.ventana.minsize(920, 570)
        self.ventana.resizable(True, True)
        _centrar(self.ventana, self.parent)

        self.crear_interfaz()

        # Hacer modal
        self.ventana.transient(parent)
        self.ventana.grab_set()
        self.ventana.bind('<Escape>', lambda e: self.ventana.destroy())
    
    def crear_interfaz(self):
        """Crea la interfaz de la ventana"""
        
        # Frame superior con información general
        frame_superior = tk.LabelFrame(self.ventana, text="Información de Compra", font=('Arial', 10, 'bold'))
        frame_superior.pack(fill='x', padx=10, pady=10)
        
        # Primera fila - Proveedor
        frame_fila1 = tk.Frame(frame_superior)
        frame_fila1.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_fila1, text="Proveedor:*", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        
        self.combo_proveedor = ttk.Combobox(frame_fila1, width=35, state='readonly', font=('Arial', 10))
        self.combo_proveedor.pack(side='left', padx=5)
        
        tk.Button(
            frame_fila1,
            text="➕ Nuevo Proveedor",
            command=self.nuevo_proveedor,
            bg='#27ae60',
            fg='white',
            font=('Arial', 9),
            cursor='hand2'
        ).pack(side='left', padx=5)
        
        # Cargar proveedores
        self.cargar_proveedores()
        
        # Segunda fila - Fecha y Método de Pago
        frame_fila2 = tk.Frame(frame_superior)
        frame_fila2.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_fila2, text="Fecha y Hora:*", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        self.entry_fecha = tk.Entry(frame_fila2, width=18, font=('Arial', 10))
        self.entry_fecha.pack(side='left', padx=5)
        self.entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d %H:%M'))
        
        tk.Label(frame_fila2, text="Método de Pago:*", font=('Arial', 10, 'bold')).pack(side='left', padx=(20, 5))
        self.combo_metodo_pago = ttk.Combobox(frame_fila2, width=20, state='readonly', font=('Arial', 10))
        self.combo_metodo_pago.pack(side='left', padx=5)
        
        # Cargar métodos de pago
        self.cargar_metodos_pago()
        
        # Tercera fila - Referencia de ticket
        frame_fila3 = tk.Frame(frame_superior)
        frame_fila3.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_fila3, text="Referencia Ticket:", font=('Arial', 10)).pack(side='left', padx=5)
        self.entry_ticket = tk.Entry(frame_fila3, width=30, font=('Arial', 10))
        self.entry_ticket.pack(side='left', padx=5)
        
        # Frame de productos
        frame_productos = tk.LabelFrame(self.ventana, text="Productos Comprados", font=('Arial', 10, 'bold'))
        frame_productos.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Botones para productos
        frame_btn_prod = tk.Frame(frame_productos)
        frame_btn_prod.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_btn_prod,
            text="➕ Agregar Producto",
            command=self.agregar_producto,
            bg='#3498db',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_btn_prod,
            text="🗑️ Quitar",
            command=self.quitar_producto,
            bg='#e74c3c',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='left', padx=5)
        
        # Tabla de productos
        frame_tabla = tk.Frame(frame_productos)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.tree_productos = ttk.Treeview(
            frame_tabla,
            columns=('Código', 'Producto', 'Cantidad', 'Costo Unit.', 'Total'),
            show='headings',
            height=8
        )
        
        self.tree_productos.heading('Código', text='Código')
        self.tree_productos.heading('Producto', text='Producto')
        self.tree_productos.heading('Cantidad', text='Cantidad')
        self.tree_productos.heading('Costo Unit.', text='Costo Unit.')
        self.tree_productos.heading('Total', text='Total')
        
        self.tree_productos.column('Código', width=80)
        self.tree_productos.column('Producto', width=300)
        self.tree_productos.column('Cantidad', width=100)
        self.tree_productos.column('Costo Unit.', width=120)
        self.tree_productos.column('Total', width=120)
        
        scroll_y = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree_productos.yview)
        self.tree_productos.configure(yscrollcommand=scroll_y.set)
        
        self.tree_productos.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        
        # Frame de totales
        frame_totales = tk.Frame(frame_productos, bg='#f1f5f9')
        frame_totales.pack(fill='x', padx=10, pady=10)
        
        frame_total = tk.Frame(frame_totales, bg='#f1f5f9')
        frame_total.pack(fill='x', pady=2)
        tk.Label(frame_total, text="TOTAL:", font=('Arial', 13, 'bold'), bg='#f1f5f9').pack(side='right', padx=5)
        self.label_total = tk.Label(frame_total, text="$0.00", font=('Arial', 13, 'bold'), fg='#e74c3c', bg='#f1f5f9')
        self.label_total.pack(side='right', padx=5)
        
        # Notas
        frame_notas = tk.Frame(self.ventana)
        frame_notas.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_notas, text="Notas:", font=('Arial', 10)).pack(anchor='w')
        self.text_notas = tk.Text(frame_notas, height=2, font=('Arial', 9))
        self.text_notas.pack(fill='x')
        
        # Botones finales
        frame_botones = tk.Frame(self.ventana)
        frame_botones.pack(fill='x', padx=10, pady=10)
        
        tk.Button(
            frame_botones,
            text="💾 Registrar Compra",
            command=self.guardar_compra,
            bg='#27ae60',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=20,
            pady=10
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            command=self.ventana.destroy,
            bg='#6b7280',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=20,
            pady=10
        ).pack(side='left', padx=5)
    
    def cargar_proveedores(self):
        """Carga proveedores en el combobox"""
        self.cursor.execute("SELECT id, nombre FROM proveedores ORDER BY nombre")
        self.proveedores = {}
        nombres = []
        
        for prov_id, nombre in self.cursor.fetchall():
            nombres.append(nombre)
            self.proveedores[nombre] = prov_id
        
        self.combo_proveedor['values'] = nombres
    
    def cargar_metodos_pago(self):
        """Carga métodos de pago en el combobox"""
        self.cursor.execute("SELECT id, nombre FROM metodos_pago WHERE activo = 1 ORDER BY nombre")
        self.metodos_pago = {}
        nombres = []
        
        for metodo_id, nombre in self.cursor.fetchall():
            nombres.append(nombre)
            self.metodos_pago[nombre] = metodo_id
        
        self.combo_metodo_pago['values'] = nombres
        if nombres:
            self.combo_metodo_pago.current(0)
    
    def nuevo_proveedor(self):
        """Crea un nuevo proveedor rápidamente"""
        from tkinter import simpledialog
        
        ventana = tk.Toplevel(self.ventana)
        ventana.title("Nuevo Proveedor")
        ventana.geometry("400x200")
        ventana.minsize(340, 200)
        ventana.resizable(True, True)
        _centrar(ventana, self.parent)
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text="Nombre del Proveedor:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        entry_nombre = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_nombre.grid(row=0, column=1, pady=5)
        entry_nombre.focus()
        
        tk.Label(frame, text="Contacto:", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5)
        entry_contacto = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_contacto.grid(row=1, column=1, pady=5)
        
        tk.Label(frame, text="Teléfono:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        entry_telefono = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_telefono.grid(row=2, column=1, pady=5)
        
        def guardar():
            nombre = entry_nombre.get().strip()
            if not nombre:
                messagebox.showwarning("Advertencia", "El nombre es obligatorio", parent=ventana)
                return
            
            try:
                self.cursor.execute("""
                    INSERT INTO proveedores (nombre, contacto, telefono)
                    VALUES (?, ?, ?)
                """, (nombre, entry_contacto.get().strip(), entry_telefono.get().strip()))
                
                self.conn.commit()
                messagebox.showinfo("Éxito", "Proveedor registrado", parent=ventana)
                self.cargar_proveedores()
                self.combo_proveedor.set(nombre)
                ventana.destroy()
                
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{str(e)}", parent=ventana)
        
        frame_btn = tk.Frame(frame)
        frame_btn.grid(row=3, column=0, columnspan=2, pady=15)
        
        tk.Button(frame_btn, text="💾 Guardar", command=guardar, bg='#27ae60', fg='white',
                 font=('Arial', 10, 'bold'), cursor='hand2', padx=15, pady=5).pack(side='left', padx=5)
        tk.Button(frame_btn, text="❌ Cancelar", command=ventana.destroy, bg='#6b7280', fg='white',
                 font=('Arial', 10, 'bold'), cursor='hand2', padx=15, pady=5).pack(side='left', padx=5)
        
        ventana.transient(self.ventana)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def agregar_producto(self):
        """Agrega un producto a la compra"""
        ventana = tk.Toplevel(self.ventana)
        ventana.title("Seleccionar Producto")
        ventana.geometry("800x500")
        ventana.minsize(720, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.parent)
        
        # Frame de búsqueda
        frame_busqueda = tk.Frame(ventana)
        frame_busqueda.pack(fill='x', padx=10, pady=10)
        
        tk.Label(frame_busqueda, text="Buscar:", font=('Arial', 10)).pack(side='left', padx=5)
        entry_buscar = tk.Entry(frame_busqueda, width=40, font=('Arial', 10))
        entry_buscar.pack(side='left', padx=5)
        
        # Tabla de productos
        frame_tabla = tk.Frame(ventana)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=5)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Nombre', 'Precio Base'),
            show='headings',
            selectmode='browse'
        )
        
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Nombre', text='Nombre')
        tree.heading('Precio Base', text='Precio Base')
        
        tree.column('ID', width=50)
        tree.column('Código', width=100)
        tree.column('Nombre', width=400)
        tree.column('Precio Base', width=100)
        
        scroll = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        def cargar_productos():
            tree.delete(*tree.get_children())
            
            buscar = entry_buscar.get().strip()
            if buscar:
                self.cursor.execute("""
                    SELECT id, codigo, nombre, precio_base
                    FROM productos
                    WHERE codigo LIKE ? OR nombre LIKE ?
                    ORDER BY nombre
                """, (f'%{buscar}%', f'%{buscar}%'))
            else:
                self.cursor.execute("""
                    SELECT id, codigo, nombre, precio_base
                    FROM productos
                    ORDER BY nombre
                """)
            
            for row in self.cursor.fetchall():
                row_list = list(row)
                row_list[3] = f"${row[3]:,.2f}"
                tree.insert('', 'end', values=row_list)
        
        entry_buscar.bind('<KeyRelease>', lambda e: cargar_productos())
        cargar_productos()
        
        # Frame de cantidad y costo
        frame_datos = tk.Frame(ventana)
        frame_datos.pack(fill='x', padx=10, pady=10)
        
        tk.Label(frame_datos, text="Cantidad:*", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        entry_cantidad = tk.Entry(frame_datos, width=10, font=('Arial', 10))
        entry_cantidad.pack(side='left', padx=5)
        entry_cantidad.insert(0, "1")
        
        tk.Label(frame_datos, text="Costo Unitario:*", font=('Arial', 10, 'bold')).pack(side='left', padx=(20, 5))
        entry_costo = tk.Entry(frame_datos, width=15, font=('Arial', 10))
        entry_costo.pack(side='left', padx=5)
        
        # Botones
        frame_botones = tk.Frame(ventana)
        frame_botones.pack(fill='x', padx=10, pady=10)
        
        def agregar():
            seleccion = tree.selection()
            if not seleccion:
                messagebox.showwarning("Advertencia", "Selecciona un producto", parent=ventana)
                return
            
            try:
                cantidad = float(entry_cantidad.get())
                costo = float(entry_costo.get().replace(',', '').replace('$', ''))
                
                if cantidad <= 0 or costo < 0:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("Advertencia", "Cantidad y costo deben ser válidos", parent=ventana)
                return
            
            item = tree.item(seleccion[0])
            producto_id = item['values'][0]
            
            self.cursor.execute("SELECT codigo, nombre FROM productos WHERE id = ?", (producto_id,))
            codigo, nombre = self.cursor.fetchone()
            
            total = cantidad * costo
            
            self.productos_compra.append({
                'producto_id': producto_id,
                'codigo': codigo,
                'nombre': nombre,
                'cantidad': cantidad,
                'costo_unitario': costo,
                'total': total
            })
            
            self.actualizar_tabla_productos()
            ventana.destroy()
        
        tk.Button(
            frame_botones,
            text="➕ Agregar",
            command=agregar,
            bg='#27ae60',
            fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2',
            padx=15,
            pady=8
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="❌ Cancelar",
            command=ventana.destroy,
            bg='#6b7280',
            fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2',
            padx=15,
            pady=8
        ).pack(side='left', padx=5)
        
        ventana.transient(self.ventana)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def quitar_producto(self):
        """Quita un producto de la compra"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona un producto para quitar")
            return
        
        item = self.tree_productos.item(seleccion[0])
        codigo = item['values'][0]
        
        for i, prod in enumerate(self.productos_compra):
            if prod['codigo'] == codigo:
                del self.productos_compra[i]
                break
        
        self.actualizar_tabla_productos()
    
    def actualizar_tabla_productos(self):
        """Actualiza la tabla de productos y el total"""
        self.tree_productos.delete(*self.tree_productos.get_children())
        
        total_general = 0
        
        for prod in self.productos_compra:
            self.tree_productos.insert('', 'end', values=(
                prod['codigo'],
                prod['nombre'],
                f"{prod['cantidad']:.2f}",
                f"${prod['costo_unitario']:,.2f}",
                f"${prod['total']:,.2f}"
            ))
            
            total_general += prod['total']
        
        self.label_total.config(text=f"${total_general:,.2f}")
    
    def guardar_compra(self):
        """Guarda la compra en la base de datos"""
        
        # Validaciones
        if not self.combo_proveedor.get():
            messagebox.showwarning("Advertencia", "Selecciona un proveedor")
            return
        
        if not self.productos_compra:
            messagebox.showwarning("Advertencia", "Agrega al menos un producto")
            return
        
        try:
            # Generar folio
            fecha_actual = datetime.now()
            año = fecha_actual.strftime('%Y')

            self.cursor.execute("""
                SELECT folio FROM compras
                WHERE folio LIKE ?
                ORDER BY folio DESC
                LIMIT 1
            """, (f"COMP-{año}-%",))

            row = self.cursor.fetchone()
            if row:
                try:
                    ultimo = int(row[0].split('-')[-1])
                except (ValueError, IndexError):
                    ultimo = 0
            else:
                ultimo = 0

            consecutivo = ultimo + 1
            while True:
                folio = f"COMP-{año}-{consecutivo:04d}"
                self.cursor.execute("SELECT 1 FROM compras WHERE folio = ?", (folio,))
                if not self.cursor.fetchone():
                    break
                consecutivo += 1
            
            # Calcular total
            total = sum(p['total'] for p in self.productos_compra)
            
            # Obtener IDs
            proveedor_id = self.proveedores[self.combo_proveedor.get()]
            metodo_pago_id = self.metodos_pago[self.combo_metodo_pago.get()]
            
            # Fecha
            fecha_compra = self.entry_fecha.get().strip()
            ticket_ref = self.entry_ticket.get().strip()
            notas = self.text_notas.get('1.0', 'end-1c').strip()
            
            # Insertar compra
            self.cursor.execute("""
                INSERT INTO compras 
                (folio, proveedor_id, fecha_compra, total, metodo_pago_id, notas, ticket_referencia)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (folio, proveedor_id, fecha_compra, total, metodo_pago_id, notas, ticket_ref))
            
            compra_id = self.cursor.lastrowid

            # Lista de productos cuyo costo superó el precio_base
            subidas = []

            # Insertar detalle y actualizar stock
            for prod in self.productos_compra:
                self.cursor.execute("""
                    INSERT INTO compra_detalle
                    (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                    VALUES (?, ?, ?, ?, ?)
                """, (compra_id, prod['producto_id'], prod['cantidad'],
                      prod['costo_unitario'], prod['total']))
                
                # Obtener stock antes de actualizar
                self.cursor.execute("SELECT stock_actual FROM productos WHERE id = ?",
                                    (prod['producto_id'],))
                stock_antes_row = self.cursor.fetchone()
                stock_antes = stock_antes_row[0] if stock_antes_row else 0

                # Actualizar stock del producto
                self.cursor.execute("""
                    UPDATE productos
                    SET stock_actual = stock_actual + ?
                    WHERE id = ?
                """, (prod['cantidad'], prod['producto_id']))

                # ── Verificar si costo_unitario supera precio_base ────────────
                self.cursor.execute(
                    "SELECT precio_base, nombre FROM productos WHERE id=?",
                    (prod['producto_id'],))
                pb_row = self.cursor.fetchone()
                if pb_row:
                    precio_base_actual, nombre_prod = pb_row
                    if prod['costo_unitario'] > (precio_base_actual or 0):
                        subidas.append({
                            'producto_id': prod['producto_id'],
                            'nombre':      nombre_prod,
                            'precio_base': precio_base_actual or 0,
                            'nuevo_costo': prod['costo_unitario'],
                        })

                # Registrar movimiento de entrada en historial de stock
                if _reg_entrada:
                    try:
                        _reg_entrada(self.cursor, self.conn,
                                     prod['producto_id'], prod['cantidad'],
                                     stock_antes, folio)
                    except Exception:
                        pass
            
            self.conn.commit()

            # ── Preguntar si actualizar precio_base para productos que subieron ─
            if subidas:
                detalle_txt = '\n'.join(
                    f'  • {s["nombre"]}:  ${s["precio_base"]:,.2f}  →  ${s["nuevo_costo"]:,.2f}'
                    for s in subidas
                )
                respuesta = messagebox.askyesno(
                    '📈 Precios de compra más altos',
                    f'Los siguientes productos se compraron más caro que su precio_base actual:\n\n'
                    f'{detalle_txt}\n\n'
                    f'¿Deseas actualizar el precio_base (costo de referencia) con los nuevos valores?\n\n'
                    f'Esto afectará el costo estimado de cotizaciones futuras.',
                    icon='warning'
                )
                if respuesta:
                    from datetime import date as _date
                    hoy = _date.today().isoformat()
                    for s in subidas:
                        self.cursor.execute("""
                            UPDATE productos
                            SET precio_base       = ?,
                                precio_base_fecha = ?
                            WHERE id = ?
                        """, (s['nuevo_costo'], hoy, s['producto_id']))
                        # Registrar en historial de precios
                        self.cursor.execute("""
                            INSERT INTO producto_precio_historial
                                (producto_id, precio, fecha, motivo, fuente)
                            VALUES (?, ?, ?, ?, 'compra')
                        """, (s['producto_id'], s['nuevo_costo'], hoy,
                              f"Actualizado desde compra — costo supera precio base anterior (${s['precio_base']:,.2f})"))
                    self.conn.commit()
                    messagebox.showinfo(
                        'Precio base actualizado',
                        f'{len(subidas)} producto(s) actualizados.\n'
                        f'Las nuevas cotizaciones usarán el nuevo costo como referencia.'
                    )

            messagebox.showinfo(
                "Éxito",
                f"Compra registrada correctamente\n\nFolio: {folio}\nTotal: ${total:,.2f}\n\nStock actualizado"
            )
            
            self.ventana.destroy()
            if self.on_guardado:
                try:
                    self.on_guardado()
                except Exception:
                    pass
            
        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror("Error", f"No se pudo guardar la compra:\n{str(e)}")
