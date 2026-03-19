# -*- coding: utf-8 -*-
"""
Módulo de Cotizaciones
Maneja la creación y edición de cotizaciones
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime


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


class VentanaCotizacion:
    """Ventana para crear o editar cotizaciones"""
    
    def __init__(self, parent, conn, cursor, utilidad, modo='nueva', cotizacion_id=None,
                 on_ir_catalogo=None):
        self.parent = parent
        self.conn = conn
        self.cursor = cursor
        self.UTILIDAD = utilidad
        self.modo = modo
        self.cotizacion_id = cotizacion_id
        self.on_ir_catalogo = on_ir_catalogo  # callback para navegar al catálogo
        
        # Lista de productos agregados a la cotización
        self.productos_cotizacion = []
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Nueva Cotización" if modo == 'nueva' else "Editar Cotización")
        self.ventana.geometry("1000x700")
        self.ventana.minsize(920, 620)
        self.ventana.resizable(True, True)
        _centrar(self.ventana, self.parent)
        
        self.crear_interfaz()
        
        # Cargar datos si está en modo editar
        if self.modo == 'editar' and self.cotizacion_id:
            self.cargar_datos_cotizacion()
        
        # Hacer modal
        self.ventana.transient(parent)
        self.ventana.grab_set()
    
    def crear_interfaz(self):
        """Crea la interfaz de la ventana"""
        
        # Frame superior con información general
        frame_superior = tk.LabelFrame(self.ventana, text="Información General", font=('Arial', 10, 'bold'))
        frame_superior.pack(fill='x', padx=10, pady=10)
        
        # Primera fila
        frame_fila1 = tk.Frame(frame_superior)
        frame_fila1.pack(fill='x', padx=10, pady=5)
        
        # Folio
        tk.Label(frame_fila1, text="Folio:", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        self.label_folio = tk.Label(frame_fila1, text="Se generará automáticamente", font=('Arial', 10), fg='gray')
        self.label_folio.pack(side='left', padx=5)
        
        # Fecha
        tk.Label(frame_fila1, text="Fecha:", font=('Arial', 10, 'bold')).pack(side='left', padx=(20, 5))
        self.label_fecha = tk.Label(frame_fila1, text=datetime.now().strftime('%Y-%m-%d'), font=('Arial', 10))
        self.label_fecha.pack(side='left', padx=5)
        
        # Segunda fila - Cliente
        frame_fila2 = tk.Frame(frame_superior)
        frame_fila2.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_fila2, text="Cliente:*", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        
        # Combo de clientes
        self.combo_cliente = ttk.Combobox(frame_fila2, width=40, state='readonly', font=('Arial', 10))
        self.combo_cliente.pack(side='left', padx=5)
        self.combo_cliente.bind('<<ComboboxSelected>>', self.cliente_seleccionado)
        
        tk.Button(
            frame_fila2,
            text="➕ Nuevo Cliente",
            command=self.nuevo_cliente_rapido,
            bg='#27ae60',
            fg='white',
            font=('Arial', 9),
            cursor='hand2'
        ).pack(side='left', padx=5)
        
        # Cargar clientes
        self.cargar_clientes()
        
        # Información del cliente seleccionado
        self.label_info_cliente = tk.Label(frame_fila2, text="", font=('Arial', 9), fg='#6b7280')
        self.label_info_cliente.pack(side='left', padx=10)
        
        # Frame de productos
        frame_productos = tk.LabelFrame(self.ventana, text="Productos", font=('Arial', 10, 'bold'))
        frame_productos.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Botones para agregar productos
        frame_btn_productos = tk.Frame(frame_productos)
        frame_btn_productos.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_btn_productos,
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
            frame_btn_productos,
            text="✏️ Editar Cantidad",
            command=self.editar_cantidad_producto,
            bg='#f39c12',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_btn_productos,
            text="🗑️ Quitar Seleccionado",
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
            columns=('Código', 'Producto', 'Cantidad', 'Precio Unit.', 'Subtotal', 'IVA', 'Total', 'Stock'),
            show='headings',
            height=8
        )
        
        # Configurar columnas
        self.tree_productos.heading('Código', text='Código')
        self.tree_productos.heading('Producto', text='Producto')
        self.tree_productos.heading('Cantidad', text='Cantidad')
        self.tree_productos.heading('Precio Unit.', text='Precio Unit.')
        self.tree_productos.heading('Subtotal', text='Subtotal')
        self.tree_productos.heading('IVA', text='IVA')
        self.tree_productos.heading('Total', text='Total')
        self.tree_productos.heading('Stock', text='Stock')
        
        self.tree_productos.column('Código', width=80)
        self.tree_productos.column('Producto', width=200)
        self.tree_productos.column('Cantidad', width=80)
        self.tree_productos.column('Precio Unit.', width=100)
        self.tree_productos.column('Subtotal', width=100)
        self.tree_productos.column('IVA', width=80)
        self.tree_productos.column('Total', width=100)
        self.tree_productos.column('Stock', width=80)
        
        scroll_y = ttk.Scrollbar(frame_tabla, orient='vertical', command=self.tree_productos.yview)
        self.tree_productos.configure(yscrollcommand=scroll_y.set)
        
        self.tree_productos.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        
        # Doble clic para editar producto completo
        self.tree_productos.bind('<Double-1>', lambda e: self.editar_producto_completo())
        
        # Frame de totales
        frame_totales = tk.Frame(frame_productos, bg='#f1f5f9')
        frame_totales.pack(fill='x', padx=10, pady=10)
        
        # Subtotal
        frame_subtotal = tk.Frame(frame_totales, bg='#f1f5f9')
        frame_subtotal.pack(fill='x', pady=2)
        tk.Label(frame_subtotal, text="Subtotal:", font=('Arial', 11, 'bold'), bg='#f1f5f9').pack(side='right', padx=5)
        self.label_subtotal = tk.Label(frame_subtotal, text="$0.00", font=('Arial', 11), bg='#f1f5f9')
        self.label_subtotal.pack(side='right', padx=5)
        
        # IVA
        frame_iva = tk.Frame(frame_totales, bg='#f1f5f9')
        frame_iva.pack(fill='x', pady=2)
        tk.Label(frame_iva, text="IVA:", font=('Arial', 11, 'bold'), bg='#f1f5f9').pack(side='right', padx=5)
        self.label_iva = tk.Label(frame_iva, text="$0.00", font=('Arial', 11), bg='#f1f5f9')
        self.label_iva.pack(side='right', padx=5)
        
        # Total
        frame_total = tk.Frame(frame_totales, bg='#f1f5f9')
        frame_total.pack(fill='x', pady=2)
        tk.Label(frame_total, text="TOTAL:", font=('Arial', 13, 'bold'), bg='#f1f5f9').pack(side='right', padx=5)
        self.label_total = tk.Label(frame_total, text="$0.00", font=('Arial', 13, 'bold'), fg='#27ae60', bg='#f1f5f9')
        self.label_total.pack(side='right', padx=5)
        
        # Frame de notas
        frame_notas = tk.Frame(self.ventana)
        frame_notas.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_notas, text="Notas/Observaciones:", font=('Arial', 10)).pack(anchor='w')
        self.text_notas = tk.Text(frame_notas, height=3, font=('Arial', 9))
        self.text_notas.pack(fill='x')
        
        # Frame de botones finales
        frame_botones = tk.Frame(self.ventana)
        frame_botones.pack(fill='x', padx=10, pady=10)
        
        tk.Button(
            frame_botones,
            text="💾 Guardar Cotización",
            command=self.guardar_cotizacion,
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
    
    def cargar_datos_cotizacion(self):
        """Carga los datos existentes de la cotización para editar"""
        try:
            # Obtener datos de la cotización
            self.cursor.execute("""
                SELECT folio, fecha, cliente_id, notas
                FROM cotizaciones
                WHERE id = ?
            """, (self.cotizacion_id,))
            
            row = self.cursor.fetchone()
            if not row:
                messagebox.showerror("Error", "No se encontró la cotización")
                self.ventana.destroy()
                return
            
            folio, fecha, cliente_id, notas = row
            
            # Cargar folio
            self.label_folio.config(text=folio, fg='black')
            
            # Cargar fecha
            self.label_fecha.config(text=fecha)
            
            # Cargar cliente
            self.cursor.execute("""
                SELECT nombre_comercial, tipo
                FROM clientes
                WHERE id = ?
            """, (cliente_id,))
            
            cliente_row = self.cursor.fetchone()
            if cliente_row:
                nombre, tipo = cliente_row
                display_name = f"{nombre} ({tipo})"
                if display_name in self.clientes:
                    self.combo_cliente.set(display_name)
                    self.cliente_seleccionado()
            
            # Cargar notas
            if notas:
                self.text_notas.delete('1.0', 'end')
                self.text_notas.insert('1.0', notas)
            
            # Cargar productos
            self.cursor.execute("""
                SELECT 
                    cd.producto_id,
                    cd.cantidad,
                    cd.precio_unitario,
                    cd.subtotal,
                    cd.iva,
                    cd.total,
                    cd.tiene_stock,
                    p.codigo,
                    p.nombre,
                    p.stock_actual,
                    p.aplica_iva
                FROM cotizacion_detalle cd
                INNER JOIN productos p ON cd.producto_id = p.id
                WHERE cd.cotizacion_id = ?
                ORDER BY cd.id
            """, (self.cotizacion_id,))
            
            productos = self.cursor.fetchall()
            
            for prod_row in productos:
                (producto_id, cantidad, precio_unitario, subtotal, iva, total, tiene_stock,
                 codigo, nombre, stock_actual, aplica_iva) = prod_row
                
                # Agregar a la lista de productos
                producto = {
                    'producto_id': producto_id,
                    'codigo': codigo,
                    'nombre': nombre,
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'subtotal': subtotal,
                    'iva': iva,
                    'total': total,
                    'tiene_stock': bool(tiene_stock),
                    'stock_disponible': stock_actual,
                    'aplica_iva': bool(aplica_iva)
                }
                
                self.productos_cotizacion.append(producto)
                
                # Agregar a la tabla visual
                self.tree_productos.insert('', 'end', values=(
                    codigo,
                    nombre,
                    f"{cantidad:.2f}",
                    f"${precio_unitario:,.2f}",
                    f"${subtotal:,.2f}",
                    f"${iva:,.2f}",
                    f"${total:,.2f}",
                    "✓" if tiene_stock else "✗"
                ))
            
            # Actualizar totales
            self.actualizar_tabla_productos()
            
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudieron cargar los datos:\n{str(e)}")
            self.ventana.destroy()
    
    def cargar_clientes(self):
        """Carga los clientes en el combobox"""
        self.cursor.execute("SELECT id, nombre_comercial, tipo FROM clientes ORDER BY nombre_comercial")
        self.clientes = {}
        nombres = []
        
        for cliente_id, nombre, tipo in self.cursor.fetchall():
            display_name = f"{nombre} ({tipo})"
            nombres.append(display_name)
            self.clientes[display_name] = {'id': cliente_id, 'nombre': nombre, 'tipo': tipo}
        
        self.combo_cliente['values'] = nombres
    
    def cliente_seleccionado(self, event=None):
        """Evento cuando se selecciona un cliente"""
        cliente_nombre = self.combo_cliente.get()
        if cliente_nombre in self.clientes:
            cliente = self.clientes[cliente_nombre]
            
            # Mostrar información del cliente
            self.cursor.execute("""
                SELECT rfc, contacto, telefono
                FROM clientes WHERE id = ?
            """, (cliente['id'],))
            
            row = self.cursor.fetchone()
            if row:
                rfc, contacto, telefono = row
                info = f"RFC: {rfc or 'N/A'}"
                if contacto:
                    info += f" | Contacto: {contacto}"
                if telefono:
                    info += f" | Tel: {telefono}"
                
                self.label_info_cliente.config(text=info)
            
            # Recalcular precios si ya hay productos
            if self.productos_cotizacion:
                self.recalcular_productos()
    
    def nuevo_cliente_rapido(self):
        """Crea un nuevo cliente de forma rápida"""
        from tkinter import simpledialog
        
        # Ventana simple para cliente rápido
        ventana = tk.Toplevel(self.ventana)
        ventana.title("Nuevo Cliente Rápido")
        ventana.geometry("480x320")
        ventana.minsize(400, 240)
        ventana.resizable(True, True)
        _centrar(ventana, self.parent)
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        # Nombre comercial
        tk.Label(frame, text="Nombre Comercial:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        entry_nombre = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_nombre.grid(row=0, column=1, pady=5)
        entry_nombre.focus()
        
        # Tipo
        tk.Label(frame, text="Tipo:*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        combo_tipo = ttk.Combobox(frame, values=['Gobierno', 'Hotel'], state='readonly', width=27, font=('Arial', 10))
        combo_tipo.grid(row=1, column=1, pady=5)
        combo_tipo.set('Hotel')
        
        # RFC
        tk.Label(frame, text="RFC:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        entry_rfc = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_rfc.grid(row=2, column=1, pady=5)
        
        # Contacto
        tk.Label(frame, text="Contacto:", font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=5)
        entry_contacto = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_contacto.grid(row=3, column=1, pady=5)
        
        # Teléfono
        tk.Label(frame, text="Teléfono:", font=('Arial', 10)).grid(row=4, column=0, sticky='w', pady=5)
        entry_telefono = tk.Entry(frame, width=30, font=('Arial', 10))
        entry_telefono.grid(row=4, column=1, pady=5)
        
        def guardar_rapido():
            nombre = entry_nombre.get().strip()
            tipo = combo_tipo.get()
            
            if not nombre or not tipo:
                messagebox.showwarning("Advertencia", "Nombre y tipo son obligatorios", parent=ventana)
                return
            
            try:
                self.cursor.execute("""
                    INSERT INTO clientes (nombre_comercial, tipo, rfc, contacto, telefono)
                    VALUES (?, ?, ?, ?, ?)
                """, (nombre, tipo, entry_rfc.get().strip().upper(), entry_contacto.get().strip(), entry_telefono.get().strip()))
                
                self.conn.commit()
                messagebox.showinfo("Éxito", "Cliente registrado correctamente", parent=ventana)
                
                # Recargar clientes y seleccionar el nuevo
                self.cargar_clientes()
                display_name = f"{nombre} ({tipo})"
                self.combo_cliente.set(display_name)
                self.cliente_seleccionado()
                
                ventana.destroy()
                
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{str(e)}", parent=ventana)
        
        frame_btn = tk.Frame(frame)
        frame_btn.grid(row=5, column=0, columnspan=2, pady=15)
        
        tk.Button(frame_btn, text="💾 Guardar", command=guardar_rapido, bg='#27ae60', fg='white',
                 font=('Arial', 10, 'bold'), cursor='hand2', padx=15, pady=5).pack(side='left', padx=5)
        tk.Button(frame_btn, text="❌ Cancelar", command=ventana.destroy, bg='#6b7280', fg='white',
                 font=('Arial', 10, 'bold'), cursor='hand2', padx=15, pady=5).pack(side='left', padx=5)
        
        ventana.transient(self.ventana)
        ventana.grab_set()
    
    def nuevo_producto_rapido(self, ventana_padre, callback_recargar):
        """Crea un nuevo producto de forma rápida desde la ventana de cotización"""
        ventana = tk.Toplevel(ventana_padre)
        ventana.title("Nuevo Producto Rápido")
        ventana.geometry("520x500")
        ventana.minsize(440, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.parent)
        
        frame = tk.Frame(ventana, padx=20, pady=15)
        frame.pack(fill='both', expand=True)
        
        # Categorías y subcategorías
        self.cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        categorias = self.cursor.fetchall()
        cat_dict = {nombre: cat_id for cat_id, nombre in categorias}
        
        campos = []
        
        # Nombre
        tk.Label(frame, text="Nombre del Producto:*", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=0, column=0, sticky='w', pady=3)
        entry_nombre = tk.Entry(frame, width=40, font=('Arial', 9))
        entry_nombre.grid(row=0, column=1, pady=3, sticky='w')
        entry_nombre.focus()
        
        # Código (opcional, se puede autogenerar)
        tk.Label(frame, text="Código (opcional):", font=('Arial', 9),
                 anchor='w').grid(row=1, column=0, sticky='w', pady=3)
        entry_codigo = tk.Entry(frame, width=40, font=('Arial', 9))
        entry_codigo.grid(row=1, column=1, pady=3, sticky='w')
        
        # Categoría
        tk.Label(frame, text="Categoría:*", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=2, column=0, sticky='w', pady=3)
        combo_cat = ttk.Combobox(frame, values=[c[1] for c in categorias],
                                  state='readonly', width=37, font=('Arial', 9))
        combo_cat.grid(row=2, column=1, pady=3, sticky='w')
        if categorias:
            combo_cat.set(categorias[0][1])
        
        # Subcategoría
        tk.Label(frame, text="Subcategoría:", font=('Arial', 9),
                 anchor='w').grid(row=3, column=0, sticky='w', pady=3)
        combo_subcat = ttk.Combobox(frame, state='readonly', width=37, font=('Arial', 9))
        combo_subcat.grid(row=3, column=1, pady=3, sticky='w')
        
        def cargar_subcats(event=None):
            cat_nombre = combo_cat.get()
            if not cat_nombre:
                return
            cat_id = cat_dict.get(cat_nombre)
            if cat_id:
                self.cursor.execute(
                    "SELECT nombre FROM subcategorias WHERE categoria_id = ? ORDER BY nombre",
                    (cat_id,))
                subcats = [s[0] for s in self.cursor.fetchall()]
                combo_subcat['values'] = subcats
                if subcats:
                    combo_subcat.set(subcats[0])
        
        combo_cat.bind('<<ComboboxSelected>>', cargar_subcats)
        cargar_subcats()
        
        # Descripción
        tk.Label(frame, text="Descripción:", font=('Arial', 9),
                 anchor='w').grid(row=4, column=0, sticky='nw', pady=3)
        text_desc = tk.Text(frame, width=40, height=3, font=('Arial', 9))
        text_desc.grid(row=4, column=1, pady=3, sticky='w')
        
        # Precio Base
        tk.Label(frame, text="Precio Base:*", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=5, column=0, sticky='w', pady=3)
        entry_precio = tk.Entry(frame, width=20, font=('Arial', 9))
        entry_precio.grid(row=5, column=1, pady=3, sticky='w')
        
        # Aplica IVA
        tk.Label(frame, text="Aplica IVA:", font=('Arial', 9),
                 anchor='w').grid(row=6, column=0, sticky='w', pady=3)
        var_iva = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, variable=var_iva, font=('Arial', 9)).grid(
            row=6, column=1, pady=3, sticky='w')
        
        # Unidad de medida
        tk.Label(frame, text="Unidad:", font=('Arial', 9),
                 anchor='w').grid(row=7, column=0, sticky='w', pady=3)
        combo_unidad = ttk.Combobox(frame, values=['Pza', 'Kg', 'L', 'M', 'Caja', 'Paquete'],
                                      width=15, font=('Arial', 9))
        combo_unidad.grid(row=7, column=1, pady=3, sticky='w')
        combo_unidad.set('Pza')
        
        # Stock inicial
        tk.Label(frame, text="Stock Inicial:", font=('Arial', 9),
                 anchor='w').grid(row=8, column=0, sticky='w', pady=3)
        entry_stock = tk.Entry(frame, width=20, font=('Arial', 9))
        entry_stock.grid(row=8, column=1, pady=3, sticky='w')
        entry_stock.insert(0, '0')
        
        # Stock mínimo
        tk.Label(frame, text="Stock Mínimo:", font=('Arial', 9),
                 anchor='w').grid(row=9, column=0, sticky='w', pady=3)
        entry_stock_min = tk.Entry(frame, width=20, font=('Arial', 9))
        entry_stock_min.grid(row=9, column=1, pady=3, sticky='w')
        entry_stock_min.insert(0, '0')
        
        def guardar():
            nombre = entry_nombre.get().strip()
            codigo = entry_codigo.get().strip()
            cat_nombre = combo_cat.get()
            precio_txt = entry_precio.get().strip()
            
            if not nombre or not cat_nombre or not precio_txt:
                messagebox.showwarning("Advertencia",
                                       "Nombre, categoría y precio son obligatorios",
                                       parent=ventana)
                return
            
            try:
                precio = float(precio_txt)
                stock = float(entry_stock.get().strip() or '0')
                stock_min = float(entry_stock_min.get().strip() or '0')
            except ValueError:
                messagebox.showwarning("Advertencia",
                                       "Precio y stocks deben ser números válidos",
                                       parent=ventana)
                return
            
            cat_id = cat_dict.get(cat_nombre)
            subcat_nombre = combo_subcat.get()
            subcat_id = None
            if subcat_nombre:
                self.cursor.execute(
                    "SELECT id FROM subcategorias WHERE nombre = ? AND categoria_id = ?",
                    (subcat_nombre, cat_id))
                r = self.cursor.fetchone()
                if r:
                    subcat_id = r[0]
            
            descripcion = text_desc.get('1.0', 'end-1c').strip()
            aplica_iva = 1 if var_iva.get() else 0
            unidad = combo_unidad.get()
            
            # Generar código si no se proporcionó
            if not codigo:
                # Usar primeras 3 letras de cat + primeras 3 de subcat + consecutivo
                prefix = cat_nombre[:3].upper()
                if subcat_nombre:
                    prefix += subcat_nombre[:3].upper()
                else:
                    prefix += "GEN"
                self.cursor.execute(
                    "SELECT codigo FROM productos WHERE codigo LIKE ? ORDER BY codigo DESC LIMIT 1",
                    (f'{prefix}%',))
                ultimo = self.cursor.fetchone()
                if ultimo:
                    try:
                        num = int(ultimo[0][len(prefix):]) + 1
                    except:
                        num = 1
                else:
                    num = 1
                codigo = f"{prefix}{num:04d}"
            
            try:
                self.cursor.execute("""
                    INSERT INTO productos
                    (codigo, nombre, descripcion, categoria_id, subcategoria_id,
                     precio_base, aplica_iva, unidad_medida, stock_actual, stock_minimo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (codigo, nombre, descripcion, cat_id, subcat_id,
                      precio, aplica_iva, unidad, stock, stock_min))
                self.conn.commit()
                messagebox.showinfo("Éxito", f"Producto '{nombre}' creado correctamente.\nCódigo: {codigo}",
                                    parent=ventana)
                callback_recargar()
                ventana.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", f"Ya existe un producto con el código '{codigo}'",
                                     parent=ventana)
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e), parent=ventana)
        
        fb = tk.Frame(frame)
        fb.grid(row=10, column=0, columnspan=2, pady=12)
        tk.Button(fb, text="💾 Guardar", command=guardar,
                  bg='#0f7b5e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(fb, text="❌ Cancelar", command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        
        ventana.transient(ventana_padre)
        ventana.grab_set()
    
    def agregar_producto(self):
        """Abre ventana para seleccionar y agregar un producto"""
        
        # Verificar que haya cliente seleccionado
        if not self.combo_cliente.get():
            messagebox.showwarning("Advertencia", "Primero selecciona un cliente")
            return
        
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
        
        # Tabla de productos disponibles
        frame_tabla = tk.Frame(ventana)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=5)
        
        tree = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Nombre', 'Precio Base', 'IVA', 'Stock'),
            show='headings',
            selectmode='browse'
        )
        
        tree.heading('ID', text='ID')
        tree.heading('Código', text='Código')
        tree.heading('Nombre', text='Nombre')
        tree.heading('Precio Base', text='Precio Base')
        tree.heading('IVA', text='IVA')
        tree.heading('Stock', text='Stock')
        
        tree.column('ID', width=50)
        tree.column('Código', width=100)
        tree.column('Nombre', width=250)
        tree.column('Precio Base', width=100)
        tree.column('IVA', width=50)
        tree.column('Stock', width=80)
        
        scroll = ttk.Scrollbar(frame_tabla, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        def cargar_productos():
            """Carga productos en la tabla"""
            tree.delete(*tree.get_children())
            
            buscar = entry_buscar.get().strip()
            if buscar:
                self.cursor.execute("""
                    SELECT id, codigo, nombre, precio_base, aplica_iva, stock_actual
                    FROM productos
                    WHERE codigo LIKE ? OR nombre LIKE ?
                    ORDER BY nombre
                """, (f'%{buscar}%', f'%{buscar}%'))
            else:
                self.cursor.execute("""
                    SELECT id, codigo, nombre, precio_base, aplica_iva, stock_actual
                    FROM productos
                    ORDER BY nombre
                """)
            
            for row in self.cursor.fetchall():
                row_list = list(row)
                row_list[3] = f"${row[3]:,.2f}"
                row_list[4] = "Sí" if row[4] else "No"
                tree.insert('', 'end', values=row_list)
        
        # Referenciar cargar_productos después de definirla
        tk.Button(
            frame_busqueda,
            text="➕ Nuevo Producto",
            command=lambda: self.nuevo_producto_rapido(ventana, cargar_productos),
            bg='#27ae60',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='right', padx=5)
        
        entry_buscar.bind('<KeyRelease>', lambda e: cargar_productos())
        cargar_productos()
        
        # Frame de cantidad
        frame_cantidad = tk.Frame(ventana)
        frame_cantidad.pack(fill='x', padx=10, pady=10)
        
        tk.Label(frame_cantidad, text="Cantidad:", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        entry_cantidad = tk.Entry(frame_cantidad, width=15, font=('Arial', 10))
        entry_cantidad.pack(side='left', padx=5)
        entry_cantidad.insert(0, "1")
        
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
                if cantidad <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("Advertencia", "Ingresa una cantidad válida", parent=ventana)
                return
            
            item = tree.item(seleccion[0])
            producto_id = item['values'][0]
            
            # Obtener datos completos del producto
            self.cursor.execute("""
                SELECT id, codigo, nombre, precio_base, aplica_iva, stock_actual
                FROM productos WHERE id = ?
            """, (producto_id,))
            
            producto = self.cursor.fetchone()
            if producto:
                # Calcular precio con utilidad según tipo de cliente
                cliente_info = self.clientes[self.combo_cliente.get()]
                tipo_cliente = cliente_info['tipo']
                porcentaje_utilidad = self.UTILIDAD[tipo_cliente] / 100
                
                precio_base = producto[3]
                aplica_iva = producto[4]
                stock = producto[5]
                
                # Calcular precio unitario
                if tipo_cliente == 'Gobierno' and aplica_iva:
                    # Para gobierno: precio base + utilidad (el IVA se agrega después en el total)
                    precio_unitario = precio_base * (1 + porcentaje_utilidad)
                    # NO multiplicar por 1.16 aquí
                else:
                    # Para hotel: solo utilidad (sin IVA)
                    precio_unitario = precio_base * (1 + porcentaje_utilidad)
                
                # Calcular subtotal
                subtotal = precio_unitario * cantidad
                
                # Calcular IVA (solo si aplica)
                iva = 0
                if aplica_iva and tipo_cliente == 'Gobierno':
                    # IVA se calcula sobre el subtotal
                    iva = subtotal * 0.16
                
                total = subtotal + iva
                
                # Verificar stock
                tiene_stock = cantidad <= stock
                
                # Agregar a la lista
                self.productos_cotizacion.append({
                    'producto_id': producto_id,
                    'codigo': producto[1],
                    'nombre': producto[2],
                    'cantidad': cantidad,
                    'precio_unitario': precio_unitario,
                    'subtotal': subtotal,
                    'iva': iva,
                    'total': total,
                    'tiene_stock': tiene_stock,
                    'stock_disponible': stock
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
    
    def editar_cantidad_producto(self):
        """Permite editar la cantidad de un producto ya agregado a la cotización"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona un producto de la lista para editar su cantidad")
            return
        
        # Obtener índice del elemento seleccionado
        item_id = seleccion[0]
        idx = self.tree_productos.index(item_id)
        
        if idx >= len(self.productos_cotizacion):
            return
        
        prod = self.productos_cotizacion[idx]
        
        nueva_cantidad = simpledialog.askfloat(
            "Editar Cantidad",
            f"Producto: {prod['nombre']}\n"
            f"Stock disponible: {prod['stock_disponible']}\n"
            f"Cantidad actual: {prod['cantidad']}\n\n"
            f"Nueva cantidad:",
            initialvalue=prod['cantidad'],
            minvalue=0.01,
            parent=self.ventana
        )
        
        if nueva_cantidad is None:
            return
        
        # Recalcular con la nueva cantidad
        cliente_info = self.clientes.get(self.combo_cliente.get())
        if not cliente_info:
            return
        
        tipo_cliente = cliente_info['tipo']
        porcentaje_utilidad = self.UTILIDAD[tipo_cliente] / 100
        
        self.cursor.execute(
            "SELECT precio_base, aplica_iva, stock_actual FROM productos WHERE id = ?",
            (prod['producto_id'],)
        )
        resultado = self.cursor.fetchone()
        if not resultado:
            return
        
        precio_base, aplica_iva, stock = resultado
        
        if tipo_cliente == 'Gobierno' and aplica_iva:
            precio_unitario = precio_base * (1 + porcentaje_utilidad)
        else:
            precio_unitario = precio_base * (1 + porcentaje_utilidad)
        
        subtotal = precio_unitario * nueva_cantidad
        iva = subtotal * 0.16 if (aplica_iva and tipo_cliente == 'Gobierno') else 0
        total = subtotal + iva
        tiene_stock = nueva_cantidad <= stock
        
        # Actualizar el diccionario del producto
        self.productos_cotizacion[idx].update({
            'cantidad': nueva_cantidad,
            'precio_unitario': precio_unitario,
            'subtotal': subtotal,
            'iva': iva,
            'total': total,
            'tiene_stock': tiene_stock,
            'stock_disponible': stock
        })
        
        self.actualizar_tabla_productos()
    
    def editar_producto_completo(self):
        """Permite editar TODOS los campos de un producto ya agregado a la cotización"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            return
        
        item_id = seleccion[0]
        idx = self.tree_productos.index(item_id)
        
        if idx >= len(self.productos_cotizacion):
            return
        
        prod = self.productos_cotizacion[idx]
        
        # Ventana de edición completa
        ventana = tk.Toplevel(self.ventana)
        ventana.title(f"Editar Producto: {prod['nombre']}")
        ventana.geometry("500x450")
        ventana.minsize(420, 370)
        ventana.resizable(True, True)
        _centrar(ventana, self.parent)
        
        frame = tk.Frame(ventana, padx=20, pady=15)
        frame.pack(fill='both', expand=True)
        
        # Código (no editable, solo referencia)
        tk.Label(frame, text="Código:", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=0, column=0, sticky='w', pady=3)
        tk.Label(frame, text=prod['codigo'], font=('Arial', 9),
                 fg='#555', anchor='w').grid(row=0, column=1, sticky='w', pady=3)
        
        # Nombre del producto (solo lectura)
        tk.Label(frame, text="Producto:", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=1, column=0, sticky='w', pady=3)
        tk.Label(frame, text=prod['nombre'], font=('Arial', 9),
                 wraplength=300, anchor='w').grid(row=1, column=1, sticky='w', pady=3)
        
        # Descripción personalizada (override opcional)
        tk.Label(frame, text="Descripción\n(personalizada):", font=('Arial', 9),
                 anchor='w').grid(row=2, column=0, sticky='nw', pady=3)
        text_desc = tk.Text(frame, width=35, height=3, font=('Arial', 9))
        text_desc.grid(row=2, column=1, pady=3, sticky='w')
        if 'descripcion_custom' in prod and prod['descripcion_custom']:
            text_desc.insert('1.0', prod['descripcion_custom'])
        
        # Cantidad
        tk.Label(frame, text="Cantidad:*", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=3, column=0, sticky='w', pady=3)
        entry_cant = tk.Entry(frame, width=20, font=('Arial', 9))
        entry_cant.grid(row=3, column=1, pady=3, sticky='w')
        entry_cant.insert(0, str(prod['cantidad']))
        
        tk.Label(frame, text=f"Stock disponible: {prod['stock_disponible']:.2f}",
                 font=('Arial', 8), fg='#777').grid(row=4, column=1, sticky='w')
        
        # Precio Unitario
        tk.Label(frame, text="Precio Unitario:*", font=('Arial', 9, 'bold'),
                 anchor='w').grid(row=5, column=0, sticky='w', pady=3)
        entry_precio = tk.Entry(frame, width=20, font=('Arial', 9))
        entry_precio.grid(row=5, column=1, pady=3, sticky='w')
        entry_precio.insert(0, f"{prod['precio_unitario']:.2f}")
        
        # Descuento (opcional, nuevo campo)
        tk.Label(frame, text="Descuento %:", font=('Arial', 9),
                 anchor='w').grid(row=6, column=0, sticky='w', pady=3)
        entry_desc = tk.Entry(frame, width=20, font=('Arial', 9))
        entry_desc.grid(row=6, column=1, pady=3, sticky='w')
        entry_desc.insert(0, str(prod.get('descuento_pct', 0)))
        
        # IVA (solo informativo)
        aplica_iva = prod.get('aplica_iva', prod['iva'] > 0)
        tk.Label(frame, text="Aplica IVA:", font=('Arial', 9),
                 anchor='w').grid(row=7, column=0, sticky='w', pady=3)
        tk.Label(frame, text="Sí" if aplica_iva else "No", font=('Arial', 9),
                 fg='#16a085' if aplica_iva else '#777').grid(row=7, column=1, sticky='w', pady=3)
        
        # Vista previa de totales
        frame_preview = tk.LabelFrame(frame, text="Vista Previa", font=('Arial', 9, 'bold'))
        frame_preview.grid(row=8, column=0, columnspan=2, pady=10, sticky='ew')
        
        lbl_prev_subtotal = tk.Label(frame_preview, text="Subtotal: $0.00", font=('Arial', 9))
        lbl_prev_subtotal.pack(anchor='w', padx=10, pady=2)
        lbl_prev_iva = tk.Label(frame_preview, text="IVA: $0.00", font=('Arial', 9))
        lbl_prev_iva.pack(anchor='w', padx=10, pady=2)
        lbl_prev_total = tk.Label(frame_preview, text="Total: $0.00", font=('Arial', 10, 'bold'))
        lbl_prev_total.pack(anchor='w', padx=10, pady=2)
        
        def actualizar_preview(event=None):
            try:
                cant = float(entry_cant.get() or 0)
                precio = float(entry_precio.get() or 0)
                desc_pct = float(entry_desc.get() or 0)
                
                # Aplicar descuento
                precio_con_desc = precio * (1 - desc_pct / 100)
                subtotal = cant * precio_con_desc
                
                # Calcular IVA según tipo de cliente
                cliente_info = self.clientes.get(self.combo_cliente.get())
                iva_amt = 0
                if cliente_info and aplica_iva and cliente_info['tipo'] == 'Gobierno':
                    iva_amt = subtotal * 0.16
                
                total = subtotal + iva_amt
                
                lbl_prev_subtotal.config(text=f"Subtotal: ${subtotal:,.2f}")
                lbl_prev_iva.config(text=f"IVA: ${iva_amt:,.2f}")
                lbl_prev_total.config(text=f"Total: ${total:,.2f}")
            except:
                pass
        
        entry_cant.bind('<KeyRelease>', actualizar_preview)
        entry_precio.bind('<KeyRelease>', actualizar_preview)
        entry_desc.bind('<KeyRelease>', actualizar_preview)
        actualizar_preview()
        
        def guardar_cambios():
            try:
                nueva_cant = float(entry_cant.get())
                nuevo_precio = float(entry_precio.get())
                desc_pct = float(entry_desc.get() or 0)
                
                if nueva_cant <= 0 or nuevo_precio < 0:
                    messagebox.showwarning("Advertencia", "Cantidad y precio deben ser mayores a 0",
                                           parent=ventana)
                    return
            except ValueError:
                messagebox.showwarning("Advertencia", "Ingresa valores numéricos válidos",
                                       parent=ventana)
                return
            
            # Aplicar descuento
            precio_final = nuevo_precio * (1 - desc_pct / 100)
            subtotal = nueva_cant * precio_final
            
            # Calcular IVA
            cliente_info = self.clientes.get(self.combo_cliente.get())
            iva_amt = 0
            if cliente_info and aplica_iva and cliente_info['tipo'] == 'Gobierno':
                iva_amt = subtotal * 0.16
            
            total = subtotal + iva_amt
            
            # Stock check
            tiene_stock = nueva_cant <= prod['stock_disponible']
            
            # Actualizar producto en la lista
            prod['cantidad'] = nueva_cant
            prod['precio_unitario'] = nuevo_precio  # Guardamos el precio SIN descuento
            prod['descuento_pct'] = desc_pct
            prod['subtotal'] = subtotal
            prod['iva'] = iva_amt
            prod['total'] = total
            prod['tiene_stock'] = tiene_stock
            prod['descripcion_custom'] = text_desc.get('1.0', 'end-1c').strip()
            
            self.actualizar_tabla_productos()
            ventana.destroy()
        
        fb = tk.Frame(frame)
        fb.grid(row=9, column=0, columnspan=2, pady=12)
        tk.Button(fb, text="💾 Guardar Cambios", command=guardar_cambios,
                  bg='#0f7b5e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(fb, text="❌ Cancelar", command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        
        ventana.transient(self.ventana)
        ventana.grab_set()
    
    def quitar_producto(self):
        """Quita el producto seleccionado de la cotización"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona un producto para quitar")
            return
        
        # Obtener índice del producto
        item = self.tree_productos.item(seleccion[0])
        codigo = item['values'][0]
        
        # Buscar y eliminar de la lista
        for i, prod in enumerate(self.productos_cotizacion):
            if prod['codigo'] == codigo:
                del self.productos_cotizacion[i]
                break
        
        self.actualizar_tabla_productos()
    
    def actualizar_tabla_productos(self):
        """Actualiza la tabla de productos y los totales"""
        # Limpiar tabla
        self.tree_productos.delete(*self.tree_productos.get_children())
        
        subtotal_total = 0
        iva_total = 0
        total_general = 0
        
        # Insertar productos
        for prod in self.productos_cotizacion:
            # Determinar si tiene stock
            stock_texto = "✓" if prod['tiene_stock'] else "✗ Sin stock"
            
            # Insertar en tabla
            self.tree_productos.insert('', 'end', values=(
                prod['codigo'],
                prod['nombre'],
                f"{prod['cantidad']:.2f}",
                f"${prod['precio_unitario']:,.2f}",
                f"${prod['subtotal']:,.2f}",
                f"${prod['iva']:,.2f}",
                f"${prod['total']:,.2f}",
                stock_texto
            ))
            
            subtotal_total += prod['subtotal']
            iva_total += prod['iva']
            total_general += prod['total']
        
        # Actualizar labels de totales
        self.label_subtotal.config(text=f"${subtotal_total:,.2f}")
        self.label_iva.config(text=f"${iva_total:,.2f}")
        self.label_total.config(text=f"${total_general:,.2f}")
    
    def recalcular_productos(self):
        """Recalcula los precios de todos los productos según el cliente"""
        if not self.productos_cotizacion:
            return
        
        cliente_info = self.clientes[self.combo_cliente.get()]
        tipo_cliente = cliente_info['tipo']
        porcentaje_utilidad = self.UTILIDAD[tipo_cliente] / 100
        
        for prod in self.productos_cotizacion:
            # Obtener precio base del producto
            self.cursor.execute("""
                SELECT precio_base, aplica_iva
                FROM productos WHERE id = ?
            """, (prod['producto_id'],))
            
            resultado = self.cursor.fetchone()
            if resultado:
                precio_base, aplica_iva = resultado
                cantidad = prod['cantidad']
                
                # Recalcular precio unitario
                if tipo_cliente == 'Gobierno' and aplica_iva:
                    precio_con_utilidad = precio_base * (1 + porcentaje_utilidad)
                    precio_unitario = precio_con_utilidad * 1.16
                else:
                    precio_unitario = precio_base * (1 + porcentaje_utilidad)
                
                subtotal = precio_unitario * cantidad
                
                iva = 0
                if aplica_iva and tipo_cliente == 'Gobierno':
                    precio_sin_iva = subtotal / 1.16
                    iva = subtotal - precio_sin_iva
                
                total = subtotal
                
                # Actualizar producto
                prod['precio_unitario'] = precio_unitario
                prod['subtotal'] = subtotal
                prod['iva'] = iva
                prod['total'] = total
        
        self.actualizar_tabla_productos()
    
    def _calcular_umbral_dias(self, producto_id):
        """Calcula el umbral de días para considerar un precio desactualizado.
        Si hay 3+ registros históricos: promedio de días entre cambios × 0.8
        Si no: default de 30 días.
        Retorna (umbral_dias, n_registros, confianza)
        """
        self.cursor.execute("""
            SELECT fecha FROM producto_precio_historial
            WHERE producto_id = ?
              AND fuente != 'backfill'
            ORDER BY fecha ASC
        """, (producto_id,))
        fechas = [r[0] for r in self.cursor.fetchall()]
        n = len(fechas)

        if n >= 3:
            from datetime import date as _date
            deltas = []
            for i in range(1, n):
                try:
                    d1 = _date.fromisoformat(fechas[i-1])
                    d2 = _date.fromisoformat(fechas[i])
                    deltas.append((d2 - d1).days)
                except Exception:
                    pass
            if deltas:
                promedio = sum(deltas) / len(deltas)
                umbral   = max(7, int(promedio * 0.8))
                return umbral, n, 'alta'

        return 30, n, 'baja' if n == 0 else 'media'

    def _verificar_precios_desactualizados(self):
        """Revisa cada producto de la cotización y muestra alerta si alguno
        tiene precio_base desactualizado según su umbral calculado."""
        from datetime import date as _date
        hoy = _date.today()

        productos_alerta = []
        for prod in self.productos_cotizacion:
            pid = prod['producto_id']

            # Obtener último cambio de precio REAL (excluir backfill inicial)
            self.cursor.execute("""
                SELECT fecha, fuente FROM producto_precio_historial
                WHERE producto_id = ?
                ORDER BY fecha DESC, fecha_registro DESC
                LIMIT 1
            """, (pid,))
            row = self.cursor.fetchone()

            self.cursor.execute("SELECT precio_base, precio_base_fecha FROM productos WHERE id=?", (pid,))
            pr = self.cursor.fetchone()
            precio_actual = pr[0] if pr else 0

            if not row or row[1] == 'backfill':
                # Solo hay backfill o nada — usar precio_base_fecha del producto
                # Si precio_base_fecha también es nulo, el precio nunca se ha revisado
                ultima_fecha_str = pr[1] if pr else None
            else:
                ultima_fecha_str = row[0]

            umbral, n_registros, confianza = self._calcular_umbral_dias(pid)

            if ultima_fecha_str:
                try:
                    ultima_fecha = _date.fromisoformat(str(ultima_fecha_str)[:10])
                    dias_desde = (hoy - ultima_fecha).days
                except Exception:
                    dias_desde = 9999
            else:
                dias_desde = 9999  # nunca actualizado

            if dias_desde > umbral:
                productos_alerta.append({
                    'nombre':       prod['nombre'],
                    'precio':       precio_actual,
                    'dias':         dias_desde,
                    'umbral':       umbral,
                    'n_registros':  n_registros,
                    'confianza':    confianza,
                    'producto_id':  pid,
                })

        if not productos_alerta:
            return

        # ── Modal de alerta con edición inline ────────────────────────────
        dlg = tk.Toplevel(self.ventana)
        dlg.title("⚠ Precios posiblemente desactualizados")
        dlg.geometry("700x480")
        dlg.minsize(620, 400)
        dlg.resizable(True, True)
        _centrar(dlg, self.parent)
        dlg.configure(bg="#fff7ed")
        dlg.transient(self.ventana)
        dlg.grab_set()

        dlg.update_idletasks()
        x = self.ventana.winfo_x() + (self.ventana.winfo_width()  - 700) // 2
        y = self.ventana.winfo_y() + (self.ventana.winfo_height() - 480) // 2
        dlg.geometry(f"700x480+{x}+{y}")
        _centrar(dlg, self.parent)

        # Header
        hdr = tk.Frame(dlg, bg="#d97706", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚠  Verificación de Precios",
                 font=("Arial", 11, "bold"), bg="#d97706", fg="white").pack()
        n_alerta = len(productos_alerta)
        tk.Label(hdr,
                 text=f"{n_alerta} producto{'s' if n_alerta>1 else ''} con precio "
                      f"posiblemente desactualizado — puedes actualizar aquí mismo",
                 font=("Arial", 9), bg="#d97706", fg="#fff7ed").pack()

        # Instrucción
        tk.Label(dlg,
                 text="Escribe el nuevo precio y pulsa 💾 para actualizar. "
                      "Deja el campo igual si no quieres cambiar ese producto.",
                 font=("Arial", 8, "italic"), bg="#fff7ed", fg="#92400e",
                 pady=4).pack()

        # Canvas scrollable para filas editables
        canvas_f = tk.Frame(dlg, bg="#fff7ed")
        canvas_f.pack(fill="both", expand=True, padx=16, pady=(0, 4))
        canvas_f.grid_rowconfigure(0, weight=1)
        canvas_f.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(canvas_f, bg="#fff7ed", highlightthickness=0)
        sc = ttk.Scrollbar(canvas_f, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sc.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sc.grid(row=0, column=1, sticky="ns")

        inner = tk.Frame(canvas, bg="#fff7ed")
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))

        # Header de columnas
        cols_hdr = ["Producto", "Precio actual", "Nuevo precio", "Días sin cambio", "Confianza", ""]
        widths_h = [230, 90, 90, 100, 80, 70]
        for ci, (ch, cw) in enumerate(zip(cols_hdr, widths_h)):
            tk.Label(inner, text=ch, font=("Arial", 8, "bold"),
                     bg="#fef3c7", fg="#92400e", width=cw//7, anchor="w",
                     padx=4, pady=3).grid(row=0, column=ci, sticky="ew", padx=1, pady=(0,2))

        entries_por_pid = {}  # pid -> Entry widget

        def _actualizar_precio(pid, nombre, entry, lbl_actual, row_frame):
            txt = entry.get().strip().replace('$','').replace(',','')
            try:
                nuevo = float(txt)
                if nuevo <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Precio inválido",
                    f"Ingresa un número mayor a 0 para '{nombre}'.",
                    parent=dlg)
                return
            from datetime import date as _d
            # Obtener precio anterior
            self.cursor.execute("SELECT precio_base FROM productos WHERE id=?", (pid,))
            pr = self.cursor.fetchone()
            precio_anterior = pr[0] if pr else None
            if precio_anterior is not None and abs(nuevo - precio_anterior) < 0.001:
                messagebox.showinfo("Sin cambio",
                    f"El precio de '{nombre}' ya es ${nuevo:,.2f}.", parent=dlg)
                return
            self.cursor.execute("""
                UPDATE productos
                SET precio_base = ?, precio_base_fecha = ?
                WHERE id = ?
            """, (nuevo, _d.today().isoformat(), pid))
            self.cursor.execute("""
                INSERT INTO producto_precio_historial
                    (producto_id, precio, fecha, motivo, fuente)
                VALUES (?, ?, ?, ?, 'manual')
            """, (pid, nuevo, _d.today().isoformat(), 'Actualizado desde alerta de cotización'))
            self.conn.commit()
            lbl_actual.config(text=f"${nuevo:,.2f}", fg="#16a34a")
            entry.config(state="disabled", bg="#f0fdf4")
            row_frame.configure(bg="#f0fdf4")
            for w in row_frame.winfo_children():
                try: w.configure(bg="#f0fdf4")
                except Exception: pass

        for ri, p in enumerate(productos_alerta, 1):
            pid    = p['producto_id']
            nombre = p['nombre']
            conf_color = {"alta": "#dc2626", "media": "#d97706", "baja": "#9ca3af"}.get(
                p['confianza'], "#374151")
            conf_txt = {"alta": "Alta ✓✓✓", "media": "Media ✓✓", "baja": "Baja ✓"}.get(
                p['confianza'], p['confianza'])
            bg_row = "#fffbeb" if ri % 2 == 0 else "#fff7ed"

            rf = tk.Frame(inner, bg=bg_row)
            rf.grid(row=ri, column=0, columnspan=6, sticky="ew", pady=1)
            for ci2 in range(6):
                rf.grid_columnconfigure(ci2, weight=[4,2,2,2,1,1][ci2])

            tk.Label(rf, text=nombre[:32], font=("Arial", 8), bg=bg_row,
                     fg="#1e2d45", anchor="w", padx=4).grid(row=0, column=0, sticky="ew")

            lbl_actual = tk.Label(rf, text=f"${p['precio']:,.2f}",
                                  font=("Arial", 8), bg=bg_row, fg="#374151", anchor="e")
            lbl_actual.grid(row=0, column=1, sticky="ew", padx=4)

            entry = tk.Entry(rf, font=("Arial", 8), width=10,
                             bg="white", relief="solid", bd=1)
            entry.insert(0, f"{p['precio']:.2f}")
            entry.grid(row=0, column=2, padx=4, pady=2)
            entries_por_pid[pid] = entry

            tk.Label(rf, text=f"{p['dias']} / {p['umbral']} días",
                     font=("Arial", 8), bg=bg_row, fg="#6b7280", anchor="center"
                     ).grid(row=0, column=3, sticky="ew")

            tk.Label(rf, text=conf_txt, font=("Arial", 7, "bold"),
                     bg=bg_row, fg=conf_color, anchor="center"
                     ).grid(row=0, column=4, sticky="ew")

            tk.Button(rf, text="💾",
                      font=("Arial", 9), bg="#065f46", fg="white",
                      cursor="hand2", relief="flat", padx=6,
                      command=lambda _p=pid, _n=nombre, _e=entry, _l=lbl_actual, _rf=rf:
                          _actualizar_precio(_p, _n, _e, _l, _rf)
                      ).grid(row=0, column=5, padx=4, pady=2)

            entry.bind("<Return>", lambda e, _p=pid, _n=nombre, _e=entry,
                       _l=lbl_actual, _rf=rf:
                       _actualizar_precio(_p, _n, _e, _l, _rf))

        # Nota confianza
        nota = tk.Frame(dlg, bg="#fff7ed", padx=16)
        nota.pack(fill="x")
        tk.Label(nota,
                 text="Confianza Alta = 3+ cambios históricos  |  Media = 1-2  |  Baja = sin historial (default 30 días)",
                 font=("Arial", 7, "italic"), bg="#fff7ed", fg="#92400e",
                 wraplength=660, justify="left").pack(anchor="w")

        # Pie
        foot = tk.Frame(dlg, bg="#fef3c7", pady=8)
        foot.pack(fill="x", side="bottom")

        def _ir_catalogo():
            dlg.destroy()
            self.ventana.destroy()
            if self.on_ir_catalogo:
                self.on_ir_catalogo()

        tk.Button(foot, text="✏ Ir a Catálogo",
                  font=("Arial", 9, "bold"), bg="#d97706", fg="white",
                  cursor="hand2", padx=10, pady=5, relief="flat",
                  command=_ir_catalogo).pack(side="left", padx=12)
        tk.Button(foot, text="Cerrar",
                  font=("Arial", 9), bg="#6b7280", fg="white",
                  cursor="hand2", padx=12, pady=5, relief="flat",
                  command=dlg.destroy).pack(side="right", padx=12)
        tk.Label(foot, text="La cotización ya fue guardada correctamente.",
                 font=("Arial", 8), bg="#fef3c7", fg="#92400e").pack(side="right", padx=8)

        dlg.wait_window()

    def guardar_cotizacion(self):
        """Guarda la cotización en la base de datos"""
        
        # Validaciones
        if not self.combo_cliente.get():
            messagebox.showwarning("Advertencia", "Debes seleccionar un cliente")
            return
        
        if not self.productos_cotizacion:
            messagebox.showwarning("Advertencia", "Debes agregar al menos un producto")
            return
        
        try:
            # Calcular totales
            subtotal = sum(p['subtotal'] for p in self.productos_cotizacion)
            iva = sum(p['iva'] for p in self.productos_cotizacion)
            total = sum(p['total'] for p in self.productos_cotizacion)
            
            # Obtener cliente ID
            cliente_info = self.clientes[self.combo_cliente.get()]
            cliente_id = cliente_info['id']
            
            # Obtener notas
            notas = self.text_notas.get('1.0', 'end-1c').strip()
            
            if self.modo == 'nueva':
                # MODO NUEVA COTIZACIÓN
                # Generar folio
                fecha_actual = datetime.now()
                año = fecha_actual.strftime('%Y')
                
                self.cursor.execute("""
                    SELECT COUNT(*) FROM cotizaciones
                    WHERE strftime('%Y', fecha) = ?
                """, (año,))
                
                consecutivo = self.cursor.fetchone()[0] + 1
                folio = f"COT-{año}-{consecutivo:04d}"
                
                # Insertar cotización
                self.cursor.execute("""
                    INSERT INTO cotizaciones (folio, fecha, cliente_id, subtotal, iva, total, notas, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente')
                """, (folio, fecha_actual.strftime('%Y-%m-%d'), cliente_id, subtotal, iva, total, notas))
                
                cotizacion_id = self.cursor.lastrowid
                
                # Insertar detalle con snapshot de costo al momento de cotizar
                for prod in self.productos_cotizacion:
                    # Obtener precio_base actual como snapshot de costo
                    self.cursor.execute(
                        "SELECT precio_base FROM productos WHERE id=?",
                        (prod['producto_id'],))
                    pb_row = self.cursor.fetchone()
                    costo_snap = pb_row[0] if pb_row else 0.0

                    self.cursor.execute("""
                        INSERT INTO cotizacion_detalle
                        (cotizacion_id, producto_id, cantidad, precio_unitario,
                         subtotal, iva, total, tiene_stock, costo_snapshot)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        cotizacion_id,
                        prod['producto_id'],
                        prod['cantidad'],
                        prod['precio_unitario'],
                        prod['subtotal'],
                        prod['iva'],
                        prod['total'],
                        1 if prod['tiene_stock'] else 0,
                        costo_snap
                    ))
                
                self.conn.commit()
                
                mensaje_exito = f"Cotización guardada correctamente\n\nFolio: {folio}\nTotal: ${total:,.2f}"
                
            else:
                # MODO EDITAR COTIZACIÓN
                # Actualizar cotización existente
                self.cursor.execute("""
                    UPDATE cotizaciones 
                    SET cliente_id = ?, subtotal = ?, iva = ?, total = ?, notas = ?
                    WHERE id = ?
                """, (cliente_id, subtotal, iva, total, notas, self.cotizacion_id))
                
                # Eliminar detalle anterior
                self.cursor.execute("""
                    DELETE FROM cotizacion_detalle WHERE cotizacion_id = ?
                """, (self.cotizacion_id,))
                
                # Insertar nuevo detalle con snapshot de costo
                for prod in self.productos_cotizacion:
                    self.cursor.execute(
                        "SELECT precio_base FROM productos WHERE id=?",
                        (prod['producto_id'],))
                    pb_row = self.cursor.fetchone()
                    costo_snap = pb_row[0] if pb_row else 0.0

                    self.cursor.execute("""
                        INSERT INTO cotizacion_detalle
                        (cotizacion_id, producto_id, cantidad, precio_unitario,
                         subtotal, iva, total, tiene_stock, costo_snapshot)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        self.cotizacion_id,
                        prod['producto_id'],
                        prod['cantidad'],
                        prod['precio_unitario'],
                        prod['subtotal'],
                        prod['iva'],
                        prod['total'],
                        1 if prod['tiene_stock'] else 0,
                        costo_snap
                    ))
                
                self.conn.commit()
                
                # Obtener folio para el mensaje
                self.cursor.execute("SELECT folio FROM cotizaciones WHERE id = ?", (self.cotizacion_id,))
                folio = self.cursor.fetchone()[0]
                
                mensaje_exito = f"Cotización actualizada correctamente\n\nFolio: {folio}\nTotal: ${total:,.2f}"
            
            messagebox.showinfo("Éxito", mensaje_exito)

            # ── Alerta de precios desactualizados ──────────────────────────
            self._verificar_precios_desactualizados()

            # Verificar si hay productos sin stock
            sin_stock = [p for p in self.productos_cotizacion if not p['tiene_stock']]
            if sin_stock:
                mensaje = "Los siguientes productos no tienen stock suficiente:\n\n"
                for p in sin_stock:
                    mensaje += f"- {p['nombre']} (Stock: {p['stock_disponible']}, Requerido: {p['cantidad']})\n"
                mensaje += "\n¿Deseas generar un presupuesto para compras?"
                respuesta = messagebox.askyesno("Productos sin stock", mensaje)
                if respuesta:
                    messagebox.showinfo("Info", "La función de presupuesto se implementará próximamente")

            self.ventana.destroy()
            
        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror("Error", f"No se pudo guardar la cotización:\n{str(e)}")
