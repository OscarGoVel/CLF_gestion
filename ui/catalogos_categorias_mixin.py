# -*- coding: utf-8 -*-
"""
ui/catalogos_categorias_mixin.py
Mixin: gestión de categorías y subcategorías.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3

from ui.utils import centrar_ventana as _centrar


class _CatalogosCategoriassMixin:
    def gestionar_categorias(self):
        """Ventana para gestionar categorías y subcategorías"""
        ventana = tk.Toplevel(self.root)
        ventana.title("Gestión de Categorías")
        ventana.geometry("700x500")
        ventana.minsize(620, 420)
        ventana.resizable(True, True)
        _centrar(ventana, self.root)
        
        # Frame principal
        frame_principal = tk.Frame(ventana, padx=20, pady=20)
        frame_principal.pack(fill='both', expand=True)
        
        # === CATEGORÍAS ===
        frame_cat = tk.LabelFrame(frame_principal, text="Categorías", font=('Arial', 10, 'bold'))
        frame_cat.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Lista de categorías
        self.listbox_categorias = tk.Listbox(frame_cat, font=('Arial', 10))
        self.listbox_categorias.pack(fill='both', expand=True, padx=10, pady=10)
        self.listbox_categorias.bind('<<ListboxSelect>>', self.cargar_subcategorias_de_categoria)
        
        # Botones categorías
        frame_btn_cat = tk.Frame(frame_cat)
        frame_btn_cat.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_btn_cat,
            text="➕ Nueva",
            command=lambda: self.nueva_categoria(ventana),
            bg='#27ae60',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        tk.Button(
            frame_btn_cat,
            text="✏️ Editar",
            command=lambda: self.editar_categoria(ventana),
            bg='#f39c12',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            frame_btn_cat,
            text="🗑️ Eliminar",
            command=lambda: self.eliminar_categoria(ventana),
            bg='#e74c3c',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        # === SUBCATEGORÍAS ===
        frame_subcat = tk.LabelFrame(frame_principal, text="Subcategorías", font=('Arial', 10, 'bold'))
        frame_subcat.pack(side='right', fill='both', expand=True)
        
        # Lista de subcategorías
        self.listbox_subcategorias = tk.Listbox(frame_subcat, font=('Arial', 10))
        self.listbox_subcategorias.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Botones subcategorías
        frame_btn_subcat = tk.Frame(frame_subcat)
        frame_btn_subcat.pack(fill='x', padx=10, pady=5)
        
        tk.Button(
            frame_btn_subcat,
            text="➕ Nueva",
            command=lambda: self.nueva_subcategoria(ventana),
            bg='#27ae60',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        tk.Button(
            frame_btn_subcat,
            text="✏️ Editar",
            command=lambda: self.editar_subcategoria(ventana),
            bg='#f39c12',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)

        tk.Button(
            frame_btn_subcat,
            text="🗑️ Eliminar",
            command=lambda: self.eliminar_subcategoria(ventana),
            bg='#e74c3c',
            fg='white',
            font=('Arial', 9, 'bold'),
            cursor='hand2'
        ).pack(side='left', padx=2)
        
        # Cargar categorías
        self.cargar_lista_categorias()
        
        ventana.transient(self.root)
        ventana.grab_set()
        ventana.bind('<Escape>', lambda e: ventana.destroy())
    
    def cargar_lista_categorias(self):
        """Carga las categorías en el listbox"""
        self.listbox_categorias.delete(0, tk.END)
        self.cursor.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
        self.categorias_dict = {}
        for cat_id, nombre in self.cursor.fetchall():
            self.listbox_categorias.insert(tk.END, nombre)
            self.categorias_dict[nombre] = cat_id
    
    def cargar_subcategorias_de_categoria(self, event=None):
        """Carga las subcategorías de la categoría seleccionada"""
        self.listbox_subcategorias.delete(0, tk.END)
        
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            return
        
        categoria_nombre = self.listbox_categorias.get(seleccion[0])
        categoria_id = self.categorias_dict.get(categoria_nombre)
        
        if categoria_id:
            self.cursor.execute(
                "SELECT id, nombre FROM subcategorias WHERE categoria_id = ? ORDER BY nombre",
                (categoria_id,)
            )
            self.subcategorias_dict = {}
            for sub_id, nombre in self.cursor.fetchall():
                self.listbox_subcategorias.insert(tk.END, nombre)
                self.subcategorias_dict[nombre] = sub_id
    
    def nueva_categoria(self, ventana_padre):
        """Crea una nueva categoría"""
        nombre = tk.simpledialog.askstring("Nueva Categoría", "Nombre de la categoría:", parent=ventana_padre)
        if nombre:
            nombre = nombre.strip()
            if nombre:
                try:
                    self.cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
                    self.conn.commit()
                    self.cargar_lista_categorias()
                    messagebox.showinfo("Éxito", "Categoría creada correctamente", parent=ventana_padre)
                except sqlite3.IntegrityError:
                    messagebox.showerror("Error", "Ya existe una categoría con ese nombre", parent=ventana_padre)
    
    def editar_categoria(self, ventana_padre):
        """Renombra la categoría seleccionada"""
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una categoría para editar",
                                   parent=ventana_padre)
            return

        nombre_actual = self.listbox_categorias.get(seleccion[0])
        cat_id = self.categorias_dict.get(nombre_actual)

        # Mini-formulario
        dlg = tk.Toplevel(ventana_padre)
        dlg.title("Editar Categoría")
        dlg.geometry("400x160")
        dlg.minsize(340, 200)
        dlg.resizable(True, True)
        _centrar(dlg, self.root)
        dlg.resizable(False, False)
        dlg.transient(ventana_padre)
        dlg.grab_set()
        dlg.configure(bg='#f8fafc')

        tk.Label(dlg, text="Nuevo nombre:", font=('Arial', 10, 'bold'),
                 bg='#f8fafc').pack(pady=(16, 4))
        entry = tk.Entry(dlg, width=36, font=('Arial', 10))
        entry.insert(0, nombre_actual)
        entry.pack(padx=16)
        entry.select_range(0, 'end')
        entry.focus_set()

        def guardar(event=None):
            nuevo = entry.get().strip()
            if not nuevo:
                messagebox.showwarning("Advertencia", "El nombre no puede estar vacío",
                                       parent=dlg)
                return
            if nuevo == nombre_actual:
                dlg.destroy()
                return
            try:
                self.cursor.execute("UPDATE categorias SET nombre=? WHERE id=?",
                                    (nuevo, cat_id))
                self.conn.commit()
                self.cargar_lista_categorias()
                dlg.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Ya existe una categoría con ese nombre",
                                     parent=dlg)
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        entry.bind('<Return>', guardar)
        fb = tk.Frame(dlg, bg='#f8fafc')
        fb.pack(pady=10)
        tk.Button(fb, text="💾 Guardar", command=guardar,
                  bg='#f39c12', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=4).pack(side='left', padx=5)
        tk.Button(fb, text="Cancelar", command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=10, pady=4).pack(side='left')

    def editar_subcategoria(self, ventana_padre):
        """Renombra la subcategoría seleccionada"""
        seleccion = self.listbox_subcategorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una subcategoría para editar",
                                   parent=ventana_padre)
            return

        nombre_actual = self.listbox_subcategorias.get(seleccion[0])
        sub_id = self.subcategorias_dict.get(nombre_actual)

        dlg = tk.Toplevel(ventana_padre)
        dlg.title("Editar Subcategoría")
        dlg.geometry("400x160")
        dlg.minsize(340, 200)
        dlg.resizable(True, True)
        _centrar(dlg, self.root)
        dlg.resizable(False, False)
        dlg.transient(ventana_padre)
        dlg.grab_set()
        dlg.configure(bg='#f8fafc')

        tk.Label(dlg, text="Nuevo nombre:", font=('Arial', 10, 'bold'),
                 bg='#f8fafc').pack(pady=(16, 4))
        entry = tk.Entry(dlg, width=36, font=('Arial', 10))
        entry.insert(0, nombre_actual)
        entry.pack(padx=16)
        entry.select_range(0, 'end')
        entry.focus_set()

        def guardar(event=None):
            nuevo = entry.get().strip()
            if not nuevo:
                messagebox.showwarning("Advertencia", "El nombre no puede estar vacío",
                                       parent=dlg)
                return
            if nuevo == nombre_actual:
                dlg.destroy()
                return
            try:
                self.cursor.execute("UPDATE subcategorias SET nombre=? WHERE id=?",
                                    (nuevo, sub_id))
                self.conn.commit()
                self.cargar_subcategorias_de_categoria()
                dlg.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Ya existe una subcategoría con ese nombre",
                                     parent=dlg)
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        entry.bind('<Return>', guardar)
        fb = tk.Frame(dlg, bg='#f8fafc')
        fb.pack(pady=10)
        tk.Button(fb, text="💾 Guardar", command=guardar,
                  bg='#f39c12', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=4).pack(side='left', padx=5)
        tk.Button(fb, text="Cancelar", command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=10, pady=4).pack(side='left')

    def eliminar_categoria(self, ventana_padre):
        """Elimina la categoría seleccionada"""
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una categoría para eliminar", parent=ventana_padre)
            return
        
        categoria_nombre = self.listbox_categorias.get(seleccion[0])
        categoria_id = self.categorias_dict.get(categoria_nombre)
        
        respuesta = messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la categoría '{categoria_nombre}'?\n\nSe eliminarán también sus subcategorías.",
            parent=ventana_padre
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM subcategorias WHERE categoria_id = ?", (categoria_id,))
                self.cursor.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
                self.conn.commit()
                self.cargar_lista_categorias()
                self.listbox_subcategorias.delete(0, tk.END)
                messagebox.showinfo("Éxito", "Categoría eliminada correctamente", parent=ventana_padre)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar:\n{str(e)}", parent=ventana_padre)
    
    def nueva_subcategoria(self, ventana_padre):
        """Crea una nueva subcategoría"""
        seleccion = self.listbox_categorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Primero selecciona una categoría", parent=ventana_padre)
            return
        
        categoria_nombre = self.listbox_categorias.get(seleccion[0])
        categoria_id = self.categorias_dict.get(categoria_nombre)
        
        nombre = tk.simpledialog.askstring(
            "Nueva Subcategoría",
            f"Nombre de la subcategoría para '{categoria_nombre}':",
            parent=ventana_padre
        )
        
        if nombre:
            nombre = nombre.strip()
            if nombre:
                try:
                    self.cursor.execute(
                        "INSERT INTO subcategorias (categoria_id, nombre) VALUES (?, ?)",
                        (categoria_id, nombre)
                    )
                    self.conn.commit()
                    self.cargar_subcategorias_de_categoria()
                    messagebox.showinfo("Éxito", "Subcategoría creada correctamente", parent=ventana_padre)
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"No se pudo crear:\n{str(e)}", parent=ventana_padre)
    
    def eliminar_subcategoria(self, ventana_padre):
        """Elimina la subcategoría seleccionada"""
        seleccion = self.listbox_subcategorias.curselection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Selecciona una subcategoría para eliminar", parent=ventana_padre)
            return
        
        subcategoria_nombre = self.listbox_subcategorias.get(seleccion[0])
        subcategoria_id = self.subcategorias_dict.get(subcategoria_nombre)
        
        respuesta = messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la subcategoría '{subcategoria_nombre}'?",
            parent=ventana_padre
        )
        
        if respuesta:
            try:
                self.cursor.execute("DELETE FROM subcategorias WHERE id = ?", (subcategoria_id,))
                self.conn.commit()
                self.cargar_subcategorias_de_categoria()
                messagebox.showinfo("Éxito", "Subcategoría eliminada correctamente", parent=ventana_padre)
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"No se pudo eliminar:\n{str(e)}", parent=ventana_padre)
    
    # (removed - rebuilt in new ERP UI)

