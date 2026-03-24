#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/login.py
Pantalla de login del sistema.
Usa una base de datos central (app_usuarios.db) independiente de cada empresa.
Devuelve el dict del usuario autenticado o None si se canceló.
"""

import tkinter as tk
from tkinter import messagebox
import sqlite3
import hashlib
import os
from ui.utils import centrar_ventana
import db_connection

# Ruta de la BD central de usuarios (solo se usa en modo SQLite)
_BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_DB   = os.path.join(_BASE_DIR, 'app_usuarios.db')


# ── Hashing ───────────────────────────────────────────────────────────────────

def hash_nuevo(password: str) -> str:
    """Hash seguro usando PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), b'clf_sistema', 200_000
    ).hex()


def verificar_password(password: str, stored_hash: str) -> bool:
    return hash_nuevo(password) == stored_hash


# ── Inicialización de la BD central ──────────────────────────────────────────

def _abrir_users_db():
    conn, cursor = db_connection.conectar_usuarios()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            username       TEXT UNIQUE NOT NULL,
            nombre         TEXT NOT NULL,
            password_hash  TEXT NOT NULL,
            rol            TEXT NOT NULL DEFAULT 'Operador',
            activo         INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_acceso  TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferencias_usuario (
            usuario_id  INTEGER NOT NULL,
            clave       TEXT    NOT NULL,
            valor       TEXT    NOT NULL DEFAULT '',
            PRIMARY KEY (usuario_id, clave)
        )
    ''')
    conn.commit()
    return conn, cursor


def _crear_admin_inicial(cursor, conn) -> bool:
    """Crea el usuario admin por defecto si la tabla está vacía. Retorna True si lo creó."""
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            'INSERT INTO usuarios (username, nombre, password_hash, rol) VALUES (?,?,?,?)',
            ('admin', 'Administrador', hash_nuevo('admin123'), 'Administrador')
        )
        conn.commit()
        return True
    return False


# ── Pantalla de login ─────────────────────────────────────────────────────────

def mostrar_login(parent: tk.Misc | None = None) -> dict | None:
    """
    Muestra la ventana de login.
    - Si parent=None  → crea su propio tk.Tk() (uso desde __main__).
    - Si parent!=None → usa tk.Toplevel(parent) (uso desde dentro de la app).
    Devuelve dict del usuario o None si canceló.
    """
    conn, cursor = _abrir_users_db()
    primer_uso   = _crear_admin_inicial(cursor, conn)
    resultado    = {'usuario': None}

    # ── Crear ventana ──────────────────────────────────────────────────────
    if parent is None:
        owner = tk.Tk()
        owner.withdraw()
        win   = tk.Toplevel(owner)
        es_standalone = True
    else:
        owner = parent
        win   = tk.Toplevel(owner)
        es_standalone = False

    win.title('Iniciar sesión — CLF Gestión')
    win.resizable(False, False)
    win.protocol('WM_DELETE_WINDOW', lambda: _cancelar())

    C = {
        'bg':     '#1e2d45',
        'card':   '#ffffff',
        'accent': '#0f7b5e',
        'danger': '#dc2626',
        'text':   '#1e2d45',
        'muted':  '#6b7e99',
    }

    win.configure(bg=C['bg'])

    # ── Card ──────────────────────────────────────────────────────────────
    card = tk.Frame(win, bg=C['card'], padx=36, pady=28)
    card.pack(padx=40, pady=36)

    tk.Label(card, text='⚙', font=('Arial', 26), bg=C['card'],
             fg=C['accent']).pack()
    tk.Label(card, text='GESTIÓN CLF',
             font=('Arial', 14, 'bold'), bg=C['card'], fg=C['text']).pack(pady=(2, 0))
    tk.Label(card, text='Sistema de Gestión Comercial',
             font=('Arial', 9), bg=C['card'], fg=C['muted']).pack(pady=(0, 18))

    # Aviso primer uso
    if primer_uso:
        aviso = tk.Frame(card, bg='#fef3c7', bd=1, relief='solid', padx=10, pady=6)
        aviso.pack(fill='x', pady=(0, 12))
        tk.Label(aviso,
                 text='⚠  Primera vez: usuario admin / contraseña admin123\n'
                      'Cámbiala en Configuración → Usuarios.',
                 font=('Arial', 8), bg='#fef3c7', fg='#92400e',
                 justify='left').pack(anchor='w')

    # Usuario
    tk.Label(card, text='Usuario', font=('Arial', 9, 'bold'),
             bg=C['card'], fg=C['text'], anchor='w').pack(fill='x')
    entry_user = tk.Entry(card, font=('Arial', 11), relief='solid', bd=1, width=28)
    entry_user.pack(pady=(2, 10), ipady=4)

    # Contraseña
    tk.Label(card, text='Contraseña', font=('Arial', 9, 'bold'),
             bg=C['card'], fg=C['text'], anchor='w').pack(fill='x')
    entry_pass = tk.Entry(card, font=('Arial', 11), show='•',
                          relief='solid', bd=1, width=28)
    entry_pass.pack(pady=(2, 4), ipady=4)

    lbl_error = tk.Label(card, text='', font=('Arial', 8),
                         bg=C['card'], fg=C['danger'])
    lbl_error.pack(pady=(0, 10))

    # ── Lógica de login ───────────────────────────────────────────────────
    def _ingresar(event=None):
        username = entry_user.get().strip()
        password = entry_pass.get()

        if not username or not password:
            lbl_error.config(text='Ingresa usuario y contraseña.')
            return

        cursor.execute(
            'SELECT id, nombre, password_hash, rol, activo FROM usuarios WHERE username = ?',
            (username,)
        )
        row = cursor.fetchone()

        if not row:
            lbl_error.config(text='Usuario no encontrado.')
            entry_pass.delete(0, 'end')
            return

        uid, nombre, phash, rol, activo = row

        if not activo:
            lbl_error.config(text='Usuario desactivado. Contacta al administrador.')
            return

        if not verificar_password(password, phash):
            lbl_error.config(text='Contraseña incorrecta.')
            entry_pass.delete(0, 'end')
            return

        cursor.execute(
            'UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = ?', (uid,)
        )
        conn.commit()
        conn.close()

        resultado['usuario'] = {
            'id':       uid,
            'username': username,
            'nombre':   nombre,
            'rol':      rol,
        }
        win.destroy()
        if es_standalone:
            owner.destroy()

    def _cancelar():
        conn.close()
        win.destroy()
        if es_standalone:
            owner.destroy()

    # ── Botón ──────────────────────────────────────────────────────────────
    tk.Button(card, text='Ingresar',
              font=('Arial', 11, 'bold'),
              bg=C['accent'], fg='white',
              activebackground='#065f46', activeforeground='white',
              bd=0, relief='flat', cursor='hand2',
              padx=0, pady=8, width=26,
              command=_ingresar).pack()

    win.bind('<Return>', _ingresar)
    entry_user.focus()
    centrar_ventana(win, ancho=340, alto=None)

    win.grab_set()

    if es_standalone:
        owner.mainloop()
    else:
        win.wait_window()

    return resultado['usuario']
