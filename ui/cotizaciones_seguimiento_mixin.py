# -*- coding: utf-8 -*-
"""
ui/cotizaciones_seguimiento_mixin.py
Mixin: estado de cuenta, seguimiento de etapas, gestión de documentos, preview.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
import subprocess
import platform
from datetime import datetime

from modules.estado_de_cuenta import VentanaEstadoCuenta
from app_config import DOCUMENTOS_DIR
from ui.utils import centrar_ventana as _centrar


class _CotizacionesSeguimientoMixin:
    def ver_estado_cuenta(self):
        """Abre la ventana de Estado de Cuenta de Pedidos."""
        VentanaEstadoCuenta(self.root, self.conn, self.cursor)

    def ver_seguimiento_cotizacion(self):
        """Abre ventana de seguimiento por etapas de la cotización seleccionada."""
        import subprocess, platform

        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return

        item   = self.tree_cotizaciones.item(seleccion[0])
        cot_id = item['values'][0]
        folio  = item['values'][1]

        # Obtener info del cliente
        self.cursor.execute("""
            SELECT cl.nombre_comercial, c.fecha, c.total, c.estado
            FROM cotizaciones c JOIN clientes cl ON c.cliente_id = cl.id
            WHERE c.id = ?
        """, (cot_id,))
        info = self.cursor.fetchone()
        cliente  = info[0] if info else ''
        cot_total = info[2] if info else 0
        cot_estado = info[3] if info else ''

        # Carpeta de documentos de esta cotización
        base_docs = os.path.join(DOCUMENTOS_DIR, folio)

        # ── Ventana principal ────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f"📋 Seguimiento — {folio}")
        win.geometry("900x580")
        win.minsize(820, 500)
        win.resizable(True, True)
        _centrar(win, self.root)
        win.configure(bg='#f1f5f9')
        win.transient(self.root)
        win.grab_set()

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg='#7c3aed', pady=10)
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"📋  Seguimiento de Cotización",
                 font=('Arial', 12, 'bold'), bg='#7c3aed', fg='white').pack()
        tk.Label(hdr, text=f"{folio}  •  {cliente}  •  ${cot_total:,.2f}  •  {cot_estado}",
                 font=('Arial', 9), bg='#7c3aed', fg='#d8b4fe').pack()

        # ── Contenedor de tarjetas ────────────────────────────────────────────
        cards_frame = tk.Frame(win, bg='#f1f5f9')
        cards_frame.pack(fill='both', expand=True, padx=16, pady=12)

        # Diccionario para referencias a widgets por etapa
        widgets_etapa = {}

        def cargar_etapas():
            for w in cards_frame.winfo_children():
                w.destroy()

            # Obtener datos guardados de seguimiento
            self.cursor.execute("""
                SELECT etapa, completada, referencia, fecha_etapa, notas
                FROM seguimiento_etapas WHERE cotizacion_id = ?
            """, (cot_id,))
            datos = {row[0]: row for row in self.cursor.fetchall()}

            # Documentos físicos por tipo (OC, Complemento)
            self.cursor.execute("""
                SELECT tipo, COUNT(*) FROM documentos_cotizacion
                WHERE cotizacion_id = ? GROUP BY tipo
            """, (cot_id,))
            docs_count = dict(self.cursor.fetchall())

            # Factura XML vinculada
            self.cursor.execute("""
                SELECT id, uuid, serie, folio_factura, fecha, total,
                       rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
                       subtotal, iva, metodo_pago, forma_pago, ruta_xml
                FROM facturas WHERE cotizacion_id = ?
                ORDER BY fecha_registro DESC LIMIT 1
            """, (cot_id,))
            fac_row = self.cursor.fetchone()
            factura_xml = None
            if fac_row:
                factura_xml = {
                    'id': fac_row[0], 'uuid': fac_row[1],
                    'serie': fac_row[2], 'folio': fac_row[3],
                    'fecha': (fac_row[4] or '')[:10],
                    'total': fac_row[5] or 0,
                    'rfc_emisor': fac_row[6], 'nombre_emisor': fac_row[7],
                    'rfc_receptor': fac_row[8], 'nombre_receptor': fac_row[9],
                    'subtotal': fac_row[10] or 0, 'iva': fac_row[11] or 0,
                    'metodo_pago': fac_row[12], 'forma_pago': fac_row[13],
                    'ruta_xml': fac_row[14],
                }

            # Barra de progreso
            etapas_completas = sum(
                1 for e, _, _, _ in self._ETAPAS_SEG
                if datos.get(e, (None, 0))[1]
            )
            # Contar Facturada como completada si hay XML aunque no esté en seguimiento
            if factura_xml and not datos.get('Facturada', (None, 0))[1]:
                etapas_completas += 1
            total_etapas = len(self._ETAPAS_SEG)

            prog_frame = tk.Frame(cards_frame, bg='#f1f5f9')
            prog_frame.pack(fill='x', pady=(0, 10))
            tk.Label(prog_frame, text=f"Progreso: {etapas_completas}/{total_etapas} etapas",
                     font=('Arial', 9, 'bold'), bg='#f1f5f9', fg='#374151').pack(side='left')
            pct = int((etapas_completas / total_etapas) * 100)
            tk.Label(prog_frame, text=f"{pct}%",
                     font=('Arial', 9, 'bold'), bg='#f1f5f9', fg='#7c3aed').pack(side='right')
            bar_outer = tk.Frame(prog_frame, bg='#e2e8f0', height=8)
            bar_outer.pack(fill='x', pady=(6, 0))
            bar_outer.pack_propagate(False)
            if pct > 0:
                tk.Frame(bar_outer, bg='#7c3aed', height=8,
                         width=max(4, int(bar_outer.winfo_reqwidth() * pct / 100))
                         ).pack(side='left')

            # Una tarjeta por etapa
            for etapa, icono, fg, bg in self._ETAPAS_SEG:
                d = datos.get(etapa)
                completada  = bool(d[1]) if d else False
                referencia  = d[2] or '' if d else ''
                fecha_etapa = d[3] or '' if d else ''
                notas       = d[4] or '' if d else ''

                tipo_doc_map = {
                    'Orden de Compra':     'Orden de Compra',
                    'Facturada':           'Factura',
                    'Complemento de Pago': 'Complemento de Pago',
                }
                tipo_doc = tipo_doc_map.get(etapa)
                n_docs   = docs_count.get(tipo_doc, 0) if tipo_doc else 0

                # Facturada: completada visualmente si hay XML vinculado
                if etapa == 'Facturada' and factura_xml:
                    completada = True

                card_bg = bg if completada else '#ffffff'
                border  = fg if completada else '#cbd5e1'

                card = tk.Frame(cards_frame, bg=card_bg, pady=8, padx=12,
                                highlightbackground=border, highlightthickness=2)
                card.pack(fill='x', pady=4)

                top = tk.Frame(card, bg=card_bg)
                top.pack(fill='x')

                estado_txt = '✅' if completada else '⏳'
                tk.Label(top, text=f"{estado_txt} {icono}  {etapa}",
                         font=('Arial', 11, 'bold'), bg=card_bg,
                         fg=fg if completada else '#6b7280').pack(side='left')

                btn_frame = tk.Frame(top, bg=card_bg)
                btn_frame.pack(side='right')

                # Botón ver: Facturada → detalle XML; otros → archivo físico
                if etapa == 'Facturada' and factura_xml:
                    def _ver_fac_xml(fid=factura_xml['id']):
                        if hasattr(self, '_facturacion'):
                            self.sistema._facturacion._mostrar_detalle_por_id(fid)
                    tk.Button(btn_frame, text='🧾 Ver CFDI',
                              command=_ver_fac_xml, bg='#cffafe', fg='#0e7490',
                              font=('Arial', 8, 'bold'), cursor='hand2',
                              relief='flat', padx=8, pady=3).pack(side='left', padx=(0, 6))
                elif n_docs > 0 and tipo_doc and etapa != 'Facturada':
                    def _abrir_doc(tp=tipo_doc):
                        self.cursor.execute("""
                            SELECT ruta_archivo FROM documentos_cotizacion
                            WHERE cotizacion_id=? AND tipo=?
                            ORDER BY fecha_registro DESC LIMIT 1
                        """, (cot_id, tp))
                        frow = self.cursor.fetchone()
                        if frow and os.path.exists(frow[0]):
                            try:
                                if platform.system() == 'Windows': os.startfile(frow[0])
                                elif platform.system() == 'Darwin': subprocess.Popen(['open', frow[0]])
                                else: subprocess.Popen(['xdg-open', frow[0]])
                            except Exception as ex:
                                messagebox.showerror("Error", str(ex), parent=win)
                        else:
                            messagebox.showerror("No encontrado",
                                "El archivo no está disponible", parent=win)
                    lbl_doc = '📋' if tipo_doc == 'Orden de Compra' else '💳'
                    tk.Button(btn_frame, text=f'{lbl_doc} Ver doc ({n_docs})',
                              command=_abrir_doc, bg='#e0e7ff', fg='#3730a3',
                              font=('Arial', 8, 'bold'), cursor='hand2',
                              relief='flat', padx=8, pady=3).pack(side='left', padx=(0, 6))

                # Botón Editar etapa
                def _editar(e=etapa, comp=completada, ref=referencia,
                            fe=fecha_etapa, n=notas):
                    self._editar_etapa_seguimiento(win, cot_id, e, comp, ref, fe, n,
                                                   tipo_doc_map.get(e), cargar_etapas)
                tk.Button(btn_frame, text='✏️ Editar',
                          command=_editar, bg='#f3f4f6', fg='#374151',
                          font=('Arial', 8), cursor='hand2',
                          relief='flat', padx=8, pady=3).pack(side='left')

                # Detalle de la tarjeta
                if etapa == 'Facturada' and factura_xml:
                    det = tk.Frame(card, bg=card_bg)
                    det.pack(fill='x', pady=(6, 0))
                    fac = factura_xml
                    sf  = f"{fac['serie']}-{fac['folio']}" if fac['serie'] else (fac['folio'] or '—')
                    lineas = [
                        f"📄 {sf}   •   Fecha: {fac['fecha']}   •   Total: ${fac['total']:,.2f}",
                        f"UUID: {fac['uuid']}",
                        f"Receptor: {fac['rfc_receptor']}  {fac['nombre_receptor']}",
                    ]
                    if fac['metodo_pago'] or fac['forma_pago']:
                        lineas.append(
                            f"Método pago: {fac['metodo_pago'] or '—'}   Forma: {fac['forma_pago'] or '—'}")
                    if notas:
                        lineas.append(f"📝 {notas}")
                    for line in lineas:
                        tk.Label(det, text=line, font=('Arial', 8),
                                 bg=card_bg, fg='#0e7490', anchor='w').pack(fill='x')

                elif completada or referencia or fecha_etapa or notas:
                    det = tk.Frame(card, bg=card_bg)
                    det.pack(fill='x', pady=(6, 0))
                    campos = []
                    if referencia:  campos.append(f"Ref: {referencia}")
                    if fecha_etapa: campos.append(f"Fecha: {fecha_etapa}")
                    if notas:       campos.append(f"📝 {notas}")
                    if campos:
                        tk.Label(det, text="   ".join(campos),
                                 font=('Arial', 8), bg=card_bg, fg='#4b5563',
                                 anchor='w').pack(fill='x')


        # ── Pie de ventana ────────────────────────────────────────────────────
        foot = tk.Frame(win, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')
        tk.Button(foot, text='📎 Gestionar documentos',
                  command=lambda: [win.destroy(), self.gestionar_documentos_cotizacion()],
                  bg='#16a085', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5, relief='raised').pack(side='left', padx=12)
        def _cerrar_seguimiento():
            win.destroy()
            self.cargar_cotizaciones()
            self.sistema.actualizar_dashboard()

        tk.Button(foot, text='Cerrar', command=_cerrar_seguimiento,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=12, pady=5, relief='raised').pack(side='right', padx=12)

        win.protocol('WM_DELETE_WINDOW', _cerrar_seguimiento)

        cargar_etapas()

    def _editar_etapa_seguimiento(self, parent, cot_id, etapa, completada,
                                   referencia, fecha_etapa, notas,
                                   tipo_doc, callback_recargar):
        """Diálogo para editar una etapa de seguimiento."""
        import shutil

        dlg = tk.Toplevel(parent)
        dlg.title(f"Editar etapa — {etapa}")
        dlg.geometry("480x400")
        dlg.minsize(400, 320)
        dlg.resizable(True, True)
        _centrar(dlg, self.root)
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.grab_set()
        dlg.configure(bg='#f8fafc')

        tk.Label(dlg, text=f"✏️  {etapa}",
                 font=('Arial', 12, 'bold'), bg='#f8fafc', fg='#1e293b').pack(pady=(18, 10))

        form = tk.Frame(dlg, bg='#f8fafc')
        form.pack(fill='x', padx=24)
        form.grid_columnconfigure(1, weight=1)

        def lbl(row, texto):
            tk.Label(form, text=texto, font=('Arial', 9, 'bold'),
                     bg='#f8fafc', fg='#374151', anchor='e').grid(
                row=row, column=0, sticky='e', padx=(0, 10), pady=6)

        # Completada
        lbl(0, 'Estado:')
        var_comp = tk.BooleanVar(value=completada)
        chk = tk.Checkbutton(form, text='Marcar como completada',
                              variable=var_comp, bg='#f8fafc',
                              font=('Arial', 9))
        chk.grid(row=0, column=1, sticky='w')

        # Referencia
        lbl(1, 'Referencia:')
        entry_ref = tk.Entry(form, font=('Arial', 9), width=32)
        entry_ref.insert(0, referencia)
        entry_ref.grid(row=1, column=1, sticky='ew')

        # Fecha
        lbl(2, 'Fecha:')
        entry_fecha = tk.Entry(form, font=('Arial', 9), width=18)
        entry_fecha.insert(0, fecha_etapa)
        entry_fecha.grid(row=2, column=1, sticky='w')
        tk.Label(form, text='YYYY-MM-DD', font=('Arial', 7),
                 bg='#f8fafc', fg='#9ca3af').grid(row=3, column=1, sticky='w')

        # Notas
        lbl(4, 'Notas:')
        entry_notas = tk.Text(form, font=('Arial', 9), width=32, height=3,
                              wrap='word', relief='solid', bd=1)
        entry_notas.insert('1.0', notas)
        entry_notas.grid(row=4, column=1, sticky='ew', pady=(0, 4))

        # Adjuntar documento
        if tipo_doc:
            lbl(5, 'Documento:')
            def _adjuntar():
                base_docs = DOCUMENTOS_DIR
                # Obtener folio para la carpeta
                self.cursor.execute("SELECT folio FROM cotizaciones WHERE id=?", (cot_id,))
                folio = self.cursor.fetchone()[0]
                tipo_carpeta_map = {
                    'Orden de Compra':     'OC',
                    'Factura':             'Facturas',
                    'Complemento de Pago': 'Complementos',
                }
                carpeta = os.path.join(base_docs, folio,
                                       tipo_carpeta_map.get(tipo_doc, 'Otros'))
                os.makedirs(carpeta, exist_ok=True)
                rutas = filedialog.askopenfilenames(
                    title=f"Adjuntar {tipo_doc}",
                    filetypes=[("Documentos", "*.pdf *.xml *.docx *.xlsx *.png *.jpg"),
                               ("Todos", "*.*")],
                    parent=dlg)
                for ruta_orig in rutas:
                    nombre = os.path.basename(ruta_orig)
                    destino = os.path.join(carpeta, nombre)
                    base, ext = os.path.splitext(nombre)
                    cnt = 1
                    while os.path.exists(destino):
                        destino = os.path.join(carpeta, f"{base}_{cnt}{ext}")
                        cnt += 1
                    try:
                        shutil.copy2(ruta_orig, destino)
                        self.cursor.execute("""
                            INSERT INTO documentos_cotizacion
                            (cotizacion_id, tipo, nombre_archivo, ruta_archivo)
                            VALUES (?, ?, ?, ?)
                        """, (cot_id, tipo_doc, os.path.basename(destino), destino))
                        self.conn.commit()
                    except Exception as e:
                        messagebox.showerror("Error", str(e), parent=dlg)
                if rutas:
                    messagebox.showinfo("Listo",
                        f"{len(rutas)} archivo(s) adjuntados", parent=dlg)

            tk.Button(form, text=f'📎 Adjuntar {tipo_doc}',
                      command=_adjuntar, bg='#16a085', fg='white',
                      font=('Arial', 8, 'bold'), cursor='hand2',
                      padx=10, pady=4, relief='raised').grid(
                row=5, column=1, sticky='w', pady=6)

        # Botones guardar/cancelar
        btns = tk.Frame(dlg, bg='#f8fafc')
        btns.pack(pady=14)

        def _guardar():
            comp  = var_comp.get()
            ref   = entry_ref.get().strip()
            fecha = entry_fecha.get().strip()
            n     = entry_notas.get('1.0', 'end').strip()
            try:
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas
                        (cotizacion_id, etapa, completada, referencia, fecha_etapa, notas)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada  = excluded.completada,
                        referencia  = excluded.referencia,
                        fecha_etapa = excluded.fecha_etapa,
                        notas       = excluded.notas
                """, (cot_id, etapa, int(comp), ref or None, fecha or None, n or None))

                # ── Si es Orden de Compra, sincronizar referencia → cotizaciones.orden_compra
                if etapa == 'Orden de Compra' and ref:
                    self.cursor.execute("""
                        UPDATE cotizaciones
                        SET orden_compra = ?,
                            fecha_orden_compra = COALESCE(?, fecha_orden_compra)
                        WHERE id = ?
                    """, (ref, fecha or None, cot_id))

                # ── Si es Facturada, sincronizar referencia → cotizaciones.numero_factura
                if etapa == 'Facturada' and ref:
                    self.cursor.execute("""
                        UPDATE cotizaciones
                        SET numero_factura = ?,
                            fecha_factura = COALESCE(?, fecha_factura)
                        WHERE id = ?
                    """, (ref, fecha or None, cot_id))

                # ── Sincronizar cotizaciones.estado ─────────────────────────
                self._sync_estado_desde_seguimiento(cot_id, etapa, comp)

                self.conn.commit()

                # Siempre refrescar lista (puede haber cambiado O.C. o estado)
                self.cargar_cotizaciones()
                self.sistema.actualizar_dashboard()

            except Exception as e:
                messagebox.showerror("Error al guardar", str(e), parent=dlg)
                return
            dlg.destroy()
            callback_recargar()

        tk.Button(btns, text='💾 Guardar', command=_guardar,
                  bg='#7c3aed', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=8)
        tk.Button(btns, text='Cancelar', command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='left')

    # ── Mapa bidireccional estado ↔ etapa de seguimiento ──────────────────────
    _ESTADO_A_ETAPA = {
        'Entregada':  'Entregada',
        'Facturada':  'Facturada',
        'Pagada':     'Pagada',
    }
    _ETAPA_A_ESTADO = {
        'Entregada':  'Entregada',
        'Facturada':  'Facturada',
        'Pagada':     'Pagada',
    }

    def _sync_seguimiento_desde_estado(self, cotizacion_id, nuevo_estado, fecha=None):
        """Sincroniza seguimiento_etapas cuando cambia cotizaciones.estado.
        
        Si el nuevo_estado corresponde a una etapa de seguimiento conocida,
        hace un UPSERT marcándola como completada con la fecha indicada.
        """
        etapa = self._ESTADO_A_ETAPA.get(nuevo_estado)
        if not etapa:
            return
        fecha_etapa = fecha or datetime.now().strftime('%Y-%m-%d')
        self.cursor.execute("""
            INSERT INTO seguimiento_etapas
                (cotizacion_id, etapa, completada, fecha_etapa)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                completada  = 1,
                fecha_etapa = COALESCE(excluded.fecha_etapa, seguimiento_etapas.fecha_etapa)
        """, (cotizacion_id, etapa, fecha_etapa))

    def _sync_estado_desde_seguimiento(self, cotizacion_id, etapa, completada):
        """Sincroniza cotizaciones.estado y monto_pagado cuando se edita
        una etapa de seguimiento.
        """
        if not completada:
            return False

        # ── Pagada: marcar pago completo ─────────────────────────────────
        if etapa == 'Pagada':
            self.cursor.execute(
                "SELECT total, monto_pagado, estado FROM cotizaciones WHERE id=?",
                (cotizacion_id,))
            row = self.cursor.fetchone()
            if not row:
                return False
            total, monto_pagado, estado_actual = row
            # Si aún no tiene monto_pagado registrado, asignar el total completo
            nuevo_pagado = monto_pagado if (monto_pagado and monto_pagado >= total) else total
            from datetime import datetime as _dt
            self.cursor.execute("""
                UPDATE cotizaciones
                SET monto_pagado = ?,
                    fecha_pago   = COALESCE(fecha_pago, ?),
                    estado       = 'Pagada'
                WHERE id = ?
            """, (nuevo_pagado, _dt.now().strftime('%Y-%m-%d'), cotizacion_id))
            return True

        # ── Entregada: sincronizar estado ────────────────────────────────
        if etapa != 'Entregada':
            return False
        nuevo_estado = 'Entregada'
        orden = ['Pendiente', 'Programada', 'Parcialmente Entregada', 'Entregada', 'Cancelada']
        self.cursor.execute("SELECT estado FROM cotizaciones WHERE id = ?", (cotizacion_id,))
        row = self.cursor.fetchone()
        if not row:
            return False
        estado_actual = row[0]
        idx_actual = orden.index(estado_actual) if estado_actual in orden else 0
        idx_nuevo  = orden.index(nuevo_estado)  if nuevo_estado  in orden else 0
        if idx_nuevo > idx_actual:
            self.cursor.execute(
                "UPDATE cotizaciones SET estado = ? WHERE id = ?",
                (nuevo_estado, cotizacion_id))
            return True
        return False

    def gestionar_documentos_cotizacion(self):
        """Abre ventana para gestionar documentos adjuntos de la cotización seleccionada."""
        import shutil, subprocess, platform

        seleccion = self.tree_cotizaciones.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una cotización")
            return

        item   = self.tree_cotizaciones.item(seleccion[0])
        cot_id = item['values'][0]
        folio  = item['values'][1]

        # Directorio base de documentos junto a la BD
        base_docs = os.path.join(DOCUMENTOS_DIR, folio)
        tipos_carpeta = {
            'Orden de Compra':       os.path.join(base_docs, 'OC'),
            'Factura':               os.path.join(base_docs, 'Facturas'),
            'Complemento de Pago':   os.path.join(base_docs, 'Complementos'),
            'Otro':                  os.path.join(base_docs, 'Otros'),
        }
        for carpeta in tipos_carpeta.values():
            os.makedirs(carpeta, exist_ok=True)

        # ── Ventana ──────────────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f"📎 Documentos — {folio}")
        win.geometry("860x560")
        win.minsize(780, 480)
        win.resizable(True, True)
        _centrar(win, self.root)
        win.configure(bg='#f1f5f9')
        win.transient(self.root)

        # Header
        hdr = tk.Frame(win, bg='#16a085', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"📎  Documentos adjuntos", font=('Arial', 11, 'bold'),
                 bg='#16a085', fg='white').pack()
        tk.Label(hdr, text=folio, font=('Arial', 9),
                 bg='#16a085', fg='#d5f5ef').pack()

        # Toolbar
        tb = tk.Frame(win, bg='#d8dde8', pady=5)
        tb.pack(fill='x')
        tk.Frame(win, bg='#c5ccd8', height=1).pack(fill='x')

        # ── Tabla de documentos ───────────────────────────────────────────────
        cols = ('ID', 'Tipo', 'Archivo', 'Notas', 'Fecha')
        tree = ttk.Treeview(win, columns=cols, show='headings', selectmode='browse')
        tree.heading('ID',     text='ID')
        tree.heading('Tipo',   text='Tipo')
        tree.heading('Archivo',text='Archivo')
        tree.heading('Notas',  text='Notas')
        tree.heading('Fecha',  text='Fecha')
        tree.column('ID',     width=0,   stretch=False)
        tree.column('Tipo',   width=160, anchor='w')
        tree.column('Archivo',width=280, anchor='w')
        tree.column('Notas',  width=200, anchor='w')
        tree.column('Fecha',  width=140, anchor='w')

        # Colores por tipo
        tree.tag_configure('Orden de Compra',     background='#dbeafe', foreground='#1a4b8c')
        tree.tag_configure('Factura',             background='#dcfce7', foreground='#166534')
        tree.tag_configure('Complemento de Pago', background='#fef3c7', foreground='#92400e')
        tree.tag_configure('Otro',                background='#f1f5f9', foreground='#334155')
        tree.tag_configure('missing',             background='#fee2e2', foreground='#991b1b')

        sc_y = ttk.Scrollbar(win, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sc_y.set)

        frame_tree = tk.Frame(win, bg='#f1f5f9')
        frame_tree.pack(fill='both', expand=True, padx=10, pady=8)
        tree.pack(in_=frame_tree, side='left', fill='both', expand=True)
        sc_y.pack(in_=frame_tree, side='right', fill='y')

        def cargar_docs():
            tree.delete(*tree.get_children())
            self.cursor.execute("""
                SELECT id, tipo, nombre_archivo, ruta_archivo, notas, fecha_registro
                FROM documentos_cotizacion
                WHERE cotizacion_id = ?
                ORDER BY tipo, fecha_registro
            """, (cot_id,))
            for row in self.cursor.fetchall():
                doc_id, tipo, nombre, ruta, notas, fecha = row
                existe = os.path.exists(ruta)
                tag = tipo if existe else 'missing'
                nombre_show = nombre + (' ⚠ archivo no encontrado' if not existe else '')
                tree.insert('', 'end', values=(doc_id, tipo, nombre_show,
                                               notas or '', fecha[:16]),
                            tags=(tag,))

        def abrir_archivo(event=None):
            sel = tree.selection()
            if not sel:
                return
            vals = tree.item(sel[0])['values']
            doc_id = vals[0]
            self.cursor.execute("SELECT ruta_archivo FROM documentos_cotizacion WHERE id=?",
                                (doc_id,))
            row = self.cursor.fetchone()
            if not row:
                return
            ruta = row[0]
            if not os.path.exists(ruta):
                messagebox.showerror("No encontrado",
                    f"El archivo ya no existe en:\n{ruta}", parent=win)
                return
            try:
                if platform.system() == 'Windows':
                    os.startfile(ruta)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', ruta])
                else:
                    subprocess.Popen(['xdg-open', ruta])
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def abrir_carpeta():
            """Abre la carpeta de documentos de esta cotización en el explorador."""
            try:
                if platform.system() == 'Windows':
                    os.startfile(base_docs)
                elif platform.system() == 'Darwin':
                    subprocess.Popen(['open', base_docs])
                else:
                    subprocess.Popen(['xdg-open', base_docs])
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        def agregar_documento():
            # Diálogo para elegir tipo
            dlg = tk.Toplevel(win)
            dlg.title("Agregar Documento")
            dlg.geometry("480x320")
            dlg.minsize(400, 240)
            dlg.resizable(True, True)
            _centrar(dlg, self.root)
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            dlg.configure(bg='#f8fafc')

            tk.Label(dlg, text="Tipo de documento:", font=('Arial', 10, 'bold'),
                     bg='#f8fafc').pack(pady=(18, 4))

            var_tipo = tk.StringVar(value='Orden de Compra')
            for t in tipos_carpeta:
                tk.Radiobutton(dlg, text=t, variable=var_tipo, value=t,
                               font=('Arial', 10), bg='#f8fafc').pack(anchor='w', padx=40)

            tk.Label(dlg, text="Notas (opcional):", font=('Arial', 9),
                     bg='#f8fafc').pack(pady=(10, 2))
            entry_notas = tk.Entry(dlg, font=('Arial', 9), width=40)
            entry_notas.pack()

            def seleccionar_archivo():
                tipo = var_tipo.get()
                notas = entry_notas.get().strip()
                carpeta_destino = tipos_carpeta[tipo]

                rutas = filedialog.askopenfilenames(
                    title=f"Seleccionar {tipo}",
                    filetypes=[
                        ("Documentos", "*.pdf *.xml *.docx *.xlsx *.png *.jpg *.jpeg"),
                        ("PDF", "*.pdf"), ("XML", "*.xml"), ("Todos", "*.*")
                    ],
                    parent=dlg
                )
                if not rutas:
                    return

                agregados = 0
                for ruta_orig in rutas:
                    nombre = os.path.basename(ruta_orig)
                    destino = os.path.join(carpeta_destino, nombre)

                    # Si ya existe, agregar sufijo numérico
                    base, ext = os.path.splitext(nombre)
                    contador = 1
                    while os.path.exists(destino):
                        destino = os.path.join(carpeta_destino, f"{base}_{contador}{ext}")
                        contador += 1
                    nombre_final = os.path.basename(destino)

                    try:
                        shutil.copy2(ruta_orig, destino)
                        self.cursor.execute("""
                            INSERT INTO documentos_cotizacion
                            (cotizacion_id, tipo, nombre_archivo, ruta_archivo, notas)
                            VALUES (?, ?, ?, ?, ?)
                        """, (cot_id, tipo, nombre_final, destino, notas or None))
                        agregados += 1
                    except Exception as e:
                        messagebox.showerror("Error", f"No se pudo copiar {nombre}:\n{e}",
                                             parent=dlg)

                self.conn.commit()
                dlg.destroy()
                cargar_docs()
                if agregados:
                    messagebox.showinfo("Éxito",
                        f"{agregados} archivo(s) guardado(s) en:\n{carpeta_destino}",
                        parent=win)

            tk.Button(dlg, text="📂 Seleccionar archivo(s)", command=seleccionar_archivo,
                      bg='#16a085', fg='white', font=('Arial', 10, 'bold'),
                      cursor='hand2', padx=14, pady=7).pack(pady=14)

        def eliminar_documento():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Advertencia", "Selecciona un documento", parent=win)
                return
            vals  = tree.item(sel[0])['values']
            doc_id = vals[0]
            nombre = vals[2]

            self.cursor.execute("SELECT ruta_archivo FROM documentos_cotizacion WHERE id=?",
                                (doc_id,))
            row = self.cursor.fetchone()
            if not row:
                return
            ruta = row[0]

            resp = messagebox.askyesnocancel(
                "Eliminar documento",
                f"¿Qué deseas hacer con '{nombre}'?\n\n"
                "  [Sí]    → Eliminar registro Y archivo del disco\n"
                "  [No]    → Eliminar solo el registro (mantener archivo)\n"
                "  [Cancelar] → No hacer nada",
                parent=win
            )
            if resp is None:
                return
            try:
                self.cursor.execute("DELETE FROM documentos_cotizacion WHERE id=?", (doc_id,))
                self.conn.commit()
                if resp and os.path.exists(ruta):
                    os.remove(ruta)
                cargar_docs()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)

        # Botones del toolbar
        for texto, cmd, color in [
            ('➕ Agregar',        agregar_documento, '#16a085'),
            ('🗂️ Abrir carpeta',  abrir_carpeta,     '#1a4b8c'),
            ('📂 Abrir archivo',  abrir_archivo,     '#d97706'),
            ('🗑️ Eliminar',       eliminar_documento,'#c0392b'),
        ]:
            tk.Button(tb, text=texto, command=cmd,
                      bg=color, fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=10, pady=4,
                      relief='raised', bd=1).pack(side='left', padx=3)

        # Nota de ruta
        nota_frame = tk.Frame(win, bg='#e8f4f8', pady=4)
        nota_frame.pack(fill='x', padx=10, pady=(0, 6))
        tk.Label(nota_frame,
                 text=f"📁  Carpeta: {base_docs}",
                 font=('Arial', 7), bg='#e8f4f8', fg='#2c3e50',
                 anchor='w').pack(fill='x', padx=8)

        tree.bind('<Double-1>', abrir_archivo)
        cargar_docs()
        win.grab_set()


    def _on_select_cotizacion(self):
        """Actualiza el panel de preview al seleccionar una cotización."""
        sel = self.tree_cotizaciones.selection()
        if not sel:
            return
        cot_id = self.tree_cotizaciones.item(sel[0])['values'][0]
        self._actualizar_preview_cot(cot_id)

    def _actualizar_preview_cot(self, cot_id):
        """Rellena el panel de preview con los datos de la cotización."""
        if not hasattr(self, '_pv_tree'):
            return

        self._pv_cot_id = cot_id

        # ── Datos generales ───────────────────────────────────────────────
        self.cursor.execute("""
            SELECT c.folio, c.fecha, c.estado, c.subtotal, c.iva, c.total,
                   c.monto_entregado, c.monto_pagado,
                   cl.nombre_comercial, cl.contacto
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.id = ?
        """, (cot_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        (folio, fecha, estado, subtotal, iva, total,
         entregado, pagado, cliente, contacto) = row

        entregado = entregado or 0
        pagado    = pagado    or 0
        pendiente = total - pagado

        # ── Avatar (2 iniciales del cliente) ─────────────────────────────
        partes   = (cliente or '').split()
        iniciales = (partes[0][0] + (partes[1][0] if len(partes) > 1 else '')).upper()
        self._pv_avatar.config(text=iniciales)

        # ── Folio, cliente, fecha ─────────────────────────────────────────
        self._pv_folio.config(text=folio)
        contacto_txt = f'  ·  {contacto}' if contacto else ''
        self._pv_cliente.config(text=f'{cliente}{contacto_txt}')
        self._pv_fecha.config(text=(fecha or '')[:10])

        # ── Estado badge ──────────────────────────────────────────────────
        estado_cfg = {
            'Pendiente':              ('#fef3c7', '#92400e'),
            'Programada':             ('#dbeafe', '#1e3a5f'),
            'Parcialmente Entregada': ('#ede9fe', '#5b21b6'),
            'Entregada':              ('#dcfce7', '#14532d'),
            'Facturada':              ('#cffafe', '#164e63'),
            'Pagada':                 ('#d1fae5', '#065f46'),
            'Cancelada':              ('#f1f5f9', '#6b7280'),
        }
        bg_e, fg_e = estado_cfg.get(estado, ('#f1f5f9', '#374151'))
        self._pv_estado.config(text=estado, bg=bg_e, fg=fg_e)

        # ── Días de antigüedad ────────────────────────────────────────────
        from datetime import date as _d
        try:
            dias = (_d.today() - _d.fromisoformat(str(fecha)[:10])).days
            if dias == 0:
                dias_txt, dias_col = '🆕 Hoy', '#16a34a'
            elif dias <= 7:
                dias_txt, dias_col = f'📅 {dias}d', '#374151'
            elif dias <= 30:
                dias_txt, dias_col = f'🟡 {dias}d', '#d97706'
            else:
                dias_txt, dias_col = f'🔴 {dias}d', '#dc2626'
        except Exception:
            dias_txt, dias_col = '', '#9ca3af'
        self._pv_dias.config(text=dias_txt, fg=dias_col)

        # ── KPIs ──────────────────────────────────────────────────────────
        self._pv_kpi_total.config(text=f'${total:,.2f}')
        self._pv_kpi_entregado.config(text=f'${entregado:,.2f}')
        self._pv_kpi_pagado.config(text=f'${pagado:,.2f}')

        # ── Etapas de seguimiento ─────────────────────────────────────────
        self.cursor.execute("""
            SELECT etapa, completada, referencia, fecha_etapa
            FROM seguimiento_etapas
            WHERE cotizacion_id = ?
        """, (cot_id,))
        seg = {r[0]: (r[1], r[2], r[3]) for r in self.cursor.fetchall()}

        for w in self._pv_seg_frame.winfo_children():
            w.destroy()

        etapas_def = [
            ('📋', 'Orden de Compra',     'OC'),
            ('🚚', 'Entregada',           'Entrega'),
            ('🧾', 'Facturada',           'Factura'),
            ('💳', 'Complemento de Pago', 'Complemento'),
            ('✅', 'Pagada',              'Pago'),
        ]

        for icono, etapa_key, etapa_short in etapas_def:
            comp, ref, fec = seg.get(etapa_key, (0, None, None))
            done = bool(comp)
            bg_row  = '#f0fdf4' if done else '#f8fafc'
            fg_name = '#14532d' if done else '#6b7280'
            fg_ref  = '#16a34a' if done else '#9ca3af'
            bdr_col = '#6ee7b7' if done else '#e2e8f0'

            row = tk.Frame(self._pv_seg_frame, bg=bg_row,
                           highlightbackground=bdr_col, highlightthickness=1)
            row.pack(fill='x', pady=2)

            tk.Label(row, text=icono, font=('Arial', 16),
                     bg=bg_row, padx=6, pady=4).pack(side='left')

            body = tk.Frame(row, bg=bg_row)
            body.pack(side='left', fill='x', expand=True, pady=4)
            tk.Label(body, text=etapa_key, font=('Arial', 9, 'bold'),
                     bg=bg_row, fg=fg_name, anchor='w').pack(fill='x')

            if done:
                detalle = ref or ''
                if fec:
                    detalle += (f'  ·  {str(fec)[:10]}' if detalle else str(fec)[:10])
                tk.Label(body, text=detalle or '—',
                         font=('Arial', 8), bg=bg_row,
                         fg=fg_ref, anchor='w').pack(fill='x')
            else:
                tk.Label(body, text='Pendiente',
                         font=('Arial', 8), bg=bg_row,
                         fg=fg_ref, anchor='w').pack(fill='x')

            mark = '✓' if done else '—'
            tk.Label(row, text=mark, font=('Arial', 10, 'bold'),
                     bg=bg_row, fg=fg_name, padx=8).pack(side='right')

        # ── Tabla de productos ────────────────────────────────────────────
        self._pv_tree.delete(*self._pv_tree.get_children())
        self.cursor.execute("""
            SELECT p.nombre, cd.cantidad, cd.precio_unitario, cd.subtotal
            FROM cotizacion_detalle cd
            JOIN productos p ON p.id = cd.producto_id
            WHERE cd.cotizacion_id = ?
            ORDER BY cd.id
        """, (cot_id,))
        for i, (nombre, cant, precio, sub_p) in enumerate(self.cursor.fetchall()):
            self._pv_tree.insert('', 'end',
                tags=('par' if i % 2 == 0 else 'impar',),
                values=(nombre, f'{cant:g}',
                        f'${precio:,.2f}', f'${sub_p:,.2f}'))

        # ── Resumen financiero ────────────────────────────────────────────
        self._pv_subtotal.config(text=f'${subtotal:,.2f}')
        self._pv_iva.config(text=f'${iva:,.2f}')
        self._pv_total.config(text=f'${total:,.2f}')
        self._pv_entregado.config(text=f'${entregado:,.2f}')
        self._pv_pagado.config(text=f'${pagado:,.2f}')
        # Pendiente con color dinámico
        pend_color = '#16a34a' if pendiente <= 0 else '#d97706'
        self._pv_pendiente.config(text=f'${pendiente:,.2f}', fg=pend_color)


    # ── SECCIÓN: CATÁLOGOS ─────────────────────────────────────────────────

