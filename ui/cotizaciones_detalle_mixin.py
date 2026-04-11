# -*- coding: utf-8 -*-
"""
ui/cotizaciones_detalle_mixin.py
Mixin: ver detalle completo, vincular orden de compra, vincular factura.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

from ui.utils import centrar_ventana as _centrar


class _CotizacionesDetalleMixin:
    def ver_detalle_cotizacion(self):
        """Muestra el detalle completo de la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        
        # Obtener datos completos de la cotización
        self.cursor.execute("""
            SELECT 
                c.folio, c.fecha, c.orden_compra, c.fecha_orden_compra,
                cl.nombre_comercial, cl.tipo, cl.contacto, cl.telefono, cl.email,
                c.subtotal, c.iva, c.total, c.notas, c.estado,
                c.fecha_entrega, c.monto_entregado, c.monto_facturado, c.monto_pagado
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cotizacion_id,))
        
        cot = self.cursor.fetchone()
        if not cot:
            return
        
        (folio, fecha, oc, fecha_oc, cliente, tipo_cliente, contacto, telefono, email,
         subtotal, iva, total, notas, estado, fecha_entrega, monto_entregado, monto_facturado, monto_pagado) = cot
        
        # Obtener productos
        self.cursor.execute("""
            SELECT 
                p.codigo, p.nombre, cd.cantidad, cd.precio_unitario,
                cd.subtotal, cd.iva, cd.total, cd.tiene_stock
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
        """, (cotizacion_id,))
        
        productos = self.cursor.fetchall()
        
        # Ventana de detalle
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle - {folio}")
        ventana.geometry("900x700")
        ventana.minsize(820, 620)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.configure(bg='#f1f5f9')
        
        # Frame principal con scroll
        main_canvas = tk.Canvas(ventana, bg='#f1f5f9', highlightthickness=0)
        scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas, bg='#f1f5f9')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        # Contenido
        frame = tk.Frame(scrollable_frame, bg='#f1f5f9', padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        # === ENCABEZADO ===
        header_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        header_frame.pack(fill='x', pady=(0, 15))
        
        header_content = tk.Frame(header_frame, bg='white', padx=20, pady=15)
        header_content.pack(fill='x')
        
        tk.Label(
            header_content,
            text=folio,
            font=('Arial', 18, 'bold'),
            bg='white',
            fg='#2c3e50'
        ).pack(side='left')
        
        # Estado con color
        estado_colors = {
            'Pendiente': '#f39c12',
            'Programada': '#3498db',
            'Entregada': '#27ae60',
            'Facturada': '#9b59b6',
            'Pagada': '#16a085',
            'Cancelada': '#e74c3c'
        }
        
        estado_label = tk.Label(
            header_content,
            text=estado,
            font=('Arial', 12, 'bold'),
            bg=estado_colors.get(estado, '#6b7280'),
            fg='white',
            padx=15,
            pady=5
        )
        estado_label.pack(side='right')
        
        # === INFORMACIÓN DEL CLIENTE ===
        cliente_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        cliente_frame.pack(fill='x', pady=(0, 15))
        
        cliente_content = tk.Frame(cliente_frame, bg='white', padx=20, pady=15)
        cliente_content.pack(fill='both')
        
        tk.Label(
            cliente_content,
            text="📋 INFORMACIÓN DEL CLIENTE",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        
        info_cliente = [
            ("Cliente:", cliente),
            ("Tipo:", tipo_cliente),
            ("Contacto:", contacto or "N/A"),
            ("Teléfono:", telefono or "N/A"),
            ("Email:", email or "N/A")
        ]
        
        for i, (label, value) in enumerate(info_cliente, start=1):
            tk.Label(
                cliente_content,
                text=label,
                font=('Arial', 10, 'bold'),
                bg='white',
                fg='#6b7280'
            ).grid(row=i, column=0, sticky='w', pady=3, padx=(0, 10))
            
            tk.Label(
                cliente_content,
                text=value,
                font=('Arial', 10),
                bg='white',
                fg='#2c3e50'
            ).grid(row=i, column=1, sticky='w', pady=3)
        
        # === FECHAS Y O.C. ===
        fechas_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        fechas_frame.pack(fill='x', pady=(0, 15))
        
        fechas_content = tk.Frame(fechas_frame, bg='white', padx=20, pady=15)
        fechas_content.pack(fill='both')
        
        tk.Label(
            fechas_content,
            text="📅 FECHAS Y ORDEN DE COMPRA",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))
        
        info_fechas = [
            ("Fecha Cotización:", fecha),
            ("Orden de Compra:", oc or "Sin O.C."),
            ("Fecha O.C.:", fecha_oc or "N/A"),
            ("Fecha Entrega:", fecha_entrega or "Pendiente")
        ]
        
        for i, (label, value) in enumerate(info_fechas):
            col = (i % 2) * 2
            row = i // 2 + 1
            
            tk.Label(
                fechas_content,
                text=label,
                font=('Arial', 9, 'bold'),
                bg='white',
                fg='#6b7280'
            ).grid(row=row, column=col, sticky='w', pady=3, padx=(0, 5))
            
            tk.Label(
                fechas_content,
                text=value,
                font=('Arial', 9),
                bg='white',
                fg='#2c3e50'
            ).grid(row=row, column=col+1, sticky='w', pady=3, padx=(0, 20))
        
        # Calcular días transcurridos si hay O.C.
        if fecha_oc and estado not in ['Pagada', 'Cancelada']:
            try:
                fecha_oc_dt = datetime.strptime(fecha_oc, '%Y-%m-%d')
                dias_transcurridos = (datetime.now() - fecha_oc_dt).days
                dias_limite = 30
                dias_restantes = dias_limite - dias_transcurridos
                
                # Alerta de días
                if dias_restantes < 0:
                    color_dias = '#e74c3c'
                    texto_dias = f"⚠️ VENCIDA hace {abs(dias_restantes)} días"
                elif dias_restantes <= 5:
                    color_dias = '#f39c12'
                    texto_dias = f"⚠️ Quedan {dias_restantes} días para vencer"
                else:
                    color_dias = '#27ae60'
                    texto_dias = f"✓ Quedan {dias_restantes} días"
                
                tk.Label(
                    fechas_content,
                    text="Límite de pago (30 días):",
                    font=('Arial', 9, 'bold'),
                    bg='white',
                    fg='#6b7280'
                ).grid(row=3, column=0, sticky='w', pady=(10, 3), padx=(0, 5))
                
                tk.Label(
                    fechas_content,
                    text=texto_dias,
                    font=('Arial', 9, 'bold'),
                    bg='white',
                    fg=color_dias
                ).grid(row=3, column=1, columnspan=3, sticky='w', pady=(10, 3))
                
            except:
                pass
        
        # === PRODUCTOS ===
        productos_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        productos_frame.pack(fill='both', expand=True, pady=(0, 15))
        
        productos_content = tk.Frame(productos_frame, bg='white', padx=20, pady=15)
        productos_content.pack(fill='both', expand=True)
        
        tk.Label(
            productos_content,
            text="📦 PRODUCTOS",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).pack(anchor='w', pady=(0, 10))
        
        # Tabla de productos
        tree_frame = tk.Frame(productos_content, bg='white')
        tree_frame.pack(fill='both', expand=True)
        
        tree = ttk.Treeview(
            tree_frame,
            columns=('Código', 'Producto', 'Cant.', 'P.Unit.', 'Subtotal', 'IVA', 'Total', 'Stock'),
            show='headings',
            height=8
        )
        
        tree.heading('Código', text='Código')
        tree.heading('Producto', text='Producto')
        tree.heading('Cant.', text='Cant.')
        tree.heading('P.Unit.', text='P.Unit.')
        tree.heading('Subtotal', text='Subtotal')
        tree.heading('IVA', text='IVA')
        tree.heading('Total', text='Total')
        tree.heading('Stock', text='Stock')
        
        tree.column('Código', width=80)
        tree.column('Producto', width=250)
        tree.column('Cant.', width=60)
        tree.column('P.Unit.', width=90)
        tree.column('Subtotal', width=90)
        tree.column('IVA', width=70)
        tree.column('Total', width=90)
        tree.column('Stock', width=60)
        
        for prod in productos:
            stock_text = "✓" if prod[7] else "✗"
            tree.insert('', 'end', values=(
                prod[0], prod[1], f"{prod[2]:.2f}",
                f"${prod[3]:,.2f}", f"${prod[4]:,.2f}",
                f"${prod[5]:,.2f}", f"${prod[6]:,.2f}", stock_text
            ))
        
        scroll = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        
        tree.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        
        # === TOTALES ===
        totales_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        totales_frame.pack(fill='x', pady=(0, 15))
        
        totales_content = tk.Frame(totales_frame, bg='white', padx=20, pady=15)
        totales_content.pack(fill='x')
        
        totales_info = [
            ("Subtotal:", subtotal, '#34495e'),
            ("IVA:", iva, '#6b7280'),
            ("TOTAL:", total, '#e74c3c')
        ]
        
        for label, monto, color in totales_info:
            row = tk.Frame(totales_content, bg='white')
            row.pack(fill='x', pady=2)
            
            size = 14 if label == "TOTAL:" else 11
            weight = 'bold' if label == "TOTAL:" else 'normal'
            
            tk.Label(
                row,
                text=label,
                font=('Arial', size, weight),
                bg='white',
                fg=color
            ).pack(side='right', padx=5)
            
            tk.Label(
                row,
                text=f"${monto:,.2f}",
                font=('Arial', size, weight),
                bg='white',
                fg=color
            ).pack(side='right')
        
        # === MONTOS ===
        montos_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
        montos_frame.pack(fill='x', pady=(0, 15))
        
        montos_content = tk.Frame(montos_frame, bg='white', padx=20, pady=15)
        montos_content.pack(fill='x')
        
        tk.Label(
            montos_content,
            text="💰 SEGUIMIENTO DE MONTOS",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg='#34495e'
        ).pack(anchor='w', pady=(0, 10))
        
        montos_info = [
            ("Monto Entregado:", monto_entregado),
            ("Monto Facturado:", monto_facturado),
            ("Monto Pagado:", monto_pagado),
            ("Pendiente de Pago:", total - monto_pagado)
        ]
        
        for label, monto in montos_info:
            row = tk.Frame(montos_content, bg='white')
            row.pack(fill='x', pady=3)
            
            tk.Label(
                row,
                text=label,
                font=('Arial', 10),
                bg='white',
                fg='#6b7280'
            ).pack(side='left')
            
            color = '#27ae60' if monto == total and label == "Monto Pagado:" else '#2c3e50'
            tk.Label(
                row,
                text=f"${monto:,.2f}",
                font=('Arial', 10, 'bold'),
                bg='white',
                fg=color
            ).pack(side='right')
        
        # === NOTAS ===
        if notas:
            notas_frame = tk.Frame(frame, bg='white', relief='raised', bd=2)
            notas_frame.pack(fill='x')
            
            notas_content = tk.Frame(notas_frame, bg='white', padx=20, pady=15)
            notas_content.pack(fill='both')
            
            tk.Label(
                notas_content,
                text="📝 NOTAS",
                font=('Arial', 12, 'bold'),
                bg='white',
                fg='#34495e'
            ).pack(anchor='w', pady=(0, 5))
            
            tk.Label(
                notas_content,
                text=notas,
                font=('Arial', 10),
                bg='white',
                fg='#2c3e50',
                wraplength=800,
                justify='left'
            ).pack(anchor='w')
        
        # Botón cerrar
        btn_frame = tk.Frame(frame, bg='#f1f5f9')
        btn_frame.pack(pady=15)
        
        tk.Button(
            btn_frame,
            text="Cerrar",
            command=ventana.destroy,
            bg='#6b7280',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=40,
            pady=12,
            relief='flat'
        ).pack()
        
        ventana.transient(self.root)
    
    def vincular_orden_compra(self):
        """Vincula una orden de compra a la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        oc_actual = item['values'][4]
        
        # Ventana para ingresar OC
        ventana = tk.Toplevel(self.root)
        ventana.title(f"🔗 Vincular Orden de Compra - {folio}")
        ventana.geometry("600x500")
        ventana.minsize(520, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        
        # Frame principal con padding
        frame_main = tk.Frame(ventana, bg='#f1f5f9', padx=20, pady=20)
        frame_main.pack(fill='both', expand=True)
        
        # Frame contenedor blanco
        frame = tk.Frame(frame_main, bg='white', relief='raised', bd=2)
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Frame interno con padding
        frame_content = tk.Frame(frame, bg='white', padx=30, pady=25)
        frame_content.pack(fill='both', expand=True)
        
        # Título
        tk.Label(
            frame_content,
            text=f"Cotización: {folio}",
            font=('Arial', 14, 'bold'),
            bg='white',
            fg='#2c3e50'
        ).pack(pady=(0, 10))
        
        if oc_actual != 'Sin O.C.':
            tk.Label(
                frame_content,
                text=f"O.C. actual: {oc_actual}",
                font=('Arial', 10),
                fg='#6b7280',
                bg='white'
            ).pack(pady=(0, 15))
        
        # Separador
        ttk.Separator(frame_content, orient='horizontal').pack(fill='x', pady=15)
        
        # Campo de O.C.
        label_oc = tk.Label(
            frame_content,
            text="Número de Orden de Compra *",
            font=('Arial', 10, 'bold'),
            bg='white',
            fg='#34495e'
        )
        label_oc.pack(anchor='w', pady=(5, 5))
        
        entry_oc = tk.Entry(
            frame_content,
            font=('Arial', 11),
            relief='solid',
            bd=1,
            highlightthickness=1,
            highlightbackground='#bdc3c7',
            highlightcolor='#3498db'
        )
        entry_oc.pack(fill='x', ipady=8, pady=(0, 15))
        
        if oc_actual != 'Sin O.C.':
            entry_oc.insert(0, oc_actual)
        
        entry_oc.focus()
        
        # Campo de fecha
        label_fecha = tk.Label(
            frame_content,
            text="Fecha de O.C. (opcional)",
            font=('Arial', 10, 'bold'),
            bg='white',
            fg='#34495e'
        )
        label_fecha.pack(anchor='w', pady=(5, 5))
        
        entry_fecha = tk.Entry(
            frame_content,
            font=('Arial', 11),
            relief='solid',
            bd=1,
            highlightthickness=1,
            highlightbackground='#bdc3c7',
            highlightcolor='#3498db'
        )
        entry_fecha.pack(fill='x', ipady=8)
        entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        # Ayuda
        tk.Label(
            frame_content,
            text="📅 Formato: AAAA-MM-DD (ejemplo: 2026-02-12)",
            font=('Arial', 8, 'italic'),
            fg='#6b7280',
            bg='white'
        ).pack(anchor='w', pady=(3, 0))
        
        # Frame de botones
        frame_btn = tk.Frame(frame_content, bg='white')
        frame_btn.pack(pady=(25, 10))
        
        def guardar():
            numero_oc = entry_oc.get().strip()
            fecha_oc = entry_fecha.get().strip()
            
            if not numero_oc:
                messagebox.showwarning("Advertencia", "Ingresa el número de O.C.", parent=ventana)
                entry_oc.focus()
                return
            
            try:
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET orden_compra = ?,
                        fecha_orden_compra = ?
                    WHERE id = ?
                """, (numero_oc, fecha_oc if fecha_oc else None, cotizacion_id))

                # Sincronizar referencia de OC con seguimiento_etapas
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas (cotizacion_id, etapa, completada, referencia, fecha_etapa)
                    VALUES (?, 'Orden de Compra', 1, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada = 1,
                        referencia = excluded.referencia,
                        fecha_etapa = excluded.fecha_etapa
                """, (cotizacion_id, numero_oc, fecha_oc if fecha_oc else None))
                
                self.conn.commit()
                messagebox.showinfo("Éxito", f"✓ O.C. {numero_oc} vinculada correctamente", parent=ventana)
                self.cargar_cotizaciones()
                ventana.destroy()
                
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo vincular:\n{str(e)}", parent=ventana)
        
        # Vincular Enter a guardar
        entry_oc.bind('<Return>', lambda e: guardar())
        entry_fecha.bind('<Return>', lambda e: guardar())
        
        tk.Button(
            frame_btn,
            text="💾 Guardar",
            command=guardar,
            bg='#27ae60',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=30,
            pady=12,
            relief='flat',
            activebackground='#229954'
        ).pack(side='left', padx=5)
        
        tk.Button(
            frame_btn,
            text="❌ Cancelar",
            command=ventana.destroy,
            bg='#6b7280',
            fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2',
            padx=30,
            pady=12,
            relief='flat',
            activebackground='#6b7280'
        ).pack(side='left', padx=5)
        
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def ver_detalle_cotizacion(self):
        """Muestra el detalle completo de la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        
        # Obtener datos completos
        self.cursor.execute("""
            SELECT c.folio, c.fecha, cl.nombre_comercial, cl.tipo, c.orden_compra,
                   c.fecha_orden_compra, c.subtotal, c.iva, c.total, c.estado,
                   c.notas, c.fecha_entrega, c.monto_entregado, c.monto_facturado,
                   c.monto_pagado, cl.contacto, cl.telefono, cl.email, cl.rfc
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cotizacion_id,))

        cotizacion = self.cursor.fetchone()
        if not cotizacion:
            return

        (folio, fecha, cliente, tipo_cliente, orden_compra, fecha_oc,
         subtotal, iva, total, estado, notas, fecha_entrega,
         monto_entregado, monto_facturado, monto_pagado,
         contacto, telefono, email, rfc_cliente) = cotizacion
        
        # Obtener productos
        self.cursor.execute("""
            SELECT p.codigo, p.nombre, cd.cantidad, cd.precio_unitario, 
                   cd.subtotal, cd.iva, cd.total, cd.tiene_stock
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
        """, (cotizacion_id,))
        
        productos = self.cursor.fetchall()
        
        # Ventana
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Detalle - {folio}")
        ventana.geometry("900x700")
        ventana.minsize(820, 620)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.configure(bg='#f1f5f9')
        
        # Scroll
        canvas = tk.Canvas(ventana, bg='#f1f5f9')
        scrollbar = ttk.Scrollbar(ventana, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f1f5f9')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        frame_content = tk.Frame(scrollable_frame, bg='#f1f5f9', padx=20, pady=20)
        frame_content.pack(fill='both', expand=True)
        
        # Info General
        frame_general = tk.LabelFrame(frame_content, text="Información General", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
        frame_general.pack(fill='x', pady=(0, 15))
        
        info_general = [
            ("Folio:", folio),
            ("Fecha:", fecha),
            ("Estado:", estado),
            ("O.C.:", orden_compra or 'Sin O.C.'),
            ("Fecha O.C.:", fecha_oc or 'N/A')
        ]
        
        for label, valor in info_general:
            frame_item = tk.Frame(frame_general, bg='white')
            frame_item.pack(fill='x', pady=3)
            tk.Label(frame_item, text=label, font=('Arial', 9, 'bold'), bg='white', width=12, anchor='w').pack(side='left')
            tk.Label(frame_item, text=valor, font=('Arial', 9), bg='white').pack(side='left')
        
        # Cliente
        frame_cliente = tk.LabelFrame(frame_content, text="Cliente", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
        frame_cliente.pack(fill='x', pady=(0, 15))
        
        info_cliente = [
            ("Nombre:", cliente),
            ("Tipo:", tipo_cliente),
            ("Contacto:", contacto or 'N/A'),
            ("Teléfono:", telefono or 'N/A')
        ]
        
        for label, valor in info_cliente:
            frame_item = tk.Frame(frame_cliente, bg='white')
            frame_item.pack(fill='x', pady=3)
            tk.Label(frame_item, text=label, font=('Arial', 9, 'bold'), bg='white', width=12, anchor='w').pack(side='left')
            tk.Label(frame_item, text=valor, font=('Arial', 9), bg='white').pack(side='left')
        
        # Productos
        frame_productos = tk.LabelFrame(frame_content, text="Productos", font=('Arial', 11, 'bold'), bg='white', padx=10, pady=10)
        frame_productos.pack(fill='both', expand=True, pady=(0, 15))
        
        tree_productos = ttk.Treeview(
            frame_productos,
            columns=('Código', 'Producto', 'Cantidad', 'Precio', 'Total'),
            show='headings',
            height=8
        )
        
        for col in ('Código', 'Producto', 'Cantidad', 'Precio', 'Total'):
            tree_productos.heading(col, text=col)
        
        tree_productos.column('Código', width=80)
        tree_productos.column('Producto', width=300)
        tree_productos.column('Cantidad', width=100)
        tree_productos.column('Precio', width=120)
        tree_productos.column('Total', width=120)
        
        for prod in productos:
            tree_productos.insert('', 'end', values=(
                prod[0], prod[1], f"{prod[2]:.2f}",
                f"${prod[3]:,.2f}", f"${prod[6]:,.2f}"
            ))
        
        tree_productos.pack(fill='both', expand=True)
        
        # Totales
        frame_totales = tk.Frame(frame_content, bg='white', relief='raised', bd=2, padx=20, pady=15)
        frame_totales.pack(fill='x', pady=(0, 15))
        
        tk.Label(frame_totales, text=f"Subtotal: ${subtotal:,.2f}", font=('Arial', 10), bg='white').pack(anchor='e')
        tk.Label(frame_totales, text=f"IVA: ${iva:,.2f}", font=('Arial', 10), bg='white').pack(anchor='e')
        tk.Label(frame_totales, text=f"TOTAL: ${total:,.2f}", font=('Arial', 14, 'bold'), bg='white', fg='#e74c3c').pack(anchor='e')
        
        # Seguimiento
        dias_oc = "N/A"
        if fecha_oc:
            try:
                fecha_oc_dt = datetime.strptime(fecha_oc, '%Y-%m-%d')
                dias_transcurridos = (datetime.now() - fecha_oc_dt).days
                dias_oc = f"{dias_transcurridos} días"
                if dias_transcurridos > 30:
                    dias_oc += " ⚠️"
            except:
                pass
        
        frame_seg = tk.LabelFrame(frame_content, text="Seguimiento", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
        frame_seg.pack(fill='x', pady=(0, 15))
        
        seguimiento_info = [
            ("Días desde O.C.:", dias_oc),
            ("Monto Entregado:", f"${monto_entregado:,.2f}"),
            ("Monto Pagado:", f"${monto_pagado:,.2f}")
        ]
        
        for label, valor in seguimiento_info:
            frame_item = tk.Frame(frame_seg, bg='white')
            frame_item.pack(fill='x', pady=3)
            tk.Label(frame_item, text=label, font=('Arial', 9, 'bold'), bg='white', width=18, anchor='w').pack(side='left')
            tk.Label(frame_item, text=valor, font=('Arial', 9), bg='white').pack(side='left')
        
        if notas:
            frame_notas = tk.LabelFrame(frame_content, text="Notas", font=('Arial', 11, 'bold'), bg='white', padx=20, pady=15)
            frame_notas.pack(fill='x', pady=(0, 15))
            tk.Label(frame_notas, text=notas, font=('Arial', 9), bg='white', justify='left', wraplength=800).pack()
        
        # === FACTURAS VINCULADAS ===
        frame_facturas_cont = tk.LabelFrame(
            frame_content, text="📎 Facturas Vinculadas",
            font=('Arial', 11, 'bold'), bg='white', padx=10, pady=10)
        frame_facturas_cont.pack(fill='x', pady=(0, 15))

        _tipo_map_fac  = {'I': '📥 Ingreso', 'E': '📤 Egreso',
                          'P': '💳 Pago',   'N': '📋 Nómina', 'T': '🔄 Traslado'}
        _tipo_color    = {'I': '#1a4b8c', 'E': '#c0392b'}
        _tipo_bg       = {'I': '#eff6ff',  'E': '#fff1f2'}

        def _build_facturas_section():
            for w in frame_facturas_cont.winfo_children():
                w.destroy()
            self.cursor.execute("""
                SELECT f.id, f.serie, f.folio_factura, f.tipo, f.total, f.fecha, f.uuid
                FROM facturas f
                JOIN factura_cotizaciones fc ON fc.factura_id = f.id
                WHERE fc.cotizacion_id = ?
                ORDER BY f.tipo, f.fecha
            """, (cotizacion_id,))
            vinculadas = self.cursor.fetchall()
            if vinculadas:
                for fid, serie, folio_f, tipo, ftotal, ffecha, uuid in vinculadas:
                    sf = f"{serie}-{folio_f}" if serie else (folio_f or (uuid or '')[:8])
                    color  = _tipo_color.get(tipo, '#374151')
                    bgc    = _tipo_bg.get(tipo, '#f9fafb')
                    tipo_t = _tipo_map_fac.get(tipo, tipo)
                    row = tk.Frame(frame_facturas_cont, bg=bgc, pady=3)
                    row.pack(fill='x', padx=4, pady=2)
                    tk.Label(row, text=tipo_t, font=('Arial', 9, 'bold'),
                             bg=bgc, fg=color, width=14, anchor='w').pack(side='left', padx=(8, 4))
                    tk.Label(row, text=sf, font=('Arial', 9),
                             bg=bgc, fg='#1e2d45', width=14).pack(side='left', padx=4)
                    tk.Label(row, text=f"${ftotal:,.2f}" if ftotal else '$0.00',
                             font=('Arial', 9, 'bold'), bg=bgc, fg=color).pack(side='left', padx=4)
                    tk.Label(row, text=(ffecha or '')[:10],
                             font=('Arial', 8), bg=bgc, fg='#6b7280').pack(side='left', padx=8)
            else:
                tk.Label(frame_facturas_cont, text="Sin facturas vinculadas",
                         font=('Arial', 9, 'italic'), bg='white', fg='#9ca3af').pack(anchor='w', padx=4, pady=4)

            tk.Button(frame_facturas_cont, text="🔗 Vincular Factura",
                      command=lambda: self._vincular_factura_a_cot(
                          cotizacion_id, rfc_cliente, _build_facturas_section, ventana),
                      bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=10, pady=4, relief='flat').pack(anchor='w', padx=4, pady=(8, 2))

        _build_facturas_section()

        tk.Button(frame_content, text="Cerrar", command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 11, 'bold'),
                  padx=30, pady=10).pack(pady=10)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

    def _vincular_factura_a_cot(self, cotizacion_id, rfc_cliente, on_refresh=None, parent_win=None):
        """Diálogo simple para vincular una factura directamente desde el detalle de cotización."""
        dlg = tk.Toplevel(parent_win or self.root)
        dlg.withdraw()
        dlg.title("🔗 Vincular Factura")
        dlg.geometry("880x460")
        _centrar(dlg, parent_win or self.root)
        dlg.configure(bg='#f1f5f9')
        dlg.transient(parent_win or self.root)
        dlg.grab_set()
        dlg.resizable(True, True)

        # Header
        hdr = tk.Frame(dlg, bg='#1a4b8c', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text="🔗  Vincular Factura a Cotización",
                 font=('Arial', 11, 'bold'), bg='#1a4b8c', fg='white').pack(side='left', padx=12)
        if rfc_cliente:
            tk.Label(hdr, text=f"RFC cliente: {rfc_cliente}",
                     font=('Arial', 8), bg='#1a4b8c', fg='#93c5fd').pack(side='right', padx=12)

        # Barra de búsqueda y filtro
        sf = tk.Frame(dlg, bg='#f1f5f9', pady=6)
        sf.pack(fill='x', padx=12)
        tk.Label(sf, text="🔍", font=('Arial', 10), bg='#f1f5f9').pack(side='left')
        entry_bus = tk.Entry(sf, font=('Arial', 9), width=28, relief='solid', bd=1)
        entry_bus.pack(side='left', padx=6)
        var_todas = tk.BooleanVar(value=not bool(rfc_cliente))
        tk.Checkbutton(sf, text="Mostrar todas (sin filtrar por RFC del cliente)",
                       variable=var_todas, bg='#f1f5f9', font=('Arial', 8),
                       command=lambda: _cargar(entry_bus.get())).pack(side='left', padx=8)

        # Footer (pack antes que la tabla para que quede siempre visible)
        foot = tk.Frame(dlg, bg='#e8edf4', pady=8)
        foot.pack(side='bottom', fill='x')

        def _vincular():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Sin selección", "Selecciona una factura de la lista.", parent=dlg)
                return
            fac_id = int(tree.item(sel[0])['values'][0])
            self.cursor.execute("SELECT uuid, fecha FROM facturas WHERE id=?", (fac_id,))
            row = self.cursor.fetchone()
            if not row:
                return
            uuid, fecha_fac = row
            if hasattr(self.sistema, '_facturacion'):
                self.sistema._facturacion._vincular_factura_a_cotizacion(
                    fac_id, cotizacion_id, uuid, fecha_fac)
            else:
                try:
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO factura_cotizaciones (factura_id, cotizacion_id)
                        VALUES (?,?)
                    """, (fac_id, cotizacion_id))
                    self.cursor.execute("""
                        INSERT INTO seguimiento_etapas
                            (cotizacion_id, etapa, completada, referencia, fecha_etapa)
                        VALUES (?, 'Facturada', 1, ?, ?)
                        ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                            completada=1, referencia=excluded.referencia,
                            fecha_etapa=excluded.fecha_etapa
                    """, (cotizacion_id, uuid, (fecha_fac or '')[:10]))
                    self.conn.commit()
                    messagebox.showinfo("Éxito", "Factura vinculada.", parent=dlg)
                except sqlite3.Error as e:
                    self.conn.rollback()
                    messagebox.showerror("Error", str(e), parent=dlg)
                    return
            if on_refresh:
                on_refresh()
            dlg.destroy()

        tk.Button(foot, text="✅ Vincular seleccionada", command=_vincular,
                  bg='#16a34a', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=14, pady=5, relief='flat').pack(side='left', padx=12)
        tk.Button(foot, text="Cancelar", command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=12, pady=5, relief='flat').pack(side='right', padx=12)

        # Tabla de facturas
        cols = ('_id', 'Tipo', 'Serie-Folio', 'Total', 'Fecha', 'RFC Receptor')
        frm_tree = tk.Frame(dlg, bg='#f1f5f9')
        frm_tree.pack(fill='both', expand=True, padx=12, pady=(0, 4))
        tree = ttk.Treeview(frm_tree, columns=cols, show='headings',
                             height=10, selectmode='browse')
        tree.column('_id',         width=0,   stretch=False)
        tree.column('Tipo',        width=110)
        tree.column('Serie-Folio', width=120)
        tree.column('Total',       width=110, anchor='e')
        tree.column('Fecha',       width=90)
        tree.column('RFC Receptor',width=180)
        for col in cols[1:]:
            tree.heading(col, text=col)
        tree.tag_configure('ingreso', foreground='#1a4b8c')
        tree.tag_configure('egreso',  foreground='#c0392b')
        sc_y = ttk.Scrollbar(frm_tree, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sc_y.set)
        sc_y.pack(side='right', fill='y')
        tree.pack(fill='both', expand=True)
        tree.bind('<Double-1>', lambda e: _vincular())

        tipo_map_d = {'I': '📥 Ingreso', 'E': '📤 Egreso',
                      'P': '💳 Pago',   'N': '📋 Nómina', 'T': '🔄 Traslado'}

        def _cargar(buscar=''):
            tree.delete(*tree.get_children())
            like = f'%{buscar}%'
            if not var_todas.get() and rfc_cliente:
                self.cursor.execute("""
                    SELECT f.id, f.tipo, f.serie, f.folio_factura,
                           f.total, f.fecha, f.rfc_receptor
                    FROM facturas f
                    WHERE UPPER(f.rfc_receptor) = UPPER(?)
                      AND f.id NOT IN (
                          SELECT factura_id FROM factura_cotizaciones
                          WHERE cotizacion_id = ?)
                      AND f.tipo IN ('I','E')
                      AND (f.folio_factura LIKE ? OR COALESCE(f.serie,'') LIKE ?
                           OR f.uuid LIKE ?)
                    ORDER BY f.tipo, f.fecha DESC
                """, (rfc_cliente, cotizacion_id, like, like, like))
            else:
                self.cursor.execute("""
                    SELECT f.id, f.tipo, f.serie, f.folio_factura,
                           f.total, f.fecha, f.rfc_receptor
                    FROM facturas f
                    WHERE f.id NOT IN (
                              SELECT factura_id FROM factura_cotizaciones
                              WHERE cotizacion_id = ?)
                      AND f.tipo IN ('I','E')
                      AND (f.folio_factura LIKE ? OR COALESCE(f.serie,'') LIKE ?
                           OR f.uuid LIKE ?)
                    ORDER BY f.tipo, f.fecha DESC
                """, (cotizacion_id, like, like, like))
            for row in self.cursor.fetchall():
                fid, tipo, serie, folio_f, ftotal, ffecha, rfc_rec = row
                sf_disp = f"{serie}-{folio_f}" if serie else (folio_f or '—')
                tag = 'ingreso' if tipo == 'I' else ('egreso' if tipo == 'E' else '')
                tree.insert('', 'end', tags=(tag,), values=(
                    fid,
                    tipo_map_d.get(tipo, tipo),
                    sf_disp,
                    f"${ftotal:,.2f}" if ftotal else '$0.00',
                    (ffecha or '')[:10],
                    rfc_rec or '—',
                ))

        entry_bus.bind('<KeyRelease>', lambda e: _cargar(entry_bus.get()))
        _cargar()

    # (removed - rebuilt in new ERP UI)

