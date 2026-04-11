# -*- coding: utf-8 -*-
"""
ui/catalogos_clientes_mixin.py
Mixin: métodos de gestión de clientes.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

from ui.utils import centrar_ventana as _centrar, campo_error as _campo_error, campo_ok as _campo_ok


class _CatalogosClientesMixin:
    def cargar_clientes(self):
        """Carga la lista de clientes en la tabla"""
        # Limpiar tabla
        for item in self.tree_clientes.get_children():
            self.tree_clientes.delete(item)
        
        # Obtener término de búsqueda
        buscar = self.entry_buscar_cliente.get().strip().lower()

        # Consultar base de datos
        if buscar:
            self.cursor.execute("""
                SELECT id, nombre_comercial, razon_social, tipo, rfc,
                       regimen_fiscal, uso_cfdi, cp_fiscal,
                       contacto, telefono, email
                FROM clientes
                WHERE LOWER(nombre_comercial) LIKE ? OR LOWER(razon_social) LIKE ? OR LOWER(rfc) LIKE ?
                ORDER BY nombre_comercial
            """, (f'%{buscar}%', f'%{buscar}%', f'%{buscar}%'))
        else:
            self.cursor.execute("""
                SELECT id, nombre_comercial, razon_social, tipo, rfc,
                       regimen_fiscal, uso_cfdi, cp_fiscal,
                       contacto, telefono, email
                FROM clientes
                ORDER BY nombre_comercial
            """)
        
        # Insertar datos
        for row in self.cursor.fetchall():
            self.tree_clientes.insert('', 'end', values=row)

        n = len(self.tree_clientes.get_children())
        if hasattr(self, '_status_cli'):
            self._status_cli.config(
                text=f'{n} cliente{"s" if n!=1 else ""}  ·  doble clic para editar')
        if hasattr(self, '_actualizar_tabs_catalogos'):
            self._actualizar_tabs_catalogos()

    def nuevo_cliente(self):
        """Abre ventana para crear nuevo cliente"""
        self.ventana_cliente(modo='nuevo')
    
    def editar_cliente(self):
        """Abre ventana para editar cliente seleccionado"""
        seleccion = self.tree_clientes.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona un cliente para editar")
            return
        
        item = self.tree_clientes.item(seleccion[0])
        cliente_id = item['values'][0]
        self.ventana_cliente(modo='editar', cliente_id=cliente_id)
    
    def eliminar_cliente(self):
        """Elimina el cliente seleccionado"""
        seleccion = self.tree_clientes.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Por favor selecciona un cliente para eliminar")
            return
        
        item = self.tree_clientes.item(seleccion[0])
        cliente_id = item['values'][0]
        nombre = item['values'][1]
        
        respuesta = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Estás seguro de eliminar al cliente '{nombre}'?\n\nEsta acción no se puede deshacer."
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
                self.conn.commit()
                messagebox.showinfo("Éxito", "Cliente eliminado correctamente")
                self.cargar_clientes()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar el cliente:\n{str(e)}")
    
    def ventana_cliente(self, modo='nuevo', cliente_id=None, _prefill=None, _callback=None):
        """Ventana para crear o editar cliente con datos fiscales SAT."""
        # ── Catálogos SAT ──────────────────────────────────────────────────
        REGIMENES = [
            ('601', 'General de Ley Personas Morales'),
            ('603', 'Personas Morales con Fines no Lucrativos'),
            ('605', 'Sueldos y Salarios e Ingresos Asimilados'),
            ('606', 'Arrendamiento'),
            ('607', 'Régimen de Enajenación o Adquisición de Bienes'),
            ('608', 'Demás ingresos'),
            ('610', 'Residentes en el Extranjero sin EP en México'),
            ('611', 'Ingresos por Dividendos'),
            ('612', 'Personas Físicas con Actividades Empresariales'),
            ('614', 'Ingresos por intereses'),
            ('616', 'Sin obligaciones fiscales'),
            ('620', 'Sociedades Cooperativas de Producción'),
            ('621', 'Incorporación Fiscal'),
            ('622', 'Actividades Agrícolas, Ganaderas, Silvícolas'),
            ('623', 'Opcional para Grupos de Sociedades'),
            ('624', 'Coordinados'),
            ('625', 'Actividades Empresariales vía Plataformas Tecnológicas'),
            ('626', 'RESICO – Simplificado de Confianza'),
        ]
        USOS_CFDI = [
            ('G01', 'Adquisición de mercancias'),
            ('G02', 'Devoluciones, descuentos o bonificaciones'),
            ('G03', 'Gastos en general'),
            ('I01', 'Construcciones'),
            ('I02', 'Mobiliario y equipo de oficina'),
            ('I03', 'Equipo de transporte'),
            ('I04', 'Equipo de cómputo y accesorios'),
            ('I05', 'Dados, troqueles, moldes, matrices'),
            ('I06', 'Comunicaciones telefónicas'),
            ('I07', 'Comunicaciones satelitales'),
            ('I08', 'Otra maquinaria y equipo'),
            ('D01', 'Honorarios médicos y gastos hospitalarios'),
            ('D02', 'Gastos médicos por incapacidad'),
            ('D03', 'Gastos funerales'),
            ('D04', 'Donativos'),
            ('D10', 'Pagos por servicios educativos'),
            ('S01', 'Sin efectos fiscales'),
            ('CP01', 'Pagos'),
            ('CN01', 'Nómina'),
        ]
        reg_opts    = [f"{c} – {n}" for c, n in REGIMENES]
        uso_opts    = [f"{c} – {n}" for c, n in USOS_CFDI]

        # ── Cargar datos existentes ────────────────────────────────────────
        datos = {}
        if _prefill:
            datos.update(_prefill)
        if modo == 'editar' and cliente_id:
            self.cursor.execute("""
                SELECT nombre_comercial, razon_social, tipo, rfc, direccion,
                       contacto, telefono, email, regimen_fiscal, uso_cfdi, cp_fiscal
                FROM clientes WHERE id = ?
            """, (cliente_id,))
            row = self.cursor.fetchone()
            if row:
                keys = ['nombre_comercial', 'razon_social', 'tipo', 'rfc',
                        'direccion', 'contacto', 'telefono', 'email',
                        'regimen_fiscal', 'uso_cfdi', 'cp_fiscal']
                datos = {k: (v or '') for k, v in zip(keys, row)}

            # Auto-llenar desde facturas si faltan datos SAT
            if not datos.get('regimen_fiscal') or not datos.get('uso_cfdi'):
                rfc = datos.get('rfc', '')
                if rfc:
                    self.cursor.execute("""
                        SELECT uso_cfdi FROM facturas
                        WHERE rfc_receptor = ? AND uso_cfdi IS NOT NULL AND uso_cfdi != ''
                        ORDER BY fecha DESC LIMIT 1
                    """, (rfc,))
                    frow = self.cursor.fetchone()
                    if frow and not datos.get('uso_cfdi'):
                        datos['uso_cfdi'] = frow[0]

        # ── Ventana ────────────────────────────────────────────────────────
        ventana = tk.Toplevel(self.root)
        ventana.title('Nuevo Cliente' if modo == 'nuevo' else f"Editar Cliente — {datos.get('nombre_comercial','')}")
        ventana.geometry('580x660')
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

        # Cabecera
        hdr = tk.Frame(ventana, bg='#1e3a5f', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='👥  ' + ('Nuevo Cliente' if modo == 'nuevo' else 'Editar Cliente'),
                 font=('Arial', 11, 'bold'), bg='#1e3a5f', fg='white').pack(side='left', padx=12)

        # Canvas + scroll
        canvas = tk.Canvas(ventana, bg='#f1f5f9', highlightthickness=0)
        sb = ttk.Scrollbar(ventana, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        inner = tk.Frame(canvas, bg='#f1f5f9')
        wid = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))

        def section(parent, titulo, color='#1e3a5f'):
            hf = tk.Frame(parent, bg=color, pady=4)
            hf.pack(fill='x', padx=12, pady=(10, 0))
            tk.Label(hf, text=titulo, font=('Arial', 9, 'bold'),
                     bg=color, fg='white').pack(side='left', padx=8)
            return tk.Frame(parent, bg='#ffffff', padx=14, pady=8,
                            highlightbackground='#e2e8f0', highlightthickness=1)

        def field(parent, row, label, widget_type='entry', width=38,
                  required=False, values=None, height=3):
            lbl = label + ('*' if required else '')
            tk.Label(parent, text=lbl,
                     font=('Arial', 9, 'bold' if required else 'normal'),
                     bg='#ffffff', fg='#374151', anchor='w').grid(
                row=row, column=0, sticky='w', padx=(0, 10), pady=4)
            if widget_type == 'combo':
                w = ttk.Combobox(parent, values=values or [], state='readonly',
                                 width=width - 2, font=('Arial', 9))
            elif widget_type == 'text':
                w = tk.Text(parent, width=width, height=height,
                            font=('Arial', 9), relief='solid', bd=1)
            else:
                w = tk.Entry(parent, width=width, font=('Arial', 9),
                             relief='solid', bd=1)
            w.grid(row=row, column=1, sticky='ew', pady=4)
            parent.grid_columnconfigure(1, weight=1)
            return w

        # ── Sección: Datos Generales ───────────────────────────────────────
        sec1 = section(inner, '📋  Datos Generales')
        sec1.pack(fill='x', padx=12)

        e_nombre   = field(sec1, 0, 'Nombre Comercial', required=True)
        e_nombre.insert(0, datos.get('nombre_comercial', ''))
        lbl_err_nombre_cli = tk.Label(sec1, text='', font=('Arial', 8),
                                      fg='#dc2626', bg='white')
        lbl_err_nombre_cli.grid(row=1, column=1, sticky='w', pady=(0,2))

        e_razon    = field(sec1, 1, 'Razón Social')
        e_razon.insert(0, datos.get('razon_social', ''))

        c_tipo = field(sec1, 2, 'Tipo de Cliente', 'combo', required=True,
                       values=['Gobierno', 'Hotel', 'Empresa', 'Persona Física', 'Otro'])
        c_tipo.set(datos.get('tipo', 'Empresa'))

        e_rfc = field(sec1, 3, 'RFC')
        e_rfc.insert(0, datos.get('rfc', ''))

        e_dir = field(sec1, 4, 'Dirección', 'text', height=2)
        e_dir.insert('1.0', datos.get('direccion', ''))

        # ── Sección: Contacto ──────────────────────────────────────────────
        sec2 = section(inner, '📞  Contacto', '#374151')
        sec2.pack(fill='x', padx=12)

        e_contacto  = field(sec2, 0, 'Persona de Contacto')
        e_contacto.insert(0, datos.get('contacto', ''))

        e_telefono  = field(sec2, 1, 'Teléfono')
        e_telefono.insert(0, datos.get('telefono', ''))

        e_email     = field(sec2, 2, 'Email')
        e_email.insert(0, datos.get('email', ''))

        # ── Sección: Datos Fiscales SAT ────────────────────────────────────
        sec3 = section(inner, '🏛️  Datos Fiscales SAT', '#7c3aed')
        sec3.pack(fill='x', padx=12, pady=(0, 10))

        tk.Label(sec3, text='Estos datos se usan al generar CFDIs para este cliente.',
                 font=('Arial', 7, 'italic'), bg='#ffffff',
                 fg='#9ca3af').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))

        c_regimen = field(sec3, 1, 'Régimen Fiscal', 'combo', values=reg_opts)
        # Pre-seleccionar por código
        cur_reg = datos.get('regimen_fiscal', '')
        if cur_reg:
            match = next((o for o in reg_opts if o.startswith(cur_reg)), '')
            if match:
                c_regimen.set(match)

        c_uso = field(sec3, 2, 'Uso de CFDI', 'combo', values=uso_opts)
        cur_uso = datos.get('uso_cfdi', '')
        if cur_uso:
            match = next((o for o in uso_opts if o.startswith(cur_uso)), '')
            if match:
                c_uso.set(match)

        e_cp = field(sec3, 3, 'C.P. Fiscal')
        e_cp.insert(0, datos.get('cp_fiscal', ''))

        # Nota de auto-llenado si se detectó dato desde factura
        if modo == 'editar' and datos.get('uso_cfdi'):
            tk.Label(sec3, text='ℹ️ Datos detectados desde facturas importadas.',
                     font=('Arial', 7), bg='#ffffff', fg='#0e7490'
                     ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(0, 2))

        # ── Pie: botones ───────────────────────────────────────────────────
        foot = tk.Frame(ventana, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')

        def guardar(event=None):
            _campo_ok(e_nombre, lbl_err_nombre_cli)
            nombre = e_nombre.get().strip()
            tipo   = c_tipo.get()
            ok = True
            if not nombre:
                _campo_error(e_nombre, lbl_err_nombre_cli, "El nombre comercial es obligatorio")
                ok = False
            if not tipo:
                messagebox.showwarning('Advertencia', 'Selecciona un tipo de cliente',
                                       parent=ventana)
                if ok: return
                return
            if not ok:
                return

            # Extraer código de régimen y uso (antes del " – ")
            reg_val = c_regimen.get().split(' – ')[0] if c_regimen.get() else ''
            uso_val = c_uso.get().split(' – ')[0]     if c_uso.get()     else ''

            datos_save = {
                'nombre_comercial': nombre,
                'razon_social':     e_razon.get().strip(),
                'tipo':             tipo,
                'rfc':              e_rfc.get().strip().upper(),
                'direccion':        e_dir.get('1.0', 'end-1c').strip(),
                'contacto':         e_contacto.get().strip(),
                'telefono':         e_telefono.get().strip(),
                'email':            e_email.get().strip(),
                'regimen_fiscal':   reg_val,
                'uso_cfdi':         uso_val,
                'cp_fiscal':        e_cp.get().strip(),
            }
            try:
                if modo == 'nuevo':
                    self.cursor.execute("""
                        INSERT INTO clientes
                        (nombre_comercial, razon_social, tipo, rfc, direccion,
                         contacto, telefono, email, regimen_fiscal, uso_cfdi, cp_fiscal)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, tuple(datos_save.values()))
                    msg = 'Cliente registrado correctamente'
                else:
                    self.cursor.execute("""
                        UPDATE clientes SET
                        nombre_comercial=?, razon_social=?, tipo=?, rfc=?,
                        direccion=?, contacto=?, telefono=?, email=?,
                        regimen_fiscal=?, uso_cfdi=?, cp_fiscal=?
                        WHERE id=?
                    """, (*datos_save.values(), cliente_id))
                    msg = 'Cliente actualizado correctamente'
                self.conn.commit()
                new_cli_id = self.cursor.lastrowid if modo == 'nuevo' else cliente_id
                messagebox.showinfo('Éxito', msg, parent=ventana)
                self.cargar_clientes()
                ventana.destroy()
                if _callback:
                    _callback(new_cli_id)
            except sqlite3.Error as e:
                messagebox.showerror('Error', str(e), parent=ventana)

        ventana.bind('<Return>', guardar)
        tk.Button(foot, text='💾 Guardar', command=guardar,
                  bg='#0f7b5e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=12)
        tk.Button(foot, text='Cancelar', command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='right', padx=12)

        e_nombre.focus()


    # (removed - rebuilt in new ERP UI)

