#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/configuracion.py
Sección de Configuración del sistema.
Pestañas: Empresa · Comercial · PDF/Documentos · Respaldo
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import shutil
from datetime import datetime
import sqlite3
import app_config
import sesion
import db_connection
from ui.login import hash_nuevo, verificar_password, USERS_DB


class Configuracion:
    """
    Componente de UI para la sección Configuración.
    Recibe `sistema` (instancia de SistemaGestion) como única dependencia.
    """

    def __init__(self, sistema):
        self.sistema = sistema
        self.root    = sistema.root
        self.C       = sistema.C
        self._frame  = None
        self._prefs  = {}          # copia de trabajo de las preferencias actuales
        self._empresa_id = sistema.empresa.get('id', '') if sistema.empresa else ''

    # ──────────────────────────────────────────────────────────────────────────
    def crear_seccion(self):
        """Construye el frame de la sección y lo registra en sistema._secciones."""
        self._frame = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['configuracion'] = self._frame
        # Conexión a la BD central de usuarios (independiente de la empresa)
        self._uconn, self._ucursor = db_connection.conectar_usuarios()
        self._construir()

    # ──────────────────────────────────────────────────────────────────────────
    def _construir(self):
        C = self.C

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self._frame, bg=C['nav_bg'], height=44)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)
        tk.Label(hdr, text='⚙  Configuración del Sistema',
                 font=('Arial', 12, 'bold'),
                 bg=C['nav_bg'], fg='white').pack(side='left', padx=16, anchor='center')

        # ── Notebook de pestañas ───────────────────────────────────────────────
        style = ttk.Style()
        style.configure('Config.TNotebook', background=C['content_bg'])
        style.configure('Config.TNotebook.Tab',
                        padding=[14, 6], font=('Arial', 9, 'bold'))

        nb = ttk.Notebook(self._frame, style='Config.TNotebook')
        nb.pack(fill='both', expand=True, padx=16, pady=12)

        self._tab_empresa   = tk.Frame(nb, bg=C['form_bg'])
        self._tab_comercial = tk.Frame(nb, bg=C['form_bg'])
        self._tab_pdf       = tk.Frame(nb, bg=C['form_bg'])
        self._tab_respaldo  = tk.Frame(nb, bg=C['form_bg'])
        self._tab_usuarios  = tk.Frame(nb, bg=C['form_bg'])
        self._tab_mis_rutas = tk.Frame(nb, bg=C['form_bg'])

        nb.add(self._tab_empresa,   text='🏢  Empresa')
        nb.add(self._tab_comercial, text='💰  Comercial')
        nb.add(self._tab_pdf,       text='📄  PDF / Documentos')
        nb.add(self._tab_respaldo,  text='💾  Respaldo')
        nb.add(self._tab_usuarios,  text='👤  Usuarios')
        nb.add(self._tab_mis_rutas, text='📁  Mis Rutas PDF')

        self._build_tab_empresa()
        self._build_tab_comercial()
        self._build_tab_pdf()
        self._build_tab_respaldo()
        self._build_tab_usuarios()
        self._build_tab_mis_rutas()

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: EMPRESA
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_empresa(self):
        C  = self.C
        fr = self._tab_empresa
        emp = self.sistema.empresa or {}

        tk.Label(fr, text='Datos de la empresa activa',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(16, 4))
        tk.Label(fr, text='Los cambios se guardan en config.json y se aplican de inmediato.',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(anchor='w', padx=20, pady=(0, 12))

        form = tk.Frame(fr, bg=C['form_bg'])
        form.pack(fill='x', padx=20)

        campos = [
            ('Nombre comercial',   'nombre'),
            ('Razón social',       'razon_social'),
            ('RFC',                'rfc'),
            ('E-mail',             'email'),
            ('Teléfono',           'telefono'),
            ('Dirección',          'direccion'),
        ]
        self._emp_vars = {}
        for i, (label, key) in enumerate(campos):
            tk.Label(form, text=label, font=('Arial', 9), bg=C['form_bg'],
                     fg=C['text_secondary'], width=18, anchor='e').grid(
                row=i, column=0, padx=(0, 8), pady=5, sticky='e')
            var = tk.StringVar(value=emp.get(key, ''))
            entry = tk.Entry(form, textvariable=var, font=('Arial', 10),
                             width=48, relief='solid', bd=1)
            entry.grid(row=i, column=1, pady=5, sticky='w')
            self._emp_vars[key] = var

        # RFC — solo lectura (cambiar RFC tiene implicaciones fiscales)
        # Lo mostramos pero deshabilitado
        form.grid_slaves(row=2, column=1)[0].config(state='disabled',
                                                     disabledbackground='#f1f5f9',
                                                     disabledforeground='#6b7280')

        tk.Button(fr, text='💾  Guardar datos de empresa',
                  font=('Arial', 10, 'bold'),
                  bg=C['accent'], fg='white', cursor='hand2',
                  activebackground=C['accent_dark'], activeforeground='white',
                  bd=0, padx=18, pady=8,
                  command=self._guardar_empresa).pack(anchor='w', padx=20, pady=16)

    def _guardar_empresa(self):
        datos = {k: v.get().strip() for k, v in self._emp_vars.items()}
        if not datos['nombre']:
            messagebox.showwarning('Campo requerido', 'El nombre comercial no puede estar vacío.')
            return

        app_config.guardar_empresa(self._empresa_id, datos)

        # Actualizar dict global EMPRESA en main
        import main as _main
        _main.EMPRESA.update({
            'nombre':    datos.get('nombre', ''),
            'email':     datos.get('email', ''),
            'telefono':  datos.get('telefono', ''),
            'direccion': datos.get('direccion', ''),
        })
        # Actualizar dict en sistema.empresa
        self.sistema.empresa.update(datos)

        messagebox.showinfo('Guardado', 'Datos de empresa actualizados correctamente.')

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: COMERCIAL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_comercial(self):
        C  = self.C
        fr = self._tab_comercial

        tk.Label(fr, text='Parámetros comerciales',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(16, 2))
        tk.Label(fr, text='Los porcentajes de utilidad se aplican al crear cotizaciones según el tipo de cliente.',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(anchor='w', padx=20, pady=(0, 12))

        # IVA default
        iva_fr = tk.Frame(fr, bg=C['form_bg'])
        iva_fr.pack(fill='x', padx=20, pady=(0, 12))
        tk.Label(iva_fr, text='IVA por defecto (%):',
                 font=('Arial', 9), bg=C['form_bg'],
                 fg=C['text_secondary'], width=22, anchor='e').pack(side='left')
        self._iva_var = tk.StringVar(value=str(app_config.IVA_DEFAULT[0]))
        tk.Entry(iva_fr, textvariable=self._iva_var, font=('Arial', 10),
                 width=8, relief='solid', bd=1).pack(side='left', padx=8)
        tk.Label(iva_fr, text='(ej. 16 para 16 %)',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(side='left')

        # Utilidades por tipo de cliente
        tk.Label(fr, text='Porcentajes de utilidad por tipo de cliente',
                 font=('Arial', 9, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(4, 4))

        util_outer = tk.Frame(fr, bg=C['form_bg'])
        util_outer.pack(fill='both', expand=True, padx=20)

        # Tabla editable con Treeview + botones
        cols_tree = tk.Frame(util_outer, bg=C['form_bg'])
        cols_tree.pack(side='left', fill='both', expand=True)

        self._tree_util = ttk.Treeview(cols_tree,
            columns=('tipo', 'utilidad'), show='headings', height=8)
        self._tree_util.heading('tipo',     text='Tipo de cliente')
        self._tree_util.heading('utilidad', text='Utilidad (%)')
        self._tree_util.column('tipo',     width=220)
        self._tree_util.column('utilidad', width=100, anchor='center')
        self._tree_util.pack(fill='both', expand=True)

        # Botones a la derecha
        btn_fr = tk.Frame(util_outer, bg=C['form_bg'])
        btn_fr.pack(side='left', padx=(10, 0), anchor='n', pady=2)
        for txt, cmd in [('➕ Agregar', self._agregar_utilidad),
                         ('✏️ Editar',   self._editar_utilidad),
                         ('🗑 Eliminar', self._eliminar_utilidad)]:
            tk.Button(btn_fr, text=txt, font=('Arial', 9),
                      bg=C['toolbar_bg'], fg=C['text_dark'],
                      cursor='hand2', bd=0, padx=10, pady=6,
                      relief='flat',
                      command=cmd).pack(fill='x', pady=2)

        self._recargar_tree_util()

        tk.Button(fr, text='💾  Guardar configuración comercial',
                  font=('Arial', 10, 'bold'),
                  bg=C['accent'], fg='white', cursor='hand2',
                  activebackground=C['accent_dark'], activeforeground='white',
                  bd=0, padx=18, pady=8,
                  command=self._guardar_comercial).pack(anchor='w', padx=20, pady=16)

    def _recargar_tree_util(self):
        for row in self._tree_util.get_children():
            self._tree_util.delete(row)
        for tipo, pct in app_config.UTILIDAD.items():
            self._tree_util.insert('', 'end', values=(tipo, pct))

    def _agregar_utilidad(self):
        dlg = _DialogoCampo(self.root, 'Agregar tipo de cliente',
                            [('Tipo de cliente', ''), ('Utilidad (%)', '0')])
        if dlg.resultado:
            tipo, pct = dlg.resultado
            tipo = tipo.strip()
            if not tipo:
                return
            try:
                pct = float(pct)
            except ValueError:
                messagebox.showwarning('Valor inválido', 'La utilidad debe ser un número.')
                return
            app_config.UTILIDAD[tipo] = pct
            self._recargar_tree_util()

    def _editar_utilidad(self):
        sel = self._tree_util.selection()
        if not sel:
            messagebox.showwarning('Selección', 'Selecciona un tipo de cliente.')
            return
        tipo, pct = self._tree_util.item(sel[0])['values']
        dlg = _DialogoCampo(self.root, f'Editar — {tipo}',
                            [('Tipo de cliente', tipo), ('Utilidad (%)', str(pct))])
        if dlg.resultado:
            nuevo_tipo, nuevo_pct = dlg.resultado
            nuevo_tipo = nuevo_tipo.strip()
            if not nuevo_tipo:
                return
            try:
                nuevo_pct = float(nuevo_pct)
            except ValueError:
                messagebox.showwarning('Valor inválido', 'La utilidad debe ser un número.')
                return
            if nuevo_tipo != tipo:
                del app_config.UTILIDAD[tipo]
            app_config.UTILIDAD[nuevo_tipo] = nuevo_pct
            self._recargar_tree_util()

    def _eliminar_utilidad(self):
        sel = self._tree_util.selection()
        if not sel:
            messagebox.showwarning('Selección', 'Selecciona un tipo de cliente.')
            return
        tipo = self._tree_util.item(sel[0])['values'][0]
        if messagebox.askyesno('Confirmar', f'¿Eliminar el tipo "{tipo}"?'):
            app_config.UTILIDAD.pop(tipo, None)
            self._recargar_tree_util()

    def _guardar_comercial(self):
        try:
            iva = int(self._iva_var.get().strip())
            if iva not in (0, 8, 16):
                raise ValueError
        except ValueError:
            messagebox.showwarning('Valor inválido',
                                   'El IVA debe ser 0, 8 o 16.')
            return

        prefs = app_config.cargar_preferencias(self._empresa_id)
        prefs['comercial']['iva_default'] = iva
        prefs['comercial']['utilidad'] = dict(app_config.UTILIDAD)
        app_config.guardar_preferencias(self._empresa_id, prefs)
        messagebox.showinfo('Guardado', 'Configuración comercial guardada.')

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: PDF / DOCUMENTOS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_pdf(self):
        C  = self.C
        fr = self._tab_pdf

        tk.Label(fr, text='Configuración de PDFs y cotizaciones',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(16, 2))
        tk.Label(fr,
                 text='Estos valores se usan al generar cotizaciones, notas de remisión y facturas.',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(anchor='w', padx=20, pady=(0, 10))

        form = tk.Frame(fr, bg=C['form_bg'])
        form.pack(fill='x', padx=20)

        pdf = app_config.PDF_CONFIG
        self._pdf_vars = {}

        # Logo (campo especial con botón explorar)
        tk.Label(form, text='Logo (ruta archivo):', font=('Arial', 9),
                 bg=C['form_bg'], fg=C['text_secondary'],
                 width=22, anchor='e').grid(row=0, column=0, padx=(0, 8), pady=6, sticky='e')
        logo_fr = tk.Frame(form, bg=C['form_bg'])
        logo_fr.grid(row=0, column=1, pady=6, sticky='w')
        self._pdf_vars['logo_path'] = tk.StringVar(value=pdf.get('logo_path', 'logo_clf.jpg'))
        tk.Entry(logo_fr, textvariable=self._pdf_vars['logo_path'],
                 font=('Arial', 10), width=38, relief='solid', bd=1).pack(side='left')
        tk.Button(logo_fr, text='📂', font=('Arial', 10),
                  bg=C['toolbar_bg'], fg=C['text_dark'], cursor='hand2',
                  bd=0, padx=6, relief='flat',
                  command=self._explorar_logo).pack(side='left', padx=4)

        # Campos de texto libres
        campos_pdf = [
            ('Vigencia de cotización:',  'vigencia',       30),
            ('Lugar de entrega:',        'lugar_entrega',  30),
            ('Tiempo de entrega:',       'tiempo_entrega', 55),
            ('Leyenda moneda:',          'moneda',         55),
            ('Leyenda precios:',         'cambios',        55),
        ]
        for i, (label, key, width) in enumerate(campos_pdf, start=1):
            tk.Label(form, text=label, font=('Arial', 9),
                     bg=C['form_bg'], fg=C['text_secondary'],
                     width=22, anchor='e').grid(row=i, column=0,
                                                padx=(0, 8), pady=6, sticky='e')
            var = tk.StringVar(value=pdf.get(key, ''))
            tk.Entry(form, textvariable=var, font=('Arial', 10),
                     width=width, relief='solid', bd=1).grid(
                row=i, column=1, pady=6, sticky='w')
            self._pdf_vars[key] = var

        tk.Button(fr, text='💾  Guardar configuración de PDF',
                  font=('Arial', 10, 'bold'),
                  bg=C['accent'], fg='white', cursor='hand2',
                  activebackground=C['accent_dark'], activeforeground='white',
                  bd=0, padx=18, pady=8,
                  command=self._guardar_pdf).pack(anchor='w', padx=20, pady=16)

    def _explorar_logo(self):
        ruta = filedialog.askopenfilename(
            title='Seleccionar logo',
            filetypes=[('Imágenes', '*.jpg *.jpeg *.png *.bmp'), ('Todos', '*.*')]
        )
        if ruta:
            self._pdf_vars['logo_path'].set(ruta)

    def _guardar_pdf(self):
        prefs = app_config.cargar_preferencias(self._empresa_id)
        for key, var in self._pdf_vars.items():
            prefs['pdf'][key] = var.get().strip()
        app_config.guardar_preferencias(self._empresa_id, prefs)
        messagebox.showinfo('Guardado', 'Configuración de PDF guardada.')

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: RESPALDO
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_respaldo(self):
        C  = self.C
        fr = self._tab_respaldo

        tk.Label(fr, text='Respaldo de la base de datos',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(16, 2))
        tk.Label(fr,
                 text='Crea una copia del archivo .db con marca de tiempo en la carpeta indicada.',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(anchor='w', padx=20, pady=(0, 12))

        # Carpeta de respaldo
        carp_fr = tk.Frame(fr, bg=C['form_bg'])
        carp_fr.pack(fill='x', padx=20, pady=(0, 10))
        tk.Label(carp_fr, text='Carpeta de respaldo:',
                 font=('Arial', 9), bg=C['form_bg'],
                 fg=C['text_secondary'], width=20, anchor='e').pack(side='left')

        prefs_resp = app_config.cargar_preferencias(self._empresa_id).get('respaldo', {})
        self._respaldo_carpeta = tk.StringVar(value=prefs_resp.get('carpeta', ''))

        tk.Entry(carp_fr, textvariable=self._respaldo_carpeta,
                 font=('Arial', 10), width=40, relief='solid', bd=1).pack(
            side='left', padx=8)
        tk.Button(carp_fr, text='📂', font=('Arial', 10),
                  bg=C['toolbar_bg'], fg=C['text_dark'], cursor='hand2',
                  bd=0, padx=6, relief='flat',
                  command=self._explorar_carpeta_respaldo).pack(side='left')

        tk.Button(fr, text='💾  Guardar carpeta de respaldo',
                  font=('Arial', 9),
                  bg=C['toolbar_bg'], fg=C['text_dark'], cursor='hand2',
                  bd=0, padx=14, pady=6, relief='flat',
                  command=self._guardar_respaldo_config).pack(
            anchor='w', padx=20, pady=(0, 16))

        # Separador
        tk.Frame(fr, bg=C['border'], height=1).pack(fill='x', padx=20, pady=4)

        # Sección "Hacer respaldo ahora"
        tk.Label(fr, text='Hacer respaldo ahora',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(12, 4))

        info_fr = tk.Frame(fr, bg=C['bg_success'], bd=1, relief='solid')
        info_fr.pack(fill='x', padx=20, pady=(0, 10))

        emp = self.sistema.empresa or {}
        db_path = emp.get('db_path', '—')
        tk.Label(info_fr, text=f'Base de datos activa:\n{db_path}',
                 font=('Arial', 8), bg=C['bg_success'],
                 fg=C['text_secondary'], justify='left',
                 padx=10, pady=6).pack(anchor='w')

        self._lbl_ultimo_respaldo = tk.Label(fr, text='',
                 font=('Arial', 8), bg=C['form_bg'], fg=C['text_muted'])
        self._lbl_ultimo_respaldo.pack(anchor='w', padx=20)

        tk.Button(fr, text='⬇  Hacer respaldo ahora',
                  font=('Arial', 11, 'bold'),
                  bg=C['accent2'], fg='white', cursor='hand2',
                  activebackground=C['accent3'], activeforeground='white',
                  bd=0, padx=20, pady=10,
                  command=self._hacer_respaldo).pack(anchor='w', padx=20, pady=10)

    def _explorar_carpeta_respaldo(self):
        carpeta = filedialog.askdirectory(title='Seleccionar carpeta de respaldo')
        if carpeta:
            self._respaldo_carpeta.set(carpeta)

    def _guardar_respaldo_config(self):
        prefs = app_config.cargar_preferencias(self._empresa_id)
        prefs['respaldo']['carpeta'] = self._respaldo_carpeta.get().strip()
        app_config.guardar_preferencias(self._empresa_id, prefs)
        messagebox.showinfo('Guardado', 'Carpeta de respaldo guardada.')

    def _hacer_respaldo(self):
        carpeta = self._respaldo_carpeta.get().strip()
        if not carpeta:
            carpeta = filedialog.askdirectory(title='Seleccionar carpeta de respaldo')
            if not carpeta:
                return
            self._respaldo_carpeta.set(carpeta)

        if not os.path.isdir(carpeta):
            try:
                os.makedirs(carpeta, exist_ok=True)
            except Exception as e:
                messagebox.showerror('Error', f'No se pudo crear la carpeta:\n{e}')
                return

        emp     = self.sistema.empresa or {}
        db_path = emp.get('db_path', '')
        if not db_path or not os.path.exists(db_path):
            messagebox.showerror('Error', 'No se encontró la base de datos activa.')
            return

        ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre   = emp.get('rfc', 'backup')
        destino  = os.path.join(carpeta, f'{nombre}_respaldo_{ts}.db')

        try:
            shutil.copy2(db_path, destino)
            self._lbl_ultimo_respaldo.config(
                text=f'Último respaldo: {destino}', fg=self.C['success'])
            messagebox.showinfo('Respaldo completado',
                                f'Respaldo guardado en:\n{destino}')
        except Exception as e:
            messagebox.showerror('Error al respaldar', str(e))

    # ──────────────────────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: USUARIOS
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_usuarios(self):
        C  = self.C
        fr = self._tab_usuarios

        tk.Label(fr, text='Gestión de usuarios',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(16, 2))
        tk.Label(fr, text='Solo el Administrador puede crear o modificar usuarios.',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(anchor='w', padx=20, pady=(0, 10))

        # ── Tabla de usuarios ────────────────────────────────────────────────
        tabla_fr = tk.Frame(fr, bg=C['form_bg'])
        tabla_fr.pack(fill='both', expand=True, padx=20)

        self._tree_usr = ttk.Treeview(tabla_fr,
            columns=('id', 'username', 'nombre', 'rol', 'activo', 'ultimo_acceso'),
            show='headings', height=10)

        for col, ancho, txt in [
            ('id',            40,  'ID'),
            ('username',     120,  'Usuario'),
            ('nombre',       180,  'Nombre'),
            ('rol',          130,  'Rol'),
            ('activo',        70,  'Activo'),
            ('ultimo_acceso',160,  'Último acceso'),
        ]:
            self._tree_usr.heading(col, text=txt)
            self._tree_usr.column(col, width=ancho,
                                  anchor='center' if col in ('id','activo') else 'w')

        sb = ttk.Scrollbar(tabla_fr, orient='vertical',
                           command=self._tree_usr.yview)
        self._tree_usr.configure(yscrollcommand=sb.set)
        self._tree_usr.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # ── Botones ──────────────────────────────────────────────────────────
        btn_fr = tk.Frame(fr, bg=C['form_bg'])
        btn_fr.pack(fill='x', padx=20, pady=10)

        acciones = [
            ('➕ Nuevo usuario',        self._nuevo_usuario),
            ('✏️ Editar',               self._editar_usuario),
            ('🔑 Cambiar contraseña',   self._cambiar_password),
            ('✅ Activar / Desactivar', self._toggle_activo),
        ]
        for txt, cmd in acciones:
            tk.Button(btn_fr, text=txt, font=('Arial', 9),
                      bg=C['toolbar_bg'], fg=C['text_dark'],
                      cursor='hand2', bd=0, padx=12, pady=6, relief='flat',
                      command=cmd).pack(side='left', padx=4)

        self._cargar_usuarios()

    def _cargar_usuarios(self):
        for row in self._tree_usr.get_children():
            self._tree_usr.delete(row)
        try:
            self._ucursor.execute(
                'SELECT id, username, nombre, rol, activo, ultimo_acceso FROM usuarios ORDER BY id'
            )
            for row in self._ucursor.fetchall():
                uid, uname, nombre, rol, activo, acceso = row
                self._tree_usr.insert('', 'end', values=(
                    uid, uname, nombre, rol,
                    '✅' if activo else '🚫',
                    acceso or '—'
                ))
        except Exception:
            pass

    def _sel_usuario(self):
        """Devuelve (item_id, valores) del usuario seleccionado, o (None, None)."""
        sel = self._tree_usr.selection()
        if not sel:
            messagebox.showwarning('Selección', 'Selecciona un usuario.')
            return None, None
        vals = self._tree_usr.item(sel[0])['values']
        return sel[0], vals

    def _solo_admin(self) -> bool:
        if sesion.USUARIO_ACTUAL.get('rol') != 'Administrador':
            messagebox.showwarning('Permiso denegado',
                                   'Solo el Administrador puede gestionar usuarios.')
            return False
        return True

    def _nuevo_usuario(self):
        if not self._solo_admin():
            return
        _VentanaUsuario(self.root, self.C, self._uconn,
                        self._ucursor, callback=self._cargar_usuarios)

    def _editar_usuario(self):
        if not self._solo_admin():
            return
        _, vals = self._sel_usuario()
        if vals is None:
            return
        _VentanaUsuario(self.root, self.C, self._uconn,
                        self._ucursor, usuario_id=vals[0],
                        callback=self._cargar_usuarios)

    def _cambiar_password(self):
        uid_sesion = sesion.USUARIO_ACTUAL.get('id')
        _, vals = self._sel_usuario()
        if vals is None:
            return
        uid_sel = vals[0]
        # Solo admin puede cambiar la de otros; cualquiera puede cambiar la suya
        if uid_sesion != uid_sel and sesion.USUARIO_ACTUAL.get('rol') != 'Administrador':
            messagebox.showwarning('Permiso denegado',
                                   'Solo puedes cambiar tu propia contraseña.')
            return
        _DialogoCambiarPassword(self.root, self.C, self._uconn,
                                self._ucursor, uid_sel, vals[1])

    def _toggle_activo(self):
        if not self._solo_admin():
            return
        _, vals = self._sel_usuario()
        if vals is None:
            return
        uid, uname, _, _, estado_icon, _ = vals
        activo_actual = (estado_icon == '✅')
        nueva_accion  = 'desactivar' if activo_actual else 'activar'
        if not messagebox.askyesno('Confirmar',
                                   f'¿{nueva_accion.capitalize()} al usuario "{uname}"?'):
            return
        self._ucursor.execute(
            'UPDATE usuarios SET activo = ? WHERE id = ?',
            (0 if activo_actual else 1, uid)
        )
        self._uconn.commit()
        self._cargar_usuarios()

    # ══════════════════════════════════════════════════════════════════════════
    # PESTAÑA: MIS RUTAS PDF
    # ══════════════════════════════════════════════════════════════════════════
    def _build_tab_mis_rutas(self):
        C  = self.C
        fr = self._tab_mis_rutas

        tk.Label(fr, text='Rutas de destino para PDFs generados',
                 font=('Arial', 10, 'bold'), bg=C['form_bg'],
                 fg=C['text_dark']).pack(anchor='w', padx=20, pady=(16, 2))
        tk.Label(fr,
                 text='Estas rutas son personales — cada usuario guarda sus PDFs donde prefiera.',
                 font=('Arial', 8), bg=C['form_bg'],
                 fg=C['text_muted']).pack(anchor='w', padx=20, pady=(0, 14))

        prefs_u = app_config.cargar_prefs_usuario(sesion.USUARIO_ACTUAL.get('id'))

        self._ruta_cot_var = tk.StringVar(value=prefs_u.get('ruta_cotizaciones', ''))
        self._ruta_rem_var = tk.StringVar(value=prefs_u.get('ruta_remisiones', ''))

        campos = [
            ('Cotizaciones PDF:',      self._ruta_cot_var, self._explorar_ruta_cot),
            ('Notas de Remisión PDF:', self._ruta_rem_var, self._explorar_ruta_rem),
        ]

        for label_txt, var, cmd_explorar in campos:
            row = tk.Frame(fr, bg=C['form_bg'])
            row.pack(fill='x', padx=20, pady=5)
            tk.Label(row, text=label_txt, font=('Arial', 9),
                     bg=C['form_bg'], fg=C['text_secondary'],
                     width=22, anchor='e').pack(side='left')
            tk.Entry(row, textvariable=var, font=('Arial', 10),
                     width=44, relief='solid', bd=1).pack(side='left', padx=6)
            tk.Button(row, text='📂', font=('Arial', 10),
                      bg=C['toolbar_bg'], fg=C['text_dark'], cursor='hand2',
                      bd=0, padx=6, relief='flat',
                      command=cmd_explorar).pack(side='left')

        tk.Button(fr, text='💾  Guardar mis rutas',
                  font=('Arial', 9), bg=C['toolbar_bg'], fg=C['text_dark'],
                  cursor='hand2', bd=0, padx=14, pady=6, relief='flat',
                  command=self._guardar_mis_rutas).pack(anchor='w', padx=20, pady=(10, 0))

    def _explorar_ruta_cot(self):
        carpeta = filedialog.askdirectory(title='Carpeta para Cotizaciones PDF')
        if carpeta:
            self._ruta_cot_var.set(carpeta)

    def _explorar_ruta_rem(self):
        carpeta = filedialog.askdirectory(title='Carpeta para Notas de Remisión PDF')
        if carpeta:
            self._ruta_rem_var.set(carpeta)

    def _guardar_mis_rutas(self):
        usuario_id = sesion.USUARIO_ACTUAL.get('id')
        if not usuario_id:
            messagebox.showwarning('Sin sesión', 'No hay usuario activo.')
            return
        app_config.guardar_prefs_usuario(usuario_id, {
            'ruta_cotizaciones': self._ruta_cot_var.get().strip(),
            'ruta_remisiones':   self._ruta_rem_var.get().strip(),
        })
        messagebox.showinfo('Guardado', 'Tus rutas PDF han sido guardadas.')

    # ──────────────────────────────────────────────────────────────────────────
    def recargar(self):
        """Recarga los valores actuales al mostrar la sección."""
        prefs = app_config.cargar_preferencias(self._empresa_id)
        # PDF
        for key, var in self._pdf_vars.items():
            var.set(app_config.PDF_CONFIG.get(key, ''))
        # IVA
        self._iva_var.set(str(app_config.IVA_DEFAULT[0]))
        # Utilidades
        self._recargar_tree_util()
        # Empresa
        emp = self.sistema.empresa or {}
        for key, var in self._emp_vars.items():
            var.set(emp.get(key, ''))
        # Respaldo
        self._respaldo_carpeta.set(prefs.get('respaldo', {}).get('carpeta', ''))
        # Mis rutas PDF
        prefs_u = app_config.cargar_prefs_usuario(sesion.USUARIO_ACTUAL.get('id'))
        self._ruta_cot_var.set(prefs_u.get('ruta_cotizaciones', ''))
        self._ruta_rem_var.set(prefs_u.get('ruta_remisiones', ''))
        # Usuarios
        self._cargar_usuarios()


# ──────────────────────────────────────────────────────────────────────────────
class _VentanaUsuario:
    """Ventana para crear o editar un usuario."""

    ROLES = ('Administrador', 'Operador', 'Solo lectura')

    def __init__(self, parent, C, conn, cursor, usuario_id=None, callback=None):
        self._conn     = conn
        self._cursor   = cursor
        self._uid      = usuario_id
        self._callback = callback
        self._C        = C

        win = tk.Toplevel(parent)
        win.title('Nuevo usuario' if not usuario_id else 'Editar usuario')
        win.resizable(False, False)
        win.grab_set()
        self._win = win

        form = tk.Frame(win, bg=C['form_bg'], padx=24, pady=20)
        form.pack()

        campos = [('Nombre completo', 'nombre'), ('Usuario (login)', 'username')]
        self._vars = {}
        for i, (lbl, key) in enumerate(campos):
            tk.Label(form, text=lbl, font=('Arial', 9), bg=C['form_bg'],
                     fg=C['text_secondary'], width=18, anchor='e').grid(
                row=i, column=0, padx=(0, 8), pady=6, sticky='e')
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, font=('Arial', 10),
                     width=26, relief='solid', bd=1).grid(
                row=i, column=1, pady=6, sticky='w')
            self._vars[key] = var

        # Contraseña (solo en creación)
        if not usuario_id:
            for i, (lbl, key) in enumerate(
                [('Contraseña', 'pass1'), ('Repetir contraseña', 'pass2')], start=2
            ):
                tk.Label(form, text=lbl, font=('Arial', 9), bg=C['form_bg'],
                         fg=C['text_secondary'], width=18, anchor='e').grid(
                    row=i, column=0, padx=(0, 8), pady=6, sticky='e')
                var = tk.StringVar()
                tk.Entry(form, textvariable=var, font=('Arial', 10),
                         show='•', width=26, relief='solid', bd=1).grid(
                    row=i, column=1, pady=6, sticky='w')
                self._vars[key] = var
            rol_row = 4
        else:
            rol_row = 2

        # Rol
        tk.Label(form, text='Rol', font=('Arial', 9), bg=C['form_bg'],
                 fg=C['text_secondary'], width=18, anchor='e').grid(
            row=rol_row, column=0, padx=(0, 8), pady=6, sticky='e')
        self._rol_var = tk.StringVar(value='Operador')
        ttk.Combobox(form, textvariable=self._rol_var,
                     values=self.ROLES, state='readonly', width=24).grid(
            row=rol_row, column=1, pady=6, sticky='w')

        # Cargar datos si edición
        if usuario_id:
            cursor.execute(
                'SELECT username, nombre, rol FROM usuarios WHERE id = ?', (usuario_id,)
            )
            row = cursor.fetchone()
            if row:
                self._vars['username'].set(row[0])
                self._vars['nombre'].set(row[1])
                self._rol_var.set(row[2])

        # Botones
        btn_fr = tk.Frame(win, bg=C['form_bg'], pady=8)
        btn_fr.pack()
        tk.Button(btn_fr, text='Guardar',
                  font=('Arial', 10, 'bold'),
                  bg=C['accent'], fg='white', cursor='hand2',
                  bd=0, padx=16, pady=6, command=self._guardar).pack(side='left', padx=6)
        tk.Button(btn_fr, text='Cancelar',
                  font=('Arial', 9), bg='#6b7280', fg='white',
                  cursor='hand2', bd=0, padx=16, pady=6,
                  command=win.destroy).pack(side='left', padx=6)

        # Centrar
        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()  - win.winfo_width())  // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f'+{max(0,x)}+{max(0,y)}')

    def _guardar(self):
        nombre   = self._vars['nombre'].get().strip()
        username = self._vars['username'].get().strip()
        rol      = self._rol_var.get()

        if not nombre or not username:
            messagebox.showwarning('Campo requerido', 'Nombre y usuario son obligatorios.',
                                   parent=self._win)
            return

        if self._uid is None:
            # Crear nuevo
            p1 = self._vars.get('pass1', tk.StringVar()).get()
            p2 = self._vars.get('pass2', tk.StringVar()).get()
            if not p1:
                messagebox.showwarning('Contraseña', 'Ingresa una contraseña.',
                                       parent=self._win)
                return
            if p1 != p2:
                messagebox.showwarning('Contraseña', 'Las contraseñas no coinciden.',
                                       parent=self._win)
                return
            try:
                self._cursor.execute(
                    'INSERT INTO usuarios (username, nombre, password_hash, rol) VALUES (?,?,?,?)',
                    (username, nombre, hash_nuevo(p1), rol)
                )
                self._conn.commit()
            except Exception as e:
                messagebox.showerror('Error', f'No se pudo crear el usuario:\n{e}',
                                     parent=self._win)
                return
        else:
            # Editar
            try:
                self._cursor.execute(
                    'UPDATE usuarios SET username=?, nombre=?, rol=? WHERE id=?',
                    (username, nombre, rol, self._uid)
                )
                self._conn.commit()
            except Exception as e:
                messagebox.showerror('Error', f'No se pudo actualizar:\n{e}',
                                     parent=self._win)
                return

        if self._callback:
            self._callback()
        self._win.destroy()


# ──────────────────────────────────────────────────────────────────────────────
class _DialogoCambiarPassword:
    """Diálogo para cambiar la contraseña de un usuario."""

    def __init__(self, parent, C, conn, cursor, usuario_id, username):
        win = tk.Toplevel(parent)
        win.title(f'Cambiar contraseña — {username}')
        win.resizable(False, False)
        win.grab_set()

        form = tk.Frame(win, bg=C['form_bg'], padx=24, pady=20)
        form.pack()

        campos = [('Nueva contraseña', 'p1'), ('Repetir contraseña', 'p2')]
        vars_ = {}
        for i, (lbl, key) in enumerate(campos):
            tk.Label(form, text=lbl, font=('Arial', 9), bg=C['form_bg'],
                     fg=C['text_secondary'], width=20, anchor='e').grid(
                row=i, column=0, padx=(0, 8), pady=6, sticky='e')
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, font=('Arial', 10),
                     show='•', width=24, relief='solid', bd=1).grid(
                row=i, column=1, pady=6)
            vars_[key] = var

        lbl_err = tk.Label(win, text='', font=('Arial', 8),
                           bg=C['form_bg'], fg='#dc2626')
        lbl_err.pack()

        def _guardar():
            p1, p2 = vars_['p1'].get(), vars_['p2'].get()
            if not p1:
                lbl_err.config(text='La contraseña no puede estar vacía.')
                return
            if p1 != p2:
                lbl_err.config(text='Las contraseñas no coinciden.')
                return
            cursor.execute(
                'UPDATE usuarios SET password_hash = ? WHERE id = ?',
                (hash_nuevo(p1), usuario_id)
            )
            conn.commit()
            messagebox.showinfo('Listo', 'Contraseña actualizada.', parent=win)
            win.destroy()

        btn_fr = tk.Frame(win, bg=C['form_bg'], pady=8)
        btn_fr.pack()
        tk.Button(btn_fr, text='Guardar', font=('Arial', 10, 'bold'),
                  bg=C['accent'], fg='white', cursor='hand2',
                  bd=0, padx=16, pady=6, command=_guardar).pack(side='left', padx=6)
        tk.Button(btn_fr, text='Cancelar', font=('Arial', 9),
                  bg='#6b7280', fg='white', cursor='hand2',
                  bd=0, padx=16, pady=6, command=win.destroy).pack(side='left', padx=6)

        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()  - win.winfo_width())  // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f'+{max(0,x)}+{max(0,y)}')


# ──────────────────────────────────────────────────────────────────────────────
class _DialogoCampo:
    """Diálogo simple para ingresar uno o varios campos de texto."""

    def __init__(self, parent, titulo, campos):
        """
        campos: lista de (label, valor_inicial)
        self.resultado: lista con los valores ingresados, o None si canceló.
        """
        self.resultado = None
        win = tk.Toplevel(parent)
        win.title(titulo)
        win.resizable(False, False)
        win.grab_set()

        vars_ = []
        for i, (label, valor) in enumerate(campos):
            tk.Label(win, text=label, font=('Arial', 9)).grid(
                row=i, column=0, padx=12, pady=8, sticky='e')
            var = tk.StringVar(value=str(valor))
            tk.Entry(win, textvariable=var, font=('Arial', 10),
                     width=24, relief='solid', bd=1).grid(
                row=i, column=1, padx=12, pady=8, sticky='w')
            vars_.append(var)

        def _ok():
            self.resultado = [v.get() for v in vars_]
            win.destroy()

        btn_fr = tk.Frame(win)
        btn_fr.grid(row=len(campos), column=0, columnspan=2, pady=10)
        tk.Button(btn_fr, text='Aceptar', command=_ok,
                  bg='#0f7b5e', fg='white', font=('Arial', 9, 'bold'),
                  bd=0, padx=14, pady=5, cursor='hand2').pack(side='left', padx=6)
        tk.Button(btn_fr, text='Cancelar', command=win.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  bd=0, padx=14, pady=5, cursor='hand2').pack(side='left', padx=6)

        # Centrar
        win.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()  - win.winfo_width())  // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win.winfo_height()) // 2
        win.geometry(f'+{max(0,x)}+{max(0,y)}')
        win.wait_window()
