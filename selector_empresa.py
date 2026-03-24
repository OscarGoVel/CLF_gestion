#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Selector de Empresa — CLF Sistema de Gestión
Se muestra al arrancar. Permite elegir con qué empresa trabajar,
agregar una existente o crear una nueva.
La selección se persiste en config.json.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sqlite3
from db_init import inicializar_bd
from datetime import datetime


CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


# ── Gestión de config.json ────────────────────────────────────────────────────

def _config_default():
    """Config inicial con CLF Yucateca pre-registrada."""    # Intentar detectar la BD original en la misma carpeta que main.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_default = os.path.join(base_dir, 'gestion_comercial.db')
    return {
        'empresas': [
            {
                'id':           'emp_CLF240418U94_default',
                'nombre':       'Comercializadora, Logística y Fuerza Yucateca',
                'rfc':          'CLF240418U94',
                'razon_social': 'Comercializadora, Logística y Fuerza Yucateca S.A. de C.V.',
                'email':        'clfyucateca@gmail.com',
                'telefono':     '9993633880',
                'direccion':    'Calle 17 No. 56 Depto. 74, Kanasín, Yucatán',
                'db_path':      db_default,
                'fecha_registro': '2024-01-01',
            }
        ],
        'ultima_empresa': 'emp_CLF240418U94_default',
    }


def cargar_config():
    """Lee config.json. Si no existe crea uno con CLF Yucateca pre-registrada."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    config = _config_default()
    guardar_config(config)
    return config


def guardar_config(config):
    """Escribe config.json."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def empresa_por_id(config, emp_id):
    for e in config['empresas']:
        if e['id'] == emp_id:
            return e
    return None


# ── Selector principal ────────────────────────────────────────────────────────

