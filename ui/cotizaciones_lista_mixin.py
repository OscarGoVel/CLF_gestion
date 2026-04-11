# -*- coding: utf-8 -*-
"""
ui/cotizaciones_lista_mixin.py
Mixin: cargar lista, nueva, editar, ver cotizacion, PDF básico, cancelar.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime

from modules.cotizaciones import VentanaCotizacion
from ui.generador_pdf_cly import GeneradorPDFCLY
from app_config import UTILIDAD


class _CotizacionesListaMixin:
    def cargar_cotizaciones(self):
        """Carga la lista de cotizaciones en la tabla.
        Columnas: ID, Folio, Fecha, Cliente, Total, Estado,
                  Entregado, O.C., _oc_doc, Ref. Factura, _fac_doc, Pagado, Observaciones
        """
        for item in self.tree_cotizaciones.get_children():
            self.tree_cotizaciones.delete(item)

        buscar = self.entry_buscar_cotizacion.get().strip()
        filtro  = getattr(self, '_filtro_estado_cot', None)
        estado_filtro = filtro.get() if filtro else 'Todos'

        params = []
        where_parts = []

        if estado_filtro and estado_filtro != 'Todos':
            where_parts.append('c.estado = ?')
            params.append(estado_filtro)

        if buscar:
            where_parts.append(
                '(c.folio LIKE ? OR cl.nombre_comercial LIKE ? OR c.orden_compra LIKE ? OR c.observaciones LIKE ?)')
            params += [f'%{buscar}%', f'%{buscar}%', f'%{buscar}%', f'%{buscar}%']

        where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

        self.cursor.execute(f"""
            SELECT c.id, c.folio, c.fecha, cl.nombre_comercial,
                   c.total, c.estado, c.monto_entregado,
                   c.orden_compra, c.monto_facturado, c.monto_pagado,
                   c.observaciones
            FROM cotizaciones c
            JOIN clientes cl ON c.cliente_id = cl.id
            {where_sql}
            ORDER BY c.folio DESC
        """, params)

        rows = self.cursor.fetchall()

        # Pre-cargar documentos de OC por cotización
        if rows:
            ids = [r[0] for r in rows]
            placeholders = ','.join('?' * len(ids))

            self.cursor.execute(f"""
                SELECT cotizacion_id, tipo
                FROM documentos_cotizacion
                WHERE cotizacion_id IN ({placeholders})
                  AND tipo = 'Orden de Compra'
            """, ids)
            docs_oc_set = set()
            for cot_id, _ in self.cursor.fetchall():
                docs_oc_set.add(cot_id)

            # Referencia de OC desde seguimiento_etapas
            self.cursor.execute(f"""
                SELECT cotizacion_id, referencia
                FROM seguimiento_etapas
                WHERE cotizacion_id IN ({placeholders})
                  AND etapa = 'Orden de Compra'
                  AND referencia IS NOT NULL AND referencia != ''
            """, ids)
            seg_oc_refs = {row[0]: row[1] for row in self.cursor.fetchall()}

            # Facturas vinculadas desde factura_cotizaciones (junction table, múltiples por cotización)
            try:
                self.cursor.execute(f"""
                    SELECT fc.cotizacion_id, f.id, f.uuid, f.serie, f.folio_factura, f.fecha, f.total
                    FROM factura_cotizaciones fc
                    JOIN facturas f ON f.id = fc.factura_id
                    WHERE fc.cotizacion_id IN ({placeholders})
                    ORDER BY f.fecha DESC
                """, ids)
            except Exception:
                # Fallback a columna legacy si la tabla aún no existe
                self.cursor.execute(f"""
                    SELECT cotizacion_id, id, uuid, serie, folio_factura, fecha, total
                    FROM facturas
                    WHERE cotizacion_id IN ({placeholders})
                """, ids)
            facturas_por_cot = {}  # cot_id -> lista de facturas
            for cot_id, fid, uuid, serie, folio_f, fecha_f, total_f in self.cursor.fetchall():
                if cot_id not in facturas_por_cot:
                    facturas_por_cot[cot_id] = []
                facturas_por_cot[cot_id].append({
                    'id': fid, 'uuid': uuid, 'serie': serie,
                    'folio': folio_f, 'fecha': fecha_f, 'total': total_f,
                })
        else:
            docs_oc_set     = set()
            seg_oc_refs     = {}
            facturas_por_cot = {}

        # Estados activos (programada o más avanzado en entrega)
        ESTADOS_ACTIVOS = {'Programada', 'Parcialmente Entregada', 'Entregada',
                           'Facturada', 'Pagada'}

        for row in rows:
            cot_id, folio, fecha, cliente, total, estado, entregado, oc, facturado, pagado, obs = row
            tiene_oc  = cot_id in docs_oc_set
            fac_lista = facturas_por_cot.get(cot_id, [])
            tiene_fac = len(fac_lista) > 0
            oc_icon   = '📋' if tiene_oc  else '·'
            fac_icon  = '🧾' if tiene_fac else '·'

            # Referencia de OC desde seguimiento o campo directo
            ref_oc = seg_oc_refs.get(cot_id, '') or (oc or '')

            # Referencia de factura: serie-folio del XML (puede haber varias)
            if fac_lista:
                folios = []
                for fd in fac_lista:
                    if fd['serie'] and fd['folio']:
                        folios.append(f"{fd['serie']}-{fd['folio']}")
                    elif fd['folio']:
                        folios.append(fd['folio'])
                    else:
                        folios.append((fd['uuid'] or '')[:12] + '…')
                ref_fac = ', '.join(folios)
            else:
                ref_fac = ''

            # Lógica de visualización de O.C. y Factura en tabla
            if estado in ('Pendiente', 'Cancelada'):
                oc_txt  = 'N/A'
                fac_txt = 'N/A'
            else:
                oc_txt  = ref_oc  if ref_oc  else '✗'
                fac_txt = ref_fac if ref_fac else '✗'

            # Tags: estado de fondo + marcadores de documento
            tags = [estado]
            if tiene_oc:  tags.append('_has_oc')
            if tiene_fac: tags.append('_has_fac')

            obs_txt = (obs or '').strip()
            _emoji_estado = {
                'Pendiente':              '🟡',
                'Programada':             '🔵',
                'Parcialmente Entregada': '🟣',
                'Entregada':              '🟢',
                'Cancelada':              '⛔',
            }
            estado_display = f"{_emoji_estado.get(estado, '⚪')} {estado}"
            idx_fila = len(self.tree_cotizaciones.get_children())
            fila_tag = 'fila_par' if idx_fila % 2 == 0 else 'fila_impar'
            tags_finales = (fila_tag,) + tuple(t for t in tags if t not in (
                'Pendiente','Programada','Parcialmente Entregada',
                'Entregada','Facturada','Pagada','Cancelada'))
            # Pagado: N/A si el estado no lo aplica aún
            if estado in ('Pendiente', 'Cancelada'):
                pagado_txt = 'N/A'
            elif pagado and pagado > 0:
                pagado_txt = f'${pagado:,.2f}'
            else:
                pagado_txt = '—'

            # ── Urgencia y columna Días ───────────────────────────────────
            from datetime import date as _date
            dias_num  = None
            dias_txt  = '—'
            urg_tag   = ''
            try:
                hoy = _date.today()
                if estado == 'Cancelada':
                    dias_txt = '—'
                elif estado in ('Pendiente', 'Programada'):
                    # Días desde creación
                    dias_num = (hoy - _date.fromisoformat(str(fecha)[:10])).days
                    if dias_num > 30:
                        dias_txt = f'🔴 {dias_num}d'
                        urg_tag  = 'urg_alta'
                    elif dias_num > 14:
                        dias_txt = f'🟡 {dias_num}d'
                        urg_tag  = 'urg_media'
                    else:
                        dias_txt = f'{dias_num}d'
                elif estado == 'Entregada' and not fac_lista:
                    # Días entregada sin facturar
                    self.cursor.execute(
                        "SELECT fecha_entrega FROM cotizaciones WHERE id=?", (cot_id,))
                    fe_row = self.cursor.fetchone()
                    fe = fe_row[0] if fe_row and fe_row[0] else fecha
                    dias_num = (hoy - _date.fromisoformat(str(fe)[:10])).days
                    if dias_num > 7:
                        dias_txt = f'🔴 {dias_num}d'
                        urg_tag  = 'urg_alta'
                    elif dias_num > 3:
                        dias_txt = f'🟡 {dias_num}d'
                        urg_tag  = 'urg_media'
                    else:
                        dias_txt = f'✅ {dias_num}d'
                        urg_tag  = 'urg_baja'
                elif estado in ('Facturada',):
                    # Días desde facturación sin pagar
                    dias_num = (hoy - _date.fromisoformat(str(fecha)[:10])).days
                    if dias_num > 30:
                        dias_txt = f'🔴 {dias_num}d'
                        urg_tag  = 'urg_alta'
                    else:
                        dias_txt = f'{dias_num}d'
                elif estado == 'Pagada':
                    dias_txt = '✅'
            except Exception:
                dias_txt = '—'

            if urg_tag:
                tags_finales = (urg_tag,) + tuple(
                    t for t in tags_finales if t not in ('fila_par','fila_impar'))
            else:
                pass  # keep existing fila_par/fila_impar

            values = (
                cot_id, folio, fecha, cliente,
                f'${total:,.2f}', estado_display,
                f'${entregado:,.2f}', oc_txt, oc_icon,
                fac_txt, fac_icon,
                pagado_txt, obs_txt, dias_txt,
            )
            self.tree_cotizaciones.insert('', 'end', values=values, tags=tags_finales)

        # Reaplicar ordenamiento si el usuario había seleccionado uno
        if hasattr(self.tree_cotizaciones, 'reaplicar_sort'):
            self.tree_cotizaciones.reaplicar_sort()

        # Actualizar badge de urgentes en el tab
        self._actualizar_badge_urgentes()
    
    def nueva_cotizacion(self):
        """Abre ventana para crear nueva cotización"""
        def _ir_catalogo_nueva():
            self.sistema._navegar('catalogos')
            try:
                nb = self.sistema.catalogos._notebook
                for i in range(nb.index('end')):
                    if 'roducto' in nb.tab(i, 'text'):
                        nb.select(i)
                        break
            except Exception:
                pass

        ventana_cot = VentanaCotizacion(self.root, self.conn, self.cursor, UTILIDAD,
                                        modo='nueva', on_ir_catalogo=_ir_catalogo_nueva)
        self.root.wait_window(ventana_cot.ventana)
        # Recargar cotizaciones y dashboard
        self.cargar_cotizaciones()
        self.sistema.actualizar_dashboard()
    
    def editar_cotizacion(self):
        """Edita la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        estado = item['values'][5]
        
        # No permitir editar si ya está entregada, facturada o pagada
        if estado in ['Entregada', 'Facturada', 'Pagada']:
            messagebox.showwarning(
                "Advertencia",
                f"No se puede editar una cotización en estado '{estado}'.\n\n" +
                "Solo se pueden editar cotizaciones en estado 'Pendiente' o 'Programada'."
            )
            return
        
        # Abrir ventana en modo edición
        def _ir_catalogo_editar():
            self.sistema._navegar('catalogos')
            try:
                nb = self.sistema.catalogos._notebook
                for i in range(nb.index('end')):
                    if 'roducto' in nb.tab(i, 'text'):
                        nb.select(i)
                        break
            except Exception:
                pass

        ventana_cot = VentanaCotizacion(
            self.root, self.conn, self.cursor, UTILIDAD,
            modo='editar', cotizacion_id=cotizacion_id,
            on_ir_catalogo=_ir_catalogo_editar
        )
        self.root.wait_window(ventana_cot.ventana)
        self.cargar_cotizaciones()
        self.sistema.actualizar_dashboard()
    
    def ver_cotizacion(self):
        """Ver detalle de cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        messagebox.showinfo("Info", "Vista de detalle se implementará próximamente")
    
    def generar_pdf_cotizacion(self):
        """Genera el PDF de la cotización seleccionada"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        
        # Preguntar dónde guardar
        ruta_salida = filedialog.asksaveasfilename(
            title="Guardar cotización como...",
            defaultextension=".pdf",
            initialfile=f"Cotizacion_{folio}.pdf",
            filetypes=[("PDF files", "*.pdf")]
        )
        
        if ruta_salida:
            try:
                generador = GeneradorPDFCLY()
                arquivo = generador.generar_cotizacion(self.conn, cotizacion_id)
                if arquivo:
                    messagebox.showinfo("Éxito", f"PDF generado correctamente:\n{arquivo}")
                    
                    # Preguntar si desea abrir el PDF
                    respuesta = messagebox.askyesno("Abrir PDF", "¿Deseas abrir el PDF generado?")
                    if respuesta:
                        os.startfile(arquivo) if os.name == 'nt' else os.system(f'open "{arquivo}"')
                else:
                    messagebox.showerror("Error", "No se pudo generar el PDF")
            except Exception as e:
                messagebox.showerror("Error", f"Error al generar PDF:\n{str(e)}")
    
    def marcar_entregada(self):
        """Marca la cotización como entregada y descuenta del stock"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        # No permitir marcar como entregada si está cancelada
        if estado_actual == 'Cancelada':
            messagebox.showwarning("Advertencia", "No se puede entregar una cotización cancelada")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar entrega",
            f"¿Marcar como entregada la cotización {folio}?\n\nSe descontará del inventario."
        )
        
        if respuesta:
            try:
                # Obtener detalle de cotización
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

                # Actualizar estado y fecha de entrega
                fecha_entrega = datetime.now().strftime('%Y-%m-%d')
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Entregada',
                        fecha_entrega = ?,
                        monto_entregado = total
                    WHERE id = ?
                """, (fecha_entrega, cotizacion_id))

                self.conn.commit()
                messagebox.showinfo("Éxito", "Cotización marcada como entregada y stock actualizado")
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo actualizar:\n{str(e)}")
    
    def cancelar_cotizacion(self):
        """Cancela una cotización sin afectar el stock"""
        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona una cotización")
            return
        
        item = self.tree_cotizaciones.item(seleccion[0])
        cotizacion_id = item['values'][0]
        folio = item['values'][1]
        estado_actual = item['values'][5]
        
        # No permitir cancelar si ya está entregada o pagada
        if estado_actual in ['Entregada', 'Pagada']:
            messagebox.showwarning(
                "Advertencia", 
                f"No se puede cancelar una cotización que ya está {estado_actual.lower()}"
            )
            return
        
        # Si ya está cancelada
        if estado_actual == 'Cancelada':
            messagebox.showinfo("Info", "Esta cotización ya está cancelada")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar cancelación",
            f"¿Cancelar la cotización {folio}?\n\n" +
            "La cotización se marcará como cancelada pero permanecerá en el registro.\n" +
            "No se afectará el inventario."
        )
        
        if respuesta:
            try:
                # Actualizar estado a Cancelada
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET estado = 'Cancelada'
                    WHERE id = ?
                """, (cotizacion_id,))
                
                self.conn.commit()
                messagebox.showinfo("Éxito", "Cotización cancelada correctamente")
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()
                
            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", f"No se pudo cancelar:\n{str(e)}")

