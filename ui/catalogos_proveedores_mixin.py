# -*- coding: utf-8 -*-
"""
ui/catalogos_proveedores_mixin.py
Mixin: métodos de gestión de proveedores.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

from ui.utils import centrar_ventana as _centrar, campo_error as _campo_error, campo_ok as _campo_ok


class _CatalogosProveedoresMixin:
    # ── PROVEEDORES ────────────────────────────────────────────────────────
    def cargar_proveedores(self):
        """Carga la lista de proveedores en la tabla"""
        for item in self.tree_proveedores.get_children():
            self.tree_proveedores.delete(item)
        buscar = self.entry_buscar_proveedor.get().strip().lower()
        if buscar:
            self.cursor.execute("""
                SELECT id, nombre, rfc, regimen_fiscal, cp_fiscal,
                       contacto, telefono, email, notas
                FROM proveedores
                WHERE LOWER(nombre) LIKE ? OR LOWER(rfc) LIKE ? OR LOWER(contacto) LIKE ?
                ORDER BY nombre
            """, (f'%{buscar}%', f'%{buscar}%', f'%{buscar}%'))
        else:
            self.cursor.execute("""
                SELECT id, nombre, rfc, regimen_fiscal, cp_fiscal,
                       contacto, telefono, email, notas
                FROM proveedores ORDER BY nombre
            """)
        for row in self.cursor.fetchall():
            self.tree_proveedores.insert('', 'end', values=row)

    def nuevo_proveedor(self):
        self._ventana_proveedor(modo='nuevo')

    def editar_proveedor(self):
        sel = self.tree_proveedores.selection()
        if not sel:
            messagebox.showwarning("Advertencia", "Selecciona un proveedor para editar")
            return
        prov_id = self.tree_proveedores.item(sel[0])['values'][0]
        self._ventana_proveedor(modo='editar', prov_id=prov_id)

    def eliminar_proveedor(self):
        sel = self.tree_proveedores.selection()
        if not sel:
            messagebox.showwarning("Advertencia", "Selecciona un proveedor para eliminar")
            return
        prov_id = self.tree_proveedores.item(sel[0])['values'][0]
        nombre  = self.tree_proveedores.item(sel[0])['values'][1]
        if messagebox.askyesno("Confirmar",
                               f"¿Eliminar al proveedor '{nombre}'?"):
            try:
                self.cursor.execute("DELETE FROM proveedores WHERE id = ?", (prov_id,))
                self.conn.commit()
                self.cargar_proveedores()
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e))

    def _ventana_proveedor(self, modo='nuevo', prov_id=None, _prefill=None, _callback=None):
        """Ventana para crear o editar proveedor con datos fiscales SAT."""
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
        reg_opts = [f"{c} – {n}" for c, n in REGIMENES]

        datos = {}
        if _prefill:
            datos.update(_prefill)
        if modo == 'editar' and prov_id:
            self.cursor.execute("""
                SELECT nombre, razon_social, rfc, direccion, contacto,
                       telefono, email, notas, regimen_fiscal, cp_fiscal
                FROM proveedores WHERE id = ?
            """, (prov_id,))
            row = self.cursor.fetchone()
            if row:
                keys = ['nombre', 'razon_social', 'rfc', 'direccion', 'contacto',
                        'telefono', 'email', 'notas', 'regimen_fiscal', 'cp_fiscal']
                datos = {k: (v or '') for k, v in zip(keys, row)}

        ventana = tk.Toplevel(self.root)
        ventana.title('Nuevo Proveedor' if modo == 'nuevo' else f"Editar Proveedor — {datos.get('nombre','')}")
        ventana.geometry('560x580')
        _centrar(ventana, self.root)
        ventana.resizable(False, False)
        ventana.configure(bg='#f1f5f9')
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())

        hdr = tk.Frame(ventana, bg='#92400e', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🏭  ' + ('Nuevo Proveedor' if modo == 'nuevo' else 'Editar Proveedor'),
                 font=('Arial', 11, 'bold'), bg='#92400e', fg='white').pack(side='left', padx=12)

        canvas = tk.Canvas(ventana, bg='#f1f5f9', highlightthickness=0)
        sb = ttk.Scrollbar(ventana, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        canvas.pack(fill='both', expand=True)
        inner = tk.Frame(canvas, bg='#f1f5f9')
        wid = canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(wid, width=e.width))

        def section(parent, titulo, color):
            hf = tk.Frame(parent, bg=color, pady=4)
            hf.pack(fill='x', padx=12, pady=(10, 0))
            tk.Label(hf, text=titulo, font=('Arial', 9, 'bold'),
                     bg=color, fg='white').pack(side='left', padx=8)
            fr = tk.Frame(parent, bg='#ffffff', padx=14, pady=8,
                          highlightbackground='#e2e8f0', highlightthickness=1)
            fr.pack(fill='x', padx=12)
            fr.grid_columnconfigure(1, weight=1)
            return fr

        def field(parent, row, label, wtype='entry', width=38, values=None,
                  required=False, height=3):
            lbl = label + ('*' if required else '')
            tk.Label(parent, text=lbl,
                     font=('Arial', 9, 'bold' if required else 'normal'),
                     bg='#ffffff', fg='#374151', anchor='w').grid(
                row=row, column=0, sticky='w', padx=(0, 10), pady=4)
            if wtype == 'combo':
                w = ttk.Combobox(parent, values=values or [], state='readonly',
                                 width=width - 2, font=('Arial', 9))
            elif wtype == 'text':
                w = tk.Text(parent, width=width, height=height,
                            font=('Arial', 9), relief='solid', bd=1)
            else:
                w = tk.Entry(parent, width=width, font=('Arial', 9),
                             relief='solid', bd=1)
            w.grid(row=row, column=1, sticky='ew', pady=4)
            return w

        # Sección General
        sec1 = section(inner, '📦  Datos Generales', '#92400e')
        e_nombre  = field(sec1, 0, 'Nombre', required=True)
        e_nombre.insert(0, datos.get('nombre', ''))
        lbl_err_prov = tk.Label(sec1, text='', font=('Arial', 8),
                                fg='#dc2626', bg='#ffffff')
        lbl_err_prov.grid(row=1, column=1, sticky='w', pady=(0,2))
        e_razon   = field(sec1, 1, 'Razón Social')
        e_razon.insert(0, datos.get('razon_social', ''))
        e_rfc     = field(sec1, 2, 'RFC')
        e_rfc.insert(0, datos.get('rfc', ''))
        e_dir     = field(sec1, 3, 'Dirección', 'text', height=2)
        e_dir.insert('1.0', datos.get('direccion', ''))

        # Sección Contacto
        sec2 = section(inner, '📞  Contacto', '#374151')
        e_contacto = field(sec2, 0, 'Persona de Contacto')
        e_contacto.insert(0, datos.get('contacto', ''))
        e_tel      = field(sec2, 1, 'Teléfono')
        e_tel.insert(0, datos.get('telefono', ''))
        e_email    = field(sec2, 2, 'Email')
        e_email.insert(0, datos.get('email', ''))
        e_notas    = field(sec2, 3, 'Notas', 'text', height=2)
        e_notas.insert('1.0', datos.get('notas', ''))

        # Sección SAT
        sec3 = section(inner, '🏛️  Datos Fiscales SAT', '#7c3aed')
        tk.Label(sec3, text='Datos del emisor para CFDIs de compra.',
                 font=('Arial', 7, 'italic'), bg='#ffffff',
                 fg='#9ca3af').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 4))
        c_regimen = field(sec3, 1, 'Régimen Fiscal', 'combo', values=reg_opts)
        cur_reg = datos.get('regimen_fiscal', '')
        if cur_reg:
            match = next((o for o in reg_opts if o.startswith(cur_reg)), '')
            if match:
                c_regimen.set(match)
        e_cp = field(sec3, 2, 'C.P. Fiscal')
        e_cp.insert(0, datos.get('cp_fiscal', ''))
        tk.Label(sec3, text='',bg='#ffffff').grid(row=3, column=0, pady=(0,6))

        # Pie
        foot = tk.Frame(ventana, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')

        def guardar(event=None):
            _campo_ok(e_nombre, lbl_err_prov)
            nombre = e_nombre.get().strip()
            if not nombre:
                _campo_error(e_nombre, lbl_err_prov, "El nombre es obligatorio")
                return
            reg_val = c_regimen.get().split(' – ')[0] if c_regimen.get() else ''
            vals_dict = {
                'nombre':        nombre,
                'razon_social':  e_razon.get().strip(),
                'rfc':           e_rfc.get().strip().upper(),
                'direccion':     e_dir.get('1.0', 'end-1c').strip(),
                'contacto':      e_contacto.get().strip(),
                'telefono':      e_tel.get().strip(),
                'email':         e_email.get().strip(),
                'notas':         e_notas.get('1.0', 'end-1c').strip(),
                'regimen_fiscal':reg_val,
                'cp_fiscal':     e_cp.get().strip(),
            }
            try:
                if modo == 'nuevo':
                    self.cursor.execute("""
                        INSERT INTO proveedores
                        (nombre, razon_social, rfc, direccion, contacto,
                         telefono, email, notas, regimen_fiscal, cp_fiscal)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, tuple(vals_dict.values()))
                else:
                    self.cursor.execute("""
                        UPDATE proveedores SET
                        nombre=?, razon_social=?, rfc=?, direccion=?,
                        contacto=?, telefono=?, email=?, notas=?,
                        regimen_fiscal=?, cp_fiscal=?
                        WHERE id=?
                    """, (*vals_dict.values(), prov_id))
                self.conn.commit()
                new_prov_id = self.cursor.lastrowid if modo == 'nuevo' else prov_id
                self.cargar_proveedores()
                ventana.destroy()
                if _callback:
                    _callback(new_prov_id)
            except sqlite3.Error as e:
                messagebox.showerror('Error', str(e), parent=ventana)

        ventana.bind('<Return>', guardar)
        tk.Button(foot, text='💾 Guardar', command=guardar,
                  bg='#92400e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=16, pady=6).pack(side='left', padx=12)
        tk.Button(foot, text='Cancelar', command=ventana.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=12, pady=6).pack(side='right', padx=12)
        e_nombre.focus()


    # ── Exportaciones CSV ────────────────────────────────────────────────────

