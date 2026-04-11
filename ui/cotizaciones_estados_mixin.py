# -*- coding: utf-8 -*-
"""
ui/cotizaciones_estados_mixin.py
Mixin: generación PDF avanzada, nota de remisión, cambio de estado, marcar pagada/entregada.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os
import shutil
from datetime import datetime

from ui.generador_pdf_cly import GeneradorPDFCLY
from ui.dialogo_impresion import DialogoImpresion
from modules.entregas import VentanaEntregaParcial
from ui.utils import centrar_ventana as _centrar, campo_error as _campo_error


class _CotizacionesEstadosMixin:
    def generar_pdf_cotizacion_nueva(self):
        """Genera PDF de cotización con nuevo formato CLY (con opción de impresión parcial)"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return

        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]

        # Mostrar diálogo de impresión (completa o parcial)
        dlg = DialogoImpresion(self.root, self.conn, cotizacion_id, tipo='cotizacion')
        dlg.ventana.wait_window()

        if dlg.resultado is None:
            return  # Cancelado

        try:
            generador = GeneradorPDFCLY()
            if dlg.resultado == 'completa':
                archivo = generador.generar_cotizacion(self.conn, cotizacion_id)
            else:
                archivo = generador.generar_cotizacion(
                    self.conn, cotizacion_id,
                    productos_override=dlg.productos_para_pdf,
                    totales_override=dlg.totales_para_pdf
                )

            if archivo:
                messagebox.showinfo("Éxito", f"PDF generado: {archivo}")
                os.startfile(archivo) if os.name == 'nt' else os.system(f'open "{archivo}"')
            else:
                messagebox.showerror("Error", "No se pudo generar el PDF")

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar PDF:\n{str(e)}")
    
    def generar_nota_remision(self):
        """Genera nota de remisión para la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        estado = item['values'][5]
        
        # Verificar que esté programada o entregada
        if estado not in ['Programada', 'Entregada', 'Parcialmente Entregada']:
            respuesta = messagebox.askyesno(
                "Advertencia",
                f"La cotización está en estado '{estado}'.\n\n" +
                "Se recomienda generar nota de remisión solo para cotizaciones Programadas.\n\n" +
                "¿Deseas continuar de todos modos?"
            )
            if not respuesta:
                return
        
        # Mostrar diálogo de impresión (completa o parcial)
        dlg = DialogoImpresion(self.root, self.conn, cotizacion_id, tipo='remision')
        dlg.ventana.wait_window()

        if dlg.resultado is None:
            return  # Cancelado

        try:
            generador = GeneradorPDFCLY()
            if dlg.resultado == 'completa':
                archivo = generador.generar_nota_remision(self.conn, cotizacion_id)
            else:
                archivo = generador.generar_nota_remision(
                    self.conn, cotizacion_id,
                    productos_override=dlg.productos_para_pdf,
                    totales_override=dlg.totales_para_pdf
                )

            if archivo:
                messagebox.showinfo("Éxito", f"Nota de remisión generada: {archivo}")
                os.startfile(archivo) if os.name == 'nt' else os.system(f'open "{archivo}"')
            else:
                messagebox.showerror("Error", "No se pudo generar la nota")
                
        except Exception as e:
            messagebox.showerror("Error", f"Error al generar nota:\n{str(e)}")
    
    def cambiar_estado_rapido(self, nuevo_estado):
        """Cambia el estado de la cotización seleccionada.
        Solo permite: Pendiente, Programada, Cancelada.
        (Entrega parcial/completa tienen sus propias funciones.)
        """
        ESTADOS_PERMITIDOS = {'Pendiente', 'Programada', 'Cancelada',
                              'Parcialmente Entregada', 'Entregada'}
        if nuevo_estado not in ESTADOS_PERMITIDOS:
            messagebox.showwarning("Estado no válido",
                f"'{nuevo_estado}' ya no es un estado de cotización válido.\n\n"
                "Los estados disponibles son: Pendiente, Programada, Entregada Parcialmente, "
                "Entregada por completo y Cancelada.\n\n"
                "Para registrar OC, Factura o Pago usa la sección de Seguimiento.")
            return

        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == nuevo_estado:
            messagebox.showinfo("Info", f"La cotización ya está en estado '{nuevo_estado}'")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar cambio",
            f"¿Cambiar estado de {folio}?\n\n" +
            f"De: {estado_actual}\n" +
            f"A: {nuevo_estado}"
        )
        
        if respuesta:
            try:
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = ?
                    WHERE id = ?
                """, (nuevo_estado, cotizacion_id))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, nuevo_estado)
                
                self.conn.commit()
                
                # Si cambió a Programada, preguntar si quiere generar nota de remisión
                if nuevo_estado == 'Programada':
                    generar_nota = messagebox.askyesno(
                        "Generar Nota de Remisión",
                        f"Cotización marcada como {nuevo_estado}.\n\n" +
                        "¿Deseas generar la Nota de Remisión ahora?"
                    )
                    
                    if generar_nota:
                        generador = GeneradorPDFCLY()
                        archivo = generador.generar_nota_remision(self.conn, cotizacion_id)
                        if archivo:
                            messagebox.showinfo("Éxito", f"Nota generada: {archivo}")
                            import os
                            os.startfile(archivo) if os.name == 'nt' else os.system(f'open "{archivo}"')
                else:
                    messagebox.showinfo("Éxito", f"Estado cambiado a {nuevo_estado}")
                
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo cambiar el estado:\n{str(e)}")
    
    def marcar_facturada(self):
        """Registra la factura de una cotización"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede facturar una cotización cancelada")
            return
        
        # Ventana de registro de factura
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Registrar Factura - {folio}")
        ventana.geometry("480x380")
        ventana.minsize(400, 300)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text=f"Cotización: {folio}", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        
        tk.Label(frame, text="Número de Factura:", font=('Arial', 10)).grid(
            row=1, column=0, sticky='w', pady=5)
        entry_num_factura = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_num_factura.grid(row=1, column=1, pady=5)
        entry_num_factura.focus()
        
        tk.Label(frame, text="Monto Facturado:", font=('Arial', 10)).grid(
            row=2, column=0, sticky='w', pady=5)
        
        # Obtener total de la cotización para pre-rellenar
        self.cursor.execute("SELECT total FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        total_cot = self.cursor.fetchone()[0]
        
        entry_monto = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_monto.grid(row=2, column=1, pady=5)
        entry_monto.insert(0, f"{total_cot:.2f}")
        
        tk.Label(frame, text="Fecha de Factura:", font=('Arial', 10)).grid(
            row=3, column=0, sticky='w', pady=5)
        entry_fecha = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_fecha.grid(row=3, column=1, pady=5)
        entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d'))
        lbl_err_fecha = tk.Label(frame, text='', font=('Arial', 8), fg='#dc2626',
                                 bg=frame.cget('bg'))
        lbl_err_fecha.grid(row=3, column=2, sticky='w', padx=4)
        
        tk.Label(frame, text="Notas:", font=('Arial', 10)).grid(
            row=4, column=0, sticky='nw', pady=5)
        text_notas = tk.Text(frame, width=18, height=3, font=('Arial', 10))
        text_notas.grid(row=4, column=1, pady=5)

        # Enter guarda (excepto dentro del Text de notas)
        entry_num_factura.bind('<Return>', lambda e: guardar_factura())
        entry_monto.bind('<Return>', lambda e: guardar_factura())
        entry_fecha.bind('<Return>', lambda e: guardar_factura())

        def guardar_factura():
            try:
                monto = float(entry_monto.get())
                fecha = entry_fecha.get().strip()
                num_factura = entry_num_factura.get().strip()
                notas = text_notas.get('1.0', 'end-1c').strip()
                
                if not fecha:
                    messagebox.showwarning("Advertencia", "Ingresa la fecha de factura", parent=ventana)
                    return
                
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Facturada',
                        monto_facturado = ?,
                        fecha_factura = ?,
                        numero_factura = CASE WHEN ? != '' THEN ? ELSE numero_factura END
                    WHERE id = ?
                """, (monto, fecha, num_factura, num_factura, cotizacion_id))

                # Sincronizar referencia de factura con seguimiento_etapas
                ref_fac = num_factura if num_factura else ''
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas (cotizacion_id, etapa, completada, referencia, fecha_etapa)
                    VALUES (?, 'Facturada', 1, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada = 1,
                        referencia = CASE WHEN excluded.referencia != '' THEN excluded.referencia ELSE referencia END,
                        fecha_etapa = excluded.fecha_etapa
                """, (cotizacion_id, ref_fac, fecha))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, 'Facturada', fecha)

                self.conn.commit()
                messagebox.showinfo("Éxito", f"Cotización {folio} marcada como Facturada", parent=ventana)
                ventana.destroy()
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except ValueError:
                _campo_error(entry_monto, lbl_err_monto, "Ingresa un número válido")
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e), parent=ventana)
        
        frame_btn = tk.Frame(frame)
        frame_btn.grid(row=5, column=0, columnspan=2, pady=15)
        
        tk.Button(frame_btn, text="💾 Guardar", command=guardar_factura,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(frame_btn, text="❌ Cancelar", command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def marcar_pagada(self):
        """Registra el pago de una cotización"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede registrar pago de una cotización cancelada")
            return
        
        # Ventana de registro de pago
        ventana = tk.Toplevel(self.root)
        ventana.title(f"Registrar Pago - {folio}")
        ventana.geometry("480x340")
        ventana.minsize(400, 260)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        
        frame = tk.Frame(ventana, padx=20, pady=20)
        frame.pack(fill='both', expand=True)
        
        tk.Label(frame, text=f"Cotización: {folio}", font=('Arial', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 10))
        
        # Obtener total y monto_pagado actual
        self.cursor.execute("SELECT total, monto_pagado FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        total_cot, pagado_actual = self.cursor.fetchone()
        pendiente = total_cot - (pagado_actual or 0)
        
        tk.Label(frame, text=f"Total: ${total_cot:,.2f}  |  Ya pagado: ${pagado_actual or 0:,.2f}  |  Pendiente: ${pendiente:,.2f}",
                 font=('Arial', 9), fg='#6b7280').grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))
        
        tk.Label(frame, text="Monto Pagado Ahora:", font=('Arial', 10)).grid(
            row=2, column=0, sticky='w', pady=5)
        entry_monto = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_monto.grid(row=2, column=1, pady=5)
        entry_monto.insert(0, f"{pendiente:.2f}")
        entry_monto.focus()
        lbl_err_monto = tk.Label(frame, text='', font=('Arial', 8), fg='#dc2626',
                                 bg=frame.cget('bg'))
        lbl_err_monto.grid(row=2, column=2, sticky='w', padx=4)
        
        tk.Label(frame, text="Fecha de Pago:", font=('Arial', 10)).grid(
            row=3, column=0, sticky='w', pady=5)
        entry_fecha = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_fecha.grid(row=3, column=1, pady=5)
        entry_fecha.insert(0, datetime.now().strftime('%Y-%m-%d'))
        
        tk.Label(frame, text="Referencia / Notas:", font=('Arial', 10)).grid(
            row=4, column=0, sticky='w', pady=5)
        entry_notas = tk.Entry(frame, width=25, font=('Arial', 10))
        entry_notas.grid(row=4, column=1, pady=5)

        # Enter guarda desde cualquier campo
        for _e in (entry_monto, entry_fecha, entry_notas):
            _e.bind('<Return>', lambda e: guardar_pago())

        def guardar_pago():
            try:
                monto_nuevo = float(entry_monto.get())
                fecha = entry_fecha.get().strip()

                if not fecha:
                    _campo_error(entry_fecha, lbl_err_fecha, "La fecha es obligatoria")
                    return

                nuevo_total_pagado = (pagado_actual or 0) + monto_nuevo

                # Obtener estado actual limpio (sin emoji) directo de la BD
                self.cursor.execute("SELECT estado FROM cotizaciones WHERE id=?", (cotizacion_id,))
                estado_db = self.cursor.fetchone()[0]

                # Si el pago cubre el total → Pagada; si no, mantener estado actual
                nuevo_estado = 'Pagada' if nuevo_total_pagado >= total_cot else estado_db

                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET monto_pagado = ?,
                        fecha_pago   = ?,
                        estado       = ?
                    WHERE id = ?
                """, (nuevo_total_pagado, fecha, nuevo_estado, cotizacion_id))

                # Siempre sincronizar etapa Pagada en seguimiento con monto parcial o total
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas
                        (cotizacion_id, etapa, completada, fecha_etapa, notas)
                    VALUES (?, 'Pagada', ?, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada  = excluded.completada,
                        fecha_etapa = COALESCE(excluded.fecha_etapa, fecha_etapa),
                        notas       = COALESCE(excluded.notas, seguimiento_etapas.notas)
                """, (cotizacion_id,
                      1 if nuevo_estado == 'Pagada' else 0,
                      fecha,
                      f'Pago parcial ${monto_nuevo:,.2f}' if nuevo_estado != 'Pagada' else None))

                self.conn.commit()

                if nuevo_estado == 'Pagada':
                    msg = f"Cotización {folio} marcada como PAGADA completamente."
                else:
                    msg = (f"Pago de ${monto_nuevo:,.2f} registrado.\n"
                           f"Total pagado: ${nuevo_total_pagado:,.2f} de ${total_cot:,.2f}\n"
                           f"Pendiente: ${total_cot - nuevo_total_pagado:,.2f}")

                messagebox.showinfo("Éxito", msg, parent=ventana)
                ventana.destroy()
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()

            except ValueError:
                messagebox.showwarning("Advertencia", "El monto debe ser un número válido", parent=ventana)
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e), parent=ventana)
        
        frame_btn = tk.Frame(frame)
        frame_btn.grid(row=5, column=0, columnspan=2, pady=15)
        
        tk.Button(frame_btn, text="💾 Registrar Pago", command=guardar_pago,
                  bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        tk.Button(frame_btn, text="❌ Cancelar", command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=15, pady=6).pack(side='left', padx=5)
        
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def marcar_entregada_completa(self):
        """Marca la cotización como entregada completamente"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede entregar una cotización cancelada")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar entrega",
            f"¿Marcar como entregada completamente?\n\n" +
            f"Cotización: {folio}\n\n" +
            "Se descontará del inventario."
        )
        
        if respuesta:
            try:
                # Obtener productos
                self.cursor.execute("""
                    SELECT producto_id, cantidad
                    FROM cotizacion_detalle
                    WHERE cotizacion_id = ?
                """, (cotizacion_id,))
                
                productos = self.cursor.fetchall()
                
                # Descontar stock y registrar movimiento
                for producto_id, cantidad in productos:
                    self.cursor.execute(
                        "SELECT stock_actual FROM productos WHERE id = ?",
                        (producto_id,))
                    _row = self.cursor.fetchone()
                    _stock_antes = _row[0] if _row else 0

                    self.cursor.execute("""
                        UPDATE productos
                        SET stock_actual = stock_actual - ?
                        WHERE id = ?
                    """, (cantidad, producto_id))

                    self.cursor.execute("""
                        INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad,
                         stock_antes, stock_despues, referencia)
                        VALUES (?, 'salida', 'Entrega de cotización', ?,
                                ?, ?, ?)
                    """, (producto_id, cantidad,
                          _stock_antes, _stock_antes - cantidad, folio))

                # Actualizar cotización
                fecha_entrega = datetime.now().strftime('%Y-%m-%d')
                self.cursor.execute("""
                    SELECT total FROM cotizaciones WHERE id = ?
                """, (cotizacion_id,))
                total = self.cursor.fetchone()[0]

                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Entregada',
                        fecha_entrega = ?,
                        monto_entregado = ?,
                        entrega_parcial = 0
                    WHERE id = ?
                """, (fecha_entrega, total, cotizacion_id))

                # ── Sincronizar seguimiento_etapas ──────────────────────────
                self._sync_seguimiento_desde_estado(cotizacion_id, 'Entregada', fecha_entrega)

                self.conn.commit()
                messagebox.showinfo("Éxito", "Cotización marcada como entregada\nStock actualizado")
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo marcar como entregada:\n{str(e)}")
    
    def marcar_entregada_parcial(self):
        """Abre ventana para marcar entrega parcial de productos"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        estado = item['values'][5]
        
        # Verificar que esté en estado Programada o Parcialmente Entregada
        if estado not in ('Programada', 'Parcialmente Entregada'):
            messagebox.showwarning(
                "Estado no válido",
                "Solo se pueden registrar entregas parciales en cotizaciones con estado "
                "'Programada' o 'Parcialmente Entregada'.\n\n"
                f"Estado actual: {estado}"
            )
            return
        
        # Abrir ventana de entregas parciales y ESPERAR a que se cierre
        ventana_parcial = VentanaEntregaParcial(self.root, self.conn, self.cursor, cotizacion_id)
        self.root.wait_window(ventana_parcial.ventana)

        # Actualizar después de cerrar la ventana
        self.cargar_cotizaciones()
        self.sistema.actualizar_dashboard()
        # Refrescar stock si el módulo está cargado
        if hasattr(self, '_stock'):
            try:
                self.sistema._stock.cargar_vista_stock()
                self.sistema._stock.cargar_historial()
            except Exception:
                pass
    

    def _doble_clic_cotizacion(self, event):
        """Doble clic en el treeview:
        - Columna Observaciones → popup de edición rápida
        - Cualquier otra columna → abrir detalle de cotización
        """
        region = self.tree_cotizaciones.identify('region', event.x, event.y)
        if region != 'cell':
            return
        col_id  = self.tree_cotizaciones.identify_column(event.x)
        item_id = self.tree_cotizaciones.identify_row(event.y)
        if not item_id:
            return
        cols = self.tree_cotizaciones['columns']
        try:
            col_name = cols[int(col_id[1:]) - 1]
        except (IndexError, ValueError):
            col_name = ''

        if col_name == 'Observaciones':
            self._editar_observacion_rapida(item_id)
        else:
            self.ver_detalle_cotizacion()

    def _editar_observacion_rapida(self, item_id):
        """Popup pequeño para editar observaciones de una cotización."""
        vals   = self.tree_cotizaciones.item(item_id)['values']
        cot_id = vals[0]
        folio  = vals[1]
        obs_actual = str(vals[12]) if len(vals) > 12 else ''

        # Obtener bbox de la celda para posicionar el popup cerca
        bbox = self.tree_cotizaciones.bbox(item_id, column='Observaciones')

        popup = tk.Toplevel(self.root)
        popup.title(f"Observación — {folio}")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()
        popup.configure(bg='#f8fafc')

        # Posicionar cerca de la celda si es posible
        if bbox:
            x = self.tree_cotizaciones.winfo_rootx() + bbox[0]
            y = self.tree_cotizaciones.winfo_rooty() + bbox[1]
            popup.geometry(f"340x160+{x}+{y}")
            _centrar(ventana, self.root)
        else:
            popup.geometry("340x160")
            ventana.minsize(340, 200)
            ventana.resizable(True, True)
            _centrar(ventana, self.root)

        tk.Label(popup, text=f"📝  Observación — {folio}",
                 font=('Arial', 9, 'bold'), bg='#f8fafc', fg='#1e293b').pack(pady=(10, 4))

        txt = tk.Text(popup, font=('Arial', 9), width=38, height=4,
                      wrap='word', relief='solid', bd=1, padx=4, pady=4)
        txt.insert('1.0', obs_actual if obs_actual != 'None' else '')
        txt.pack(padx=10)
        txt.focus_set()
        txt.mark_set('insert', 'end')

        def guardar(event=None):
            nueva_obs = txt.get('1.0', 'end').strip()
            try:
                self.cursor.execute(
                    "UPDATE cotizaciones SET observaciones=? WHERE id=?",
                    (nueva_obs or None, cot_id))
                self.conn.commit()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=popup)
                return
            popup.destroy()
            self.cargar_cotizaciones()

        btns = tk.Frame(popup, bg='#f8fafc')
        btns.pack(pady=6)
        tk.Button(btns, text='💾 Guardar', command=guardar,
                  bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=10, pady=4, relief='raised').pack(side='left', padx=6)
        tk.Button(btns, text='Cancelar', command=popup.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=8, pady=4, relief='raised').pack(side='left')

        # Ctrl+Enter también guarda
        txt.bind('<Control-Return>', guardar)

    def _hover_icono_cotizacion(self, event):
        """Cambia cursor según la columna: mano para íconos de doc, lápiz para Observaciones."""
        col_id = self.tree_cotizaciones.identify_column(event.x)
        try:
            col_idx  = int(col_id[1:]) - 1
            col_name = self.tree_cotizaciones['columns'][col_idx]
        except (IndexError, ValueError):
            col_name = ''
        if col_name == 'Observaciones':
            self.tree_cotizaciones.configure(cursor='xterm')
            return
        if col_name in ('_oc_doc', '_fac_doc'):
            item_id = self.tree_cotizaciones.identify_row(event.y)
            if item_id:
                vals = self.tree_cotizaciones.item(item_id)['values']
                icon_val = str(vals[col_idx]) if len(vals) > col_idx else ''
                if icon_val in ('📋', '🧾'):
                    self.tree_cotizaciones.configure(cursor='hand2')
                    return
        self.tree_cotizaciones.configure(cursor='')

    def _click_icono_documento_cotizacion(self, event):
        """Si se hace clic en la columna 📄 de OC o Factura, abre el doc correspondiente."""
        import subprocess, platform
        region = self.tree_cotizaciones.identify('region', event.x, event.y)
        if region != 'cell':
            return
        col_id  = self.tree_cotizaciones.identify_column(event.x)   # '#1', '#2', ...
        item_id = self.tree_cotizaciones.identify_row(event.y)
        if not item_id:
            return
        # Mapear índice de columna → nombre
        cols = self.tree_cotizaciones['columns']
        try:
            col_idx  = int(col_id[1:]) - 1   # '#9' → 8
            col_name = cols[col_idx]
        except (IndexError, ValueError):
            return
        if col_name not in ('_oc_doc', '_fac_doc'):
            return
        # Obtener valor del ícono
        vals     = self.tree_cotizaciones.item(item_id)['values']
        icon_val = str(vals[col_idx])
        if icon_val not in ('📋', '🧾'):
            return                    # sin documento, no hacer nada

        cot_id = vals[0]

        if col_name == '_fac_doc':
            # Factura: abrir detalle del XML vinculado
            self._mostrar_detalle_factura_xml(cot_id)
            return

        # OC: abrir archivo físico desde documentos_cotizacion
        self.cursor.execute("""
            SELECT ruta_archivo FROM documentos_cotizacion
            WHERE cotizacion_id = ? AND tipo = 'Orden de Compra'
            ORDER BY fecha_registro DESC LIMIT 1
        """, (cot_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        ruta = row[0]
        if not os.path.exists(ruta):
            messagebox.showerror("Archivo no encontrado",
                f"El archivo ya no está en:\n{ruta}")
            return
        try:
            if platform.system() == 'Windows':
                os.startfile(ruta)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', ruta])
            else:
                subprocess.Popen(['xdg-open', ruta])
        except Exception as e:
            messagebox.showerror("Error al abrir", str(e))

    def _mostrar_detalle_factura_xml(self, cot_id, parent_win=None):
        """Muestra el detalle de la factura XML vinculada a una cotización."""
        self.cursor.execute("""
            SELECT id FROM facturas WHERE cotizacion_id = ?
            ORDER BY fecha_registro DESC LIMIT 1
        """, (cot_id,))
        row = self.cursor.fetchone()
        if not row:
            messagebox.showinfo("Sin factura XML",
                "Esta cotización no tiene una factura XML vinculada.\n\n"
                "Importa el CFDI en la sección 🧾 Facturación y vincúlalo.",
                parent=parent_win or self.root)
            return
        if hasattr(self, '_facturacion'):
            self.sistema._facturacion._mostrar_detalle_por_id(row[0])

    # Definición de etapas de seguimiento
    _ETAPAS_SEG = [
        ('Orden de Compra',     '📋', '#1a4b8c', '#dbeafe'),
        ('Entregada',           '🚚', '#166534', '#dcfce7'),
        ('Facturada',           '🧾', '#0e7490', '#cffafe'),
        ('Complemento de Pago', '💳', '#92400e', '#fef3c7'),
        ('Pagada',              '✅', '#6b21a8', '#f3e8ff'),
    ]

