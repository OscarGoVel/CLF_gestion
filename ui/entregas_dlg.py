#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
modules/entregas.py
Ventana para gestionar entregas parciales de cotizaciones.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from datetime import datetime
from ui.utils import centrar_ventana as _centrar
import sesion


class VentanaEntregaParcial:
    """Ventana para gestionar entregas parciales de cotizaciones"""
    
    def __init__(self, parent, conn, cursor, cotizacion_id):
        self.parent = parent
        self.conn = conn
        self.cursor = cursor
        self.cotizacion_id = cotizacion_id
        
        # Crear ventana
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Registrar Entrega Parcial")
        self.ventana.geometry("1100x650")
        self.ventana.minsize(1020, 570)
        self.ventana.resizable(True, True)
        _centrar(self.ventana, self.parent)
        
        # Datos de la cotización
        self.cargar_datos_cotizacion()
        
        # Crear interfaz
        self.crear_interfaz()
        
        # Hacer modal
        self.ventana.transient(parent)
        self.ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def cargar_datos_cotizacion(self):
        """Carga los datos de la cotización"""
        self.cursor.execute("""
            SELECT c.folio, c.fecha, cl.nombre_comercial, c.total
            FROM cotizaciones c
            INNER JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (self.cotizacion_id,))
        
        row = self.cursor.fetchone()
        if row:
            self.folio, self.fecha, self.cliente, self.total = row
        else:
            messagebox.showerror("Error", "No se encontró la cotización")
            self.ventana.destroy()
            return
        
        # Cargar productos con cantidades pendientes
        self.cargar_productos_pendientes()
    
    def cargar_productos_pendientes(self):
        """Carga productos con sus cantidades pendientes de entrega"""
        self.cursor.execute("""
            SELECT 
                cd.producto_id,
                p.codigo,
                p.nombre,
                cd.cantidad as cantidad_total,
                COALESCE(SUM(ep.cantidad_entregada), 0) as cantidad_entregada,
                (cd.cantidad - COALESCE(SUM(ep.cantidad_entregada), 0)) as cantidad_pendiente,
                p.stock_actual,
                p.unidad_medida
            FROM cotizacion_detalle cd
            INNER JOIN productos p ON cd.producto_id = p.id
            LEFT JOIN entregas_parciales ep ON cd.cotizacion_id = ep.cotizacion_id 
                AND cd.producto_id = ep.producto_id
            WHERE cd.cotizacion_id = ?
            GROUP BY cd.producto_id, p.codigo, p.nombre, cd.cantidad, p.stock_actual, p.unidad_medida
            HAVING cantidad_pendiente > 0
            ORDER BY p.nombre
        """, (self.cotizacion_id,))
        
        self.productos = []
        for row in self.cursor.fetchall():
            self.productos.append({
                'producto_id': row[0],
                'codigo': row[1],
                'nombre': row[2],
                'cantidad_total': row[3],
                'cantidad_entregada': row[4],
                'cantidad_pendiente': row[5],
                'stock_actual': row[6],
                'unidad_medida': row[7] or 'Pza'
            })
    
    def crear_interfaz(self):
        """Crea la interfaz de la ventana"""
        
        # Frame superior con información
        frame_info = tk.LabelFrame(self.ventana, text="Información de la Cotización", 
                                   font=('Arial', 10, 'bold'))
        frame_info.pack(fill='x', padx=10, pady=10)
        
        info_frame = tk.Frame(frame_info)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(info_frame, text=f"Folio: {self.folio}", font=('Arial', 10, 'bold')).pack(side='left', padx=10)
        tk.Label(info_frame, text=f"Fecha: {self.fecha}", font=('Arial', 10)).pack(side='left', padx=10)
        tk.Label(info_frame, text=f"Cliente: {self.cliente}", font=('Arial', 10)).pack(side='left', padx=10)
        tk.Label(info_frame, text=f"Total: ${self.total:,.2f}", font=('Arial', 10, 'bold'), 
                fg='#27ae60').pack(side='left', padx=10)
        
        # Frame de productos
        frame_productos = tk.LabelFrame(self.ventana, text="Productos Pendientes de Entrega", 
                                       font=('Arial', 10, 'bold'))
        frame_productos.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Tabla de productos
        frame_tabla = tk.Frame(frame_productos)
        frame_tabla.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Scrollbars
        scroll_y = ttk.Scrollbar(frame_tabla, orient='vertical')
        scroll_x = ttk.Scrollbar(frame_tabla, orient='horizontal')
        
        self.tree_productos = ttk.Treeview(
            frame_tabla,
            columns=('ID', 'Código', 'Producto', 'Total', 'Entregado', 'Pendiente', 'A Entregar', 'Stock', 'Unidad'),
            show='headings',
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )
        
        # Configurar columnas
        self.tree_productos.heading('ID', text='ID')
        self.tree_productos.heading('Código', text='Código')
        self.tree_productos.heading('Producto', text='Producto')
        self.tree_productos.heading('Total', text='Cant. Total')
        self.tree_productos.heading('Entregado', text='Entregado')
        self.tree_productos.heading('Pendiente', text='Pendiente')
        self.tree_productos.heading('A Entregar', text='A Entregar Ahora')
        self.tree_productos.heading('Stock', text='Stock Disp.')
        self.tree_productos.heading('Unidad', text='Unidad')
        
        self.tree_productos.column('ID', width=0, stretch=False)
        self.tree_productos.column('Código', width=80)
        self.tree_productos.column('Producto', width=250)
        self.tree_productos.column('Total', width=90)
        self.tree_productos.column('Entregado', width=90)
        self.tree_productos.column('Pendiente', width=90)
        self.tree_productos.column('A Entregar', width=120)
        self.tree_productos.column('Stock', width=90)
        self.tree_productos.column('Unidad', width=70)
        
        scroll_y.config(command=self.tree_productos.yview)
        scroll_x.config(command=self.tree_productos.xview)
        
        self.tree_productos.pack(side='left', fill='both', expand=True)
        scroll_y.pack(side='right', fill='y')
        scroll_x.pack(side='bottom', fill='x')
        
        # Cargar productos en la tabla
        for prod in self.productos:
            self.tree_productos.insert('', 'end', values=(
                prod['producto_id'],
                prod['codigo'],
                prod['nombre'],
                f"{prod['cantidad_total']:.2f}",
                f"{prod['cantidad_entregada']:.2f}",
                f"{prod['cantidad_pendiente']:.2f}",
                "0.00",  # A entregar (editable)
                f"{prod['stock_actual']:.2f}",
                prod['unidad_medida']
            ), tags=('editable',))
        
        # Botón para editar cantidad a entregar
        frame_botones_tabla = tk.Frame(frame_productos)
        frame_botones_tabla.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_botones_tabla,
            text="✏️ Editar Cantidad a Entregar",
            command=self.editar_cantidad_entregar,
            bg='#3498db',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones_tabla,
            text="🔄 Usar Máximo Posible",
            command=self.usar_maximo_posible,
            bg='#9b59b6',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones_tabla,
            text="📋 Ver Historial de Entregas",
            command=self.ver_historial,
            bg='#34495e',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2',
            padx=10,
            pady=5
        ).pack(side='left', padx=5)
        
        # Frame de notas
        frame_notas = tk.Frame(self.ventana)
        frame_notas.pack(fill='x', padx=10, pady=5)
        
        tk.Label(frame_notas, text="Notas de la entrega:", font=('Arial', 9)).pack(anchor='w')
        self.text_notas = tk.Text(frame_notas, height=3, font=('Arial', 9))
        self.text_notas.pack(fill='x')
        
        # Frame de botones finales
        frame_botones = tk.Frame(self.ventana, bg='#f1f5f9')
        frame_botones.pack(fill='x', padx=10, pady=10)
        
        tk.Button(
            frame_botones,
            text="💾 Registrar Entrega",
            command=self.registrar_entrega,
            bg='#27ae60',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=20,
            pady=10
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_botones,
            text="✓ Marcar Todo Como Entregado",
            command=self.entregar_todo,
            bg='#e67e22',
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
    
    def editar_cantidad_entregar(self):
        """Permite editar la cantidad a entregar de un producto"""
        seleccion = self.tree_productos.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona un producto")
            return
        
        item = self.tree_productos.item(seleccion[0])
        valores = item['values']
        producto_nombre = valores[2]
        pendiente = float(valores[5])
        stock = float(valores[7])
        actual = valores[6]
        
        # Ventana para ingresar cantidad
        cantidad = simpledialog.askfloat(
            "Cantidad a Entregar",
            f"Producto: {producto_nombre}\n" +
            f"Cantidad pendiente: {pendiente}\n" +
            f"Stock disponible: {stock}\n\n" +
            f"¿Cuánto deseas entregar?",
            initialvalue=actual if actual != "0.00" else min(pendiente, stock),
            minvalue=0.0,
            maxvalue=pendiente
        )
        
        if cantidad is not None:
            # Verificar stock
            if cantidad > stock:
                respuesta = messagebox.askyesno(
                    "Stock Insuficiente",
                    f"La cantidad a entregar ({cantidad}) excede el stock disponible ({stock}).\n\n" +
                    f"¿Deseas continuar de todos modos?\n" +
                    f"(El sistema permitirá stock negativo)"
                )
                if not respuesta:
                    return
            
            # Actualizar la tabla
            nuevos_valores = list(valores)
            nuevos_valores[6] = f"{cantidad:.2f}"
            self.tree_productos.item(seleccion[0], values=nuevos_valores)
    
    def usar_maximo_posible(self):
        """Establece la cantidad máxima posible para todos los productos"""
        for item in self.tree_productos.get_children():
            valores = list(self.tree_productos.item(item)['values'])
            pendiente = float(valores[5])
            stock = float(valores[7])
            
            # Usar el menor entre pendiente y stock
            maximo = min(pendiente, stock)
            valores[6] = f"{maximo:.2f}"
            
            self.tree_productos.item(item, values=valores)
        
        messagebox.showinfo("Éxito", "Se estableció el máximo posible para todos los productos")
    
    def ver_historial(self):
        """Muestra el historial de entregas de esta cotización"""
        # Crear ventana de historial
        ventana_historial = tk.Toplevel(self.ventana)
        ventana_historial.title(f"Historial de Entregas - {self.folio}")
        ventana_historial.geometry("900x400")
        ventana.minsize(820, 320)
        ventana.resizable(True, True)
        _centrar(ventana, self.parent)
        
        # Frame para la tabla
        frame = tk.Frame(ventana_historial)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Crear tabla
        tree = ttk.Treeview(
            frame,
            columns=('Fecha', 'Producto', 'Cantidad', 'Notas', 'Registrado'),
            show='headings'
        )
        
        tree.heading('Fecha', text='Fecha Entrega')
        tree.heading('Producto', text='Producto')
        tree.heading('Cantidad', text='Cantidad')
        tree.heading('Notas', text='Notas')
        tree.heading('Registrado', text='Fecha Registro')
        
        tree.column('Fecha', width=100)
        tree.column('Producto', width=300)
        tree.column('Cantidad', width=100)
        tree.column('Notas', width=200)
        tree.column('Registrado', width=150)
        
        scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # Cargar historial
        self.cursor.execute("""
            SELECT 
                ep.fecha_entrega,
                p.nombre,
                ep.cantidad_entregada,
                ep.notas,
                ep.fecha_registro
            FROM entregas_parciales ep
            INNER JOIN productos p ON ep.producto_id = p.id
            WHERE ep.cotizacion_id = ?
            ORDER BY ep.fecha_entrega DESC, ep.fecha_registro DESC
        """, (self.cotizacion_id,))
        
        entregas = self.cursor.fetchall()
        
        if not entregas:
            tree.insert('', 'end', values=('', 'No hay entregas registradas', '', '', ''))
        else:
            for entrega in entregas:
                tree.insert('', 'end', values=entrega)
        
        # Botón cerrar
        tk.Button(
            ventana_historial,
            text="Cerrar",
            command=ventana_historial.destroy,
            bg='#6b7280',
            fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2',
            padx=15,
            pady=5
        ).pack(pady=10)
        
        ventana_historial.transient(self.ventana)
    
    def entregar_todo(self):
        """Marca todo lo pendiente como entregado"""
        respuesta = messagebox.askyesno(
            "Confirmar Entrega Total",
            "¿Deseas marcar TODOS los productos pendientes como entregados?\n\n" +
            "Esto entregará toda la cantidad pendiente de cada producto."
        )
        
        if not respuesta:
            return
        
        # Establecer cantidad pendiente para todos
        for item in self.tree_productos.get_children():
            valores = list(self.tree_productos.item(item)['values'])
            pendiente = float(valores[5])
            valores[6] = f"{pendiente:.2f}"
            self.tree_productos.item(item, values=valores)
        
        messagebox.showinfo("Éxito", "Se marcó todo para entrega completa")
    
    def registrar_entrega(self):
        """Registra la entrega parcial en la base de datos"""
        
        # Recopilar productos a entregar
        productos_entregar = []
        for item in self.tree_productos.get_children():
            valores = self.tree_productos.item(item)['values']
            cantidad_entregar = float(valores[6])
            
            if cantidad_entregar > 0:
                productos_entregar.append({
                    'producto_id': valores[0],
                    'nombre': valores[2],
                    'cantidad': cantidad_entregar,
                    'stock_actual': float(valores[7])
                })
        
        if not productos_entregar:
            messagebox.showwarning("Advertencia", "Debes especificar cantidades a entregar")
            return
        
        # Confirmar
        mensaje = "Se entregarán los siguientes productos:\n\n"
        for prod in productos_entregar:
            mensaje += f"• {prod['nombre']}: {prod['cantidad']:.2f}\n"
        
        mensaje += f"\n¿Confirmar entrega?"
        
        if not messagebox.askyesno("Confirmar Entrega", mensaje):
            return
        
        try:
            fecha_entrega = datetime.now().strftime('%Y-%m-%d')
            notas = self.text_notas.get('1.0', 'end-1c').strip()
            
            # Registrar cada producto
            for prod in productos_entregar:
                # Insertar en entregas_parciales
                self.cursor.execute("""
                    INSERT INTO entregas_parciales 
                    (cotizacion_id, producto_id, cantidad_entregada, fecha_entrega, notas, usuario)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.cotizacion_id,
                    prod['producto_id'],
                    prod['cantidad'],
                    fecha_entrega,
                    notas,
                    sesion.nombre_display()
                ))
                
                # Obtener stock antes de descontar
                self.cursor.execute("SELECT stock_actual FROM productos WHERE id = ?",
                                    (prod['producto_id'],))
                _row = self.cursor.fetchone()
                _stock_antes = _row[0] if _row else 0

                # Descontar del stock
                self.cursor.execute("""
                    UPDATE productos
                    SET stock_actual = stock_actual - ?
                    WHERE id = ?
                """, (prod['cantidad'], prod['producto_id']))

                # Registrar salida en historial de stock
                self.cursor.execute("""
                    INSERT INTO movimientos_stock
                    (producto_id, tipo, motivo, cantidad,
                     stock_antes, stock_despues, referencia, notas)
                    VALUES (?, 'salida', 'Entrega de cotización', ?, ?, ?, ?, ?)
                """, (
                    prod['producto_id'],
                    prod['cantidad'],
                    _stock_antes,
                    _stock_antes - prod['cantidad'],
                    self.folio,
                    notas or None
                ))
            
            # Verificar si ya se entregó todo
            self.cursor.execute("""
                SELECT 
                    SUM(cd.cantidad) as total_cotizado,
                    SUM(COALESCE(ep.cantidad_entregada, 0)) as total_entregado
                FROM cotizacion_detalle cd
                LEFT JOIN (
                    SELECT producto_id, SUM(cantidad_entregada) as cantidad_entregada
                    FROM entregas_parciales
                    WHERE cotizacion_id = ?
                    GROUP BY producto_id
                ) ep ON cd.producto_id = ep.producto_id
                WHERE cd.cotizacion_id = ?
            """, (self.cotizacion_id, self.cotizacion_id))
            
            total_cotizado, total_entregado = self.cursor.fetchone()
            
            # Calcular monto acumulado entregado
            self.cursor.execute("""
                SELECT COALESCE(SUM(ep.cantidad_entregada * (cd.total / cd.cantidad)), 0)
                FROM entregas_parciales ep
                JOIN cotizacion_detalle cd
                    ON cd.cotizacion_id = ep.cotizacion_id
                    AND cd.producto_id  = ep.producto_id
                WHERE ep.cotizacion_id = ?
            """, (self.cotizacion_id,))
            monto_entregado = self.cursor.fetchone()[0] or 0

            # Actualizar estado de la cotización
            if total_entregado >= total_cotizado:
                # Entrega completa
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Entregada',
                        entrega_parcial = 0,
                        fecha_entrega = ?,
                        monto_entregado = ?
                    WHERE id = ?
                """, (fecha_entrega, monto_entregado, self.cotizacion_id))

                estado_msg = "completada"
            else:
                # Aún hay pendientes
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Parcialmente Entregada',
                        entrega_parcial = 1,
                        monto_entregado = ?
                    WHERE id = ?
                """, (monto_entregado, self.cotizacion_id))

                estado_msg = "parcial registrada"
            
            self.conn.commit()
            
            messagebox.showinfo(
                "Éxito",
                f"Entrega {estado_msg} correctamente\n\n" +
                f"Productos entregados: {len(productos_entregar)}\n" +
                f"Stock actualizado automáticamente"
            )
            
            self.ventana.destroy()
            
        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror("Error", f"No se pudo registrar la entrega:\n{str(e)}")