class SelectorEmpresa:
    """
    Ventana modal de selección de empresa.
    Resultado en self.empresa_seleccionada (dict) o None si se canceló.
    """

    C = {
        'bg':        '#1e2d45',
        'card':      '#263d5e',
        'card_hover':'#2e4a70',
        'accent':    '#0f7b5e',
        'accent2':   '#1a4b8c',
        'warn':      '#92400e',
        'text':      '#e2e8f0',
        'text_muted':'#94a3b8',
        'border':    '#2d4a6e',
        'white':     'white',
    }

    def __init__(self, root):
        self.root   = root
        self.empresa_seleccionada = None
        self.config = cargar_config()

        self._build()
        self._cargar_lista()

        # Si hay última empresa usada, pre-seleccionarla
        if self.config.get('ultima_empresa'):
            self._preseleccionar(self.config['ultima_empresa'])

    # ── Construcción de UI ────────────────────────────────────────────────────

    def _build(self):
        self.root.title('CLF — Seleccionar Empresa')
        self.root.geometry('620x520')
        self.root.configure(bg=self.C['bg'])
        self.root.resizable(False, False)
        self.root.protocol('WM_DELETE_WINDOW', self._cancelar)

        # Centrar ventana
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth()  - 620) // 2
        y = (self.root.winfo_screenheight() - 520) // 2
        self.root.geometry(f'620x520+{x}+{y}')

        # ── Cabecera ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=self.C['bg'], pady=24)
        hdr.pack(fill='x')
        tk.Label(hdr, text='⚙  Sistema de Gestión Comercial', font=('Arial', 18, 'bold'),
                 bg=self.C['bg'], fg=self.C['accent']).pack()
        tk.Label(hdr, text='',
                 font=('Arial', 11), bg=self.C['bg'],
                 fg=self.C['text_muted']).pack(pady=(2, 0))
        tk.Label(hdr, text='Selecciona una empresa para continuar',
                 font=('Arial', 9, 'italic'), bg=self.C['bg'],
                 fg=self.C['text_muted']).pack(pady=(4, 0))

        tk.Frame(self.root, bg=self.C['border'], height=1).pack(fill='x')

        # ── Lista de empresas ─────────────────────────────────────────────────
        lista_outer = tk.Frame(self.root, bg=self.C['bg'])
        lista_outer.pack(fill='both', expand=True, padx=24, pady=16)

        # Scrollable canvas
        self._canvas = tk.Canvas(lista_outer, bg=self.C['bg'],
                                  highlightthickness=0)
        sc = ttk.Scrollbar(lista_outer, orient='vertical',
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sc.set)
        self._canvas.pack(side='left', fill='both', expand=True)
        sc.pack(side='right', fill='y')

        self._lista_frame = tk.Frame(self._canvas, bg=self.C['bg'])
        self._wid = self._canvas.create_window(
            (0, 0), window=self._lista_frame, anchor='nw')
        self._lista_frame.bind('<Configure>',
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox('all')))
        self._canvas.bind('<Configure>',
            lambda e: self._canvas.itemconfig(self._wid, width=e.width))

        # ── Botones de acción ─────────────────────────────────────────────────
        tk.Frame(self.root, bg=self.C['border'], height=1).pack(fill='x')
        foot = tk.Frame(self.root, bg='#141e2e', pady=12)
        foot.pack(fill='x')

        tk.Button(
            foot, text='＋  Nueva empresa',
            font=('Arial', 9, 'bold'), bg=self.C['accent'], fg='white',
            cursor='hand2', relief='flat', padx=14, pady=7,
            command=self._nueva_empresa
        ).pack(side='left', padx=16)

        tk.Button(
            foot, text='📂  Agregar existente',
            font=('Arial', 9), bg=self.C['accent2'], fg='white',
            cursor='hand2', relief='flat', padx=14, pady=7,
            command=self._agregar_existente
        ).pack(side='left', padx=4)

        self._btn_entrar = tk.Button(
            foot, text='Entrar  →',
            font=('Arial', 10, 'bold'), bg='#16a34a', fg='white',
            cursor='hand2', relief='flat', padx=18, pady=7,
            state='disabled', command=self._confirmar
        )
        self._btn_entrar.pack(side='right', padx=16)

    # ── Lista de tarjetas de empresa ──────────────────────────────────────────

    def _cargar_lista(self):
        for w in self._lista_frame.winfo_children():
            w.destroy()
        self._cards = {}  # emp_id -> frame

        empresas = self.config.get('empresas', [])
        if not empresas:
            tk.Label(
                self._lista_frame,
                text='No hay empresas registradas.\nAgrega una nueva o vincula una existente.',
                font=('Arial', 10, 'italic'), bg=self.C['bg'],
                fg=self.C['text_muted'], justify='center', pady=40
            ).pack(expand=True)
            return

        for emp in empresas:
            self._crear_card(emp)

    def _crear_card(self, emp):
        emp_id = emp['id']
        existe_db = os.path.exists(emp.get('db_path', ''))

        card = tk.Frame(
            self._lista_frame, bg=self.C['card'],
            highlightbackground=self.C['border'], highlightthickness=1,
            cursor='hand2'
        )
        card.pack(fill='x', pady=4)
        self._cards[emp_id] = card

        # Indicador de estado (punto verde/rojo)
        dot_color = '#16a34a' if existe_db else '#dc2626'
        dot = tk.Label(card, text='●', font=('Arial', 12),
                       bg=self.C['card'], fg=dot_color)
        dot.pack(side='left', padx=(12, 6), pady=12)

        # Info
        info = tk.Frame(card, bg=self.C['card'])
        info.pack(side='left', fill='x', expand=True, pady=8)

        tk.Label(info, text=emp.get('nombre', 'Sin nombre'),
                 font=('Arial', 10, 'bold'), bg=self.C['card'],
                 fg=self.C['text'], anchor='w').pack(anchor='w')
        tk.Label(info,
                 text=f"RFC: {emp.get('rfc', '—')}   ·   {emp.get('db_path', '—')}",
                 font=('Arial', 8), bg=self.C['card'],
                 fg=self.C['text_muted'], anchor='w').pack(anchor='w')

        if not existe_db:
            aviso_f = tk.Frame(info, bg=self.C['card'])
            aviso_f.pack(anchor='w', fill='x')
            tk.Label(aviso_f, text='⚠ Archivo de base de datos no encontrado  ',
                     font=('Arial', 8, 'italic'), bg=self.C['card'],
                     fg='#f87171').pack(side='left')
            tk.Button(aviso_f, text='📂 Vincular BD existente',
                      font=('Arial', 7, 'bold'), bg='#1a4b8c', fg='white',
                      cursor='hand2', relief='flat', padx=6, pady=1,
                      command=lambda eid=emp_id: self._reasignar_bd(eid)
                      ).pack(side='left', padx=(0, 4))
            tk.Button(aviso_f, text='✨ Crear BD nueva',
                      font=('Arial', 7, 'bold'), bg='#0f7b5e', fg='white',
                      cursor='hand2', relief='flat', padx=6, pady=1,
                      command=lambda eid=emp_id: self._crear_bd_nueva(eid)
                      ).pack(side='left')

        # Botón quitar (×)
        tk.Button(
            card, text='×', font=('Arial', 12), bg=self.C['card'],
            fg=self.C['text_muted'], cursor='hand2', relief='flat',
            padx=8, command=lambda eid=emp_id: self._quitar_empresa(eid)
        ).pack(side='right', padx=8)

        # Click en card → seleccionar
        for widget in (card, info, dot):
            widget.bind('<Button-1>', lambda e, eid=emp_id: self._seleccionar(eid))
        for child in info.winfo_children():
            child.bind('<Button-1>', lambda e, eid=emp_id: self._seleccionar(eid))

    def _reasignar_bd(self, emp_id):
        """Permite apuntar la empresa a un archivo .db existente."""
        emp = empresa_por_id(self.config, emp_id)
        if not emp:
            return
        ruta = filedialog.askopenfilename(
            title=f'Selecciona la BD para "{emp["nombre"]}"',
            filetypes=[('SQLite DB', '*.db'), ('Todos', '*.*')],
            parent=self.root
        )
        if not ruta:
            return
        emp['db_path'] = ruta
        guardar_config(self.config)
        self._cargar_lista()
        self._seleccionar(emp_id)

    def _crear_bd_nueva(self, emp_id):
        """Crea un archivo .db nuevo con todas las tablas para la empresa."""
        emp = empresa_por_id(self.config, emp_id)
        if not emp:
            return
        ruta = filedialog.asksaveasfilename(
            title=f'Guardar BD de "{emp["nombre"]}" como...',
            defaultextension='.db',
            initialfile=f'{emp["rfc"].lower()}.db',
            filetypes=[('SQLite DB', '*.db')],
            parent=self.root
        )
        if not ruta:
            return
        try:
            conn, _ = inicializar_bd(ruta)
            conn.close()
            emp['db_path'] = ruta
            guardar_config(self.config)
            self._cargar_lista()
            self._seleccionar(emp_id)
            messagebox.showinfo(
                '✅ BD creada',
                f'Base de datos creada correctamente:\n{ruta}',
                parent=self.root)
        except Exception as e:
            messagebox.showerror('Error', f'No se pudo crear la BD:\n{e}',
                                  parent=self.root)

    def _seleccionar(self, emp_id):
        """Marca visualmente la empresa seleccionada."""
        for eid, card in self._cards.items():
            card.configure(
                bg=self.C['card_hover'] if eid == emp_id else self.C['card'],
                highlightbackground='#0f7b5e' if eid == emp_id else self.C['border']
            )
            for w in card.winfo_children():
                try:
                    w.configure(bg=self.C['card_hover'] if eid == emp_id
                                else self.C['card'])
                except Exception:
                    pass

        self._emp_id_sel = emp_id
        emp = empresa_por_id(self.config, emp_id)
        existe = emp and os.path.exists(emp.get('db_path', ''))
        self._btn_entrar.configure(
            state='normal' if existe else 'disabled',
            bg='#16a34a' if existe else '#6b7280'
        )

    def _preseleccionar(self, emp_id):
        if emp_id in self._cards:
            self._seleccionar(emp_id)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _confirmar(self):
        emp = empresa_por_id(self.config, self._emp_id_sel)
        if not emp:
            return
        if not os.path.exists(emp['db_path']):
            messagebox.showerror('Error',
                f'No se encontró el archivo:\n{emp["db_path"]}',
                parent=self.root)
            return
        # Guardar última empresa usada
        self.config['ultima_empresa'] = emp['id']
        guardar_config(self.config)
        self.empresa_seleccionada = emp
        self.root.destroy()

    def _cancelar(self):
        self.empresa_seleccionada = None
        self.root.destroy()

    def _quitar_empresa(self, emp_id):
        emp = empresa_por_id(self.config, emp_id)
        nombre = emp['nombre'] if emp else '?'
        if not messagebox.askyesno(
            'Quitar empresa',
            f'¿Quitar "{nombre}" de la lista?\n\n'
            'El archivo de base de datos NO se eliminará.',
            parent=self.root
        ):
            return
        self.config['empresas'] = [
            e for e in self.config['empresas'] if e['id'] != emp_id
        ]
        if self.config.get('ultima_empresa') == emp_id:
            self.config['ultima_empresa'] = None
        guardar_config(self.config)
        self._cargar_lista()
        self._btn_entrar.configure(state='disabled')

    def _nueva_empresa(self):
        DialogoEmpresa(self.root, self.config, modo='nueva',
                        on_guardar=self._on_empresa_guardada)

    def _agregar_existente(self):
        ruta = filedialog.askopenfilename(
            title='Selecciona el archivo de base de datos',
            filetypes=[('SQLite DB', '*.db'), ('Todos', '*.*')],
            parent=self.root
        )
        if not ruta:
            return
        # Intentar leer nombre/RFC desde la BD existente
        nombre_sugerido = ''
        rfc_sugerido    = ''
        try:
            conn_tmp = sqlite3.connect(ruta)
            c_tmp    = conn_tmp.cursor()
            c_tmp.execute("SELECT nombre_comercial FROM clientes LIMIT 1")
            row = c_tmp.fetchone()
            conn_tmp.close()
        except Exception:
            pass

        DialogoEmpresa(self.root, self.config, modo='existente',
                        db_path_inicial=ruta,
                        on_guardar=self._on_empresa_guardada)

    def _on_empresa_guardada(self, nueva_emp):
        self._cargar_lista()
        self._seleccionar(nueva_emp['id'])

    # ── helpers ───────────────────────────────────────────────────────────────

    def _emp_id_sel(self):
        return None


# ── Diálogo alta de empresa ───────────────────────────────────────────────────

class DialogoEmpresa:
    """
    Formulario para registrar una empresa nueva o agregar una existente.
    """

    def __init__(self, parent, config, modo='nueva',
                 db_path_inicial='', on_guardar=None):
        self.config     = config
        self.modo       = modo
        self.on_guardar = on_guardar

        self.win = tk.Toplevel(parent)
        self.win.withdraw()
        self.win.title('Nueva empresa' if modo == 'nueva' else 'Agregar empresa existente')
        self.win.geometry('480x380')
        self.win.configure(bg='#1e2d45')
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        # Centrar
        x = parent.winfo_x() + (parent.winfo_width()  - 480) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 380) // 2
        self.win.geometry(f'480x380+{x}+{y}')

        self._build(db_path_inicial)
        self.win.after(0, self.win.deiconify)

    def _build(self, db_path_inicial):
        # Cabecera
        hdr = tk.Frame(self.win, bg='#1a4b8c', pady=10)
        hdr.pack(fill='x')
        titulo = 'Nueva empresa' if self.modo == 'nueva' else 'Agregar empresa existente'
        tk.Label(hdr, text=titulo, font=('Arial', 11, 'bold'),
                 bg='#1a4b8c', fg='white').pack()

        body = tk.Frame(self.win, bg='#1e2d45', padx=28, pady=18)
        body.pack(fill='both', expand=True)
        body.grid_columnconfigure(1, weight=1)

        campos = [
            ('Nombre comercial *', 'nombre'),
            ('RFC *',              'rfc'),
            ('Razón social',       'razon_social'),
            ('Email',              'email'),
            ('Teléfono',           'telefono'),
        ]
        self._entries = {}
        for i, (label, key) in enumerate(campos):
            tk.Label(body, text=label, font=('Arial', 9),
                     bg='#1e2d45', fg='#94a3b8',
                     anchor='w').grid(row=i, column=0, sticky='w',
                                      pady=5, padx=(0, 12))
            e = tk.Entry(body, font=('Arial', 9), bg='#263d5e',
                         fg='white', insertbackground='white',
                         relief='flat', bd=4)
            e.grid(row=i, column=1, sticky='ew', pady=5)
            self._entries[key] = e

        # Ruta de BD
        row_db = len(campos)
        tk.Label(body, text='Archivo de BD *', font=('Arial', 9),
                 bg='#1e2d45', fg='#94a3b8',
                 anchor='w').grid(row=row_db, column=0, sticky='w', pady=5, padx=(0, 12))
        db_f = tk.Frame(body, bg='#1e2d45')
        db_f.grid(row=row_db, column=1, sticky='ew', pady=5)
        db_f.grid_columnconfigure(0, weight=1)

        self._entry_db = tk.Entry(db_f, font=('Arial', 9), bg='#263d5e',
                                   fg='white', insertbackground='white',
                                   relief='flat', bd=4)
        self._entry_db.grid(row=0, column=0, sticky='ew')
        if db_path_inicial:
            self._entry_db.insert(0, db_path_inicial)

        tk.Button(db_f, text='...', font=('Arial', 8), bg='#2d4a6e',
                  fg='white', cursor='hand2', relief='flat', padx=6,
                  command=self._browse_db).grid(row=0, column=1, padx=(4, 0))

        if self.modo == 'nueva':
            tk.Label(body,
                     text='Se creará un archivo .db nuevo en la ruta indicada.',
                     font=('Arial', 7, 'italic'), bg='#1e2d45',
                     fg='#64748b').grid(row=row_db+1, column=1, sticky='w')

        # Footer
        foot = tk.Frame(self.win, bg='#141e2e', pady=10)
        foot.pack(fill='x', side='bottom')
        tk.Button(foot, text='Guardar', font=('Arial', 9, 'bold'),
                  bg='#0f7b5e', fg='white', cursor='hand2',
                  relief='flat', padx=16, pady=6,
                  command=self._guardar).pack(side='right', padx=16)
        tk.Button(foot, text='Cancelar', font=('Arial', 9),
                  bg='#374151', fg='white', cursor='hand2',
                  relief='flat', padx=12, pady=6,
                  command=self.win.destroy).pack(side='right', padx=4)

    def _browse_db(self):
        if self.modo == 'nueva':
            ruta = filedialog.asksaveasfilename(
                title='Guardar base de datos como...',
                defaultextension='.db',
                filetypes=[('SQLite DB', '*.db')],
                parent=self.win
            )
        else:
            ruta = filedialog.askopenfilename(
                title='Selecciona el archivo de base de datos',
                filetypes=[('SQLite DB', '*.db'), ('Todos', '*.*')],
                parent=self.win
            )
        if ruta:
            self._entry_db.delete(0, 'end')
            self._entry_db.insert(0, ruta)

    def _guardar(self):
        nombre = self._entries['nombre'].get().strip()
        rfc    = self._entries['rfc'].get().strip().upper()
        db_path = self._entry_db.get().strip()

        if not nombre:
            messagebox.showwarning('Falta nombre',
                'El nombre comercial es obligatorio.', parent=self.win)
            return
        if not rfc:
            messagebox.showwarning('Falta RFC',
                'El RFC es obligatorio.', parent=self.win)
            return
        if not db_path:
            messagebox.showwarning('Falta ruta',
                'Indica el archivo de base de datos.', parent=self.win)
            return

        # Verificar que no haya duplicado de RFC
        for e in self.config['empresas']:
            if e['rfc'].upper() == rfc:
                messagebox.showwarning('Duplicado',
                    f'Ya existe una empresa con el RFC {rfc}.',
                    parent=self.win)
                return

        # Generar ID único
        emp_id = f"emp_{rfc}_{int(datetime.now().timestamp())}"

        nueva = {
            'id':          emp_id,
            'nombre':      nombre,
            'rfc':         rfc,
            'razon_social': self._entries['razon_social'].get().strip(),
            'email':       self._entries['email'].get().strip(),
            'telefono':    self._entries['telefono'].get().strip(),
            'db_path':     db_path,
            'fecha_registro': datetime.now().strftime('%Y-%m-%d'),
        }

        self.config['empresas'].append(nueva)
        guardar_config(self.config)

        # Si es empresa nueva: crear la BD con todas las tablas
        if self.modo == 'nueva':
            try:
                conn, _ = inicializar_bd(db_path)
                conn.close()
            except Exception as e:
                messagebox.showwarning(
                    'Advertencia',
                    f'Empresa registrada pero hubo un problema al crear la BD:\n{e}',
                    parent=self.win)

        self.win.destroy()
        if self.on_guardar:
            self.on_guardar(nueva)


# ── Función pública ───────────────────────────────────────────────────────────

def mostrar_selector():
    """
    Muestra la ventana de selección de empresa y devuelve
    el dict de la empresa elegida, o None si se cerró sin seleccionar.
    """
    root = tk.Tk()
    sel  = SelectorEmpresa(root)
    root.mainloop()
    return sel.empresa_seleccionada
