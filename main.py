#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Gestión Comercial
Comercializadora, Logística y Fuerza Yucateca
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
from datetime import datetime
import os
from modules.cotizaciones import VentanaCotizacion
from modules.entregas import VentanaEntregaParcial
from ui.generador_pdf_cly import GeneradorPDFCLY
from ui.dialogo_impresion import DialogoImpresion
from modules.stock import SeccionStock
from modules.compras import VentanaCompra
from modules.estado_de_cuenta import VentanaEstadoCuenta
from modules.facturacion import SeccionFacturacion
from modules.vinculacion import PanelVinculacion, detectar_pendientes
from selector_empresa import mostrar_selector, cargar_config, guardar_config
from db_init import inicializar_bd
from ui.dashboard import Dashboard
from ui.catalogos import Catalogos
from ui.cotizaciones_ui import CotizacionesUI

# Información de la empresa activa (se llena al seleccionar empresa al arrancar)
EMPRESA = {
    'nombre': '',
    'rfc':    '',
    'email':  '',
    'telefono': '',
    'direccion': '',
}

# Porcentajes de utilidad por tipo de cliente
UTILIDAD = {
    'Gobierno': 40,
    'Hotel': 35
}

class SistemaGestion:
    def __init__(self, root, empresa=None):
        self.root    = root
        self.empresa = empresa or {}

        # Actualizar dict global EMPRESA con los datos de la empresa activa
        global EMPRESA
        if empresa:
            EMPRESA.update({
                'nombre':    empresa.get('nombre', ''),
                'rfc':       empresa.get('rfc', ''),
                'email':     empresa.get('email', ''),
                'telefono':  empresa.get('telefono', ''),
                'direccion': empresa.get('direccion', ''),
            })

        titulo = f"Sistema de Gestión — {empresa['nombre']}" if empresa else "Sistema de Gestión - CLF"
        self.root.title(titulo)
        self.root.geometry("1200x700")

        # Inicializar base de datos (usa la ruta de la empresa seleccionada)
        self.init_database(empresa.get('db_path') if empresa else None)

        # Crear interfaz
        self.crear_interfaz()
    
    def _configurar_sorting_treeview(self, tree, columnas_numericas=None):
        """
        Configura ordenamiento por click en headers de columnas.
        El sort activo se persiste en tree._sort_col y tree._sort_reverse
        para que pueda reaplicarse tras una recarga de datos.

        Args:
            tree: ttk.Treeview widget
            columnas_numericas: lista de nombres de columnas con números/montos
        """
        if columnas_numericas is None:
            columnas_numericas = []

        # Estado persistente en el propio widget (sobrevive recargas)
        tree._sort_col     = None   # columna activa
        tree._sort_reverse = False  # dirección
        tree._sort_numericas = set(columnas_numericas)

        import re as _re

        def extraer_numero(texto):
            try:
                limpio = str(texto).replace('$', '').replace(',', '').replace(' ', '')
                m = _re.search(r'-?\d+\.?\d*', limpio)
                return float(m.group()) if m else 0
            except Exception:
                return 0

        def aplicar_sort(col, reverse):
            """Ordena los items actuales del tree por col/reverse."""
            items = [(tree.set(k, col), k) for k in tree.get_children('')]
            if col in tree._sort_numericas:
                items.sort(key=lambda t: extraer_numero(t[0]), reverse=reverse)
            else:
                items.sort(key=lambda t: str(t[0]).lower(), reverse=reverse)
            for index, (_, k) in enumerate(items):
                tree.move(k, '', index)
            # Actualizar indicadores en headers
            indicador = ' ▼' if reverse else ' ▲'
            for c in tree['columns']:
                txt = str(tree.heading(c)['text']).replace(' ▲', '').replace(' ▼', '')
                tree.heading(c, text=txt + (indicador if c == col else ''))

        def ordenar_por_columna(col):
            # Alternar dirección si es la misma columna
            if tree._sort_col == col:
                tree._sort_reverse = not tree._sort_reverse
            else:
                tree._sort_col     = col
                tree._sort_reverse = False
            aplicar_sort(tree._sort_col, tree._sort_reverse)

        # Método público para reaplicar el sort después de recargar datos
        def reaplicar_sort():
            if tree._sort_col:
                aplicar_sort(tree._sort_col, tree._sort_reverse)

        tree.reaplicar_sort = reaplicar_sort

        # Configurar click en cada header
        for col in tree['columns']:
            tree.heading(col, command=lambda c=col: ordenar_por_columna(c))

        return tree
    
    @staticmethod
    def _centrar_ventana(win, padre=None, ancho=None, alto=None):
        """Centra una ventana respecto a su padre o a la pantalla.
        Si se pasan ancho/alto los aplica antes de centrar.
        """
        if ancho and alto:
            win.geometry(f"{ancho}x{alto}")
        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()
        if padre:
            px = padre.winfo_rootx()
            py = padre.winfo_rooty()
            pw = padre.winfo_width()
            ph = padre.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
        else:
            x = (win.winfo_screenwidth()  - w) // 2
            y = (win.winfo_screenheight() - h) // 2
        win.geometry(f"+{max(0,x)}+{max(0,y)}")

    def init_database(self, db_path=None):
        """Inicializa la base de datos SQLite.
        Delega la creación de tablas a db_init.inicializar_bd() para que
        main.py y selector_empresa compartan exactamente el mismo esquema.
        """
        ruta = db_path or 'gestion_comercial.db'
        self.conn, self.cursor = inicializar_bd(ruta)

        # Backfill historial de precios con los precios actuales de productos
        self.cursor.execute("""
            INSERT OR IGNORE INTO producto_precio_historial
                (producto_id, precio, fecha, motivo, fuente)
            SELECT p.id,
                   p.precio_base,
                   COALESCE(p.precio_base_fecha, DATE('now')),
                   'Precio inicial (backfill)',
                   'backfill'
            FROM productos p
            WHERE p.precio_base IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM producto_precio_historial h
                  WHERE h.producto_id = p.id
              )
        """)
        self.conn.commit()

    def crear_interfaz(self):
        """Crea la interfaz principal estilo ERP compacto"""

        # ── Paleta de colores ──────────────────────────────────────────────
        self.C = {
            # ── Navegación ────────────────────────────────────────────────
            'nav_bg':          '#1e2d45',
            'nav_active':      '#eceff4',
            'nav_hover':       '#2b3a55',
            'nav_text':        '#94a3b8',
            'nav_active_text': '#1e2d45',
            # ── Layout principal ──────────────────────────────────────────
            'kpi_bg':          '#f7f9fc',
            'kpi_border':      '#d0d7e4',
            'toolbar_bg':      '#d8dde8',
            'toolbar_border':  '#c5ccd8',
            'content_bg':      '#eceff4',
            'card_bg':         'white',
            # ── Acento / acciones ─────────────────────────────────────────
            'accent':          '#0f7b5e',   # verde principal
            'accent2':         '#1a4b8c',   # azul medio
            'accent3':         '#1e3a5f',   # azul oscuro
            'accent_dark':     '#065f46',   # verde oscuro
            'purple':          '#7c3aed',   # seguimiento / vinculación
            'success':         '#27ae60',   # verde éxito
            'success2':        '#16a34a',   # verde éxito alt
            'success_alt':     '#16a085',   # teal éxito
            'warn':            '#d97706',   # ámbar advertencia
            'danger':          '#c0392b',   # rojo peligro
            'danger2':         '#dc2626',   # rojo alt
            'dark2':           '#2c3e50',   # gris oscuro
            # ── Texto ─────────────────────────────────────────────────────
            'text_dark':       '#1e2d45',
            'text_secondary':  '#374151',
            'text_muted':      '#6b7e99',
            'text_muted2':     '#6b7280',
            'text_faint':      '#9ca3af',
            # ── Fondos de UI ──────────────────────────────────────────────
            'modal_bg':        '#f1f5f9',   # fondo de modales / diálogos
            'form_bg':         '#f8fafc',   # fondo de formularios / cards
            'border':          '#e2e8f0',   # bordes, separadores
            'bg_success':      '#f0fdf4',   # fondo verde claro
            'bg_warn':         '#fef3c7',   # fondo ámbar claro
        }

        # ── Barra de navegación superior ───────────────────────────────────
        nav = tk.Frame(self.root, bg=self.C['nav_bg'], height=38)
        nav.pack(fill='x')
        nav.pack_propagate(False)

        # Logo / marca
        logo_frame = tk.Frame(nav, bg='#141f30', padx=14)
        logo_frame.pack(side='left', fill='y')
        tk.Label(logo_frame, text='⚙  GESTIÓN', font=('Arial', 10, 'bold'),
                 bg='#141f30', fg='#1aab82').pack(side='left', anchor='center')

        # Separador
        tk.Frame(nav, bg='#141f30', width=1).pack(side='left', fill='y')

        # Botones de navegación
        self._nav_botones = {}
        self._seccion_actual = tk.StringVar(value='dashboard')

        secciones = [
            ('dashboard',   '📊  Dashboard'),
            ('cotizaciones','📄  Cotizaciones'),
            ('facturacion', '🧾  Facturación'),
            ('catalogos',   '📚  Catálogos'),
            ('stock',       '📦  Stock'),
        ]

        for key, texto in secciones:
            btn = tk.Button(
                nav, text=texto,
                font=('Arial', 9, 'bold'),
                bg=self.C['nav_bg'], fg=self.C['nav_text'],
                activebackground=self.C['nav_hover'], activeforeground='white',
                bd=0, padx=14, pady=0,
                cursor='hand2', relief='flat',
                command=lambda k=key: self._navegar(k)
            )
            btn.pack(side='left', fill='y')
            self._nav_botones[key] = btn

        # Badge de alertas en nav
        self._badge_cot = tk.Label(nav, text='', font=('Arial', 8, 'bold'),
                                    bg='#c0392b', fg='white',
                                    padx=4, pady=0)
        # se posiciona dinámicamente junto al botón cotizaciones

        # ── Lado derecho: empresa activa + botón cambiar ───────────────────
        btn_cambiar = tk.Button(
            nav, text='⇄  Cambiar empresa',
            font=('Arial', 8), bg='#141f30', fg='#64748b',
            activebackground='#1e2d45', activeforeground='#94a3b8',
            bd=0, padx=10, pady=0, cursor='hand2', relief='flat',
            command=self._cambiar_empresa
        )
        btn_cambiar.pack(side='right', fill='y', padx=(0, 4))

        nombre_emp = self.empresa.get('nombre', '') if self.empresa else ''
        if nombre_emp:
            # Truncar si es muy largo
            display = nombre_emp if len(nombre_emp) <= 32 else nombre_emp[:30] + '…'
            tk.Label(nav, text=f'🏢  {display}',
                     font=('Arial', 8), bg=self.C['nav_bg'],
                     fg='#475569').pack(side='right', padx=(0, 6), pady=0)

        # ── Área de contenido ──────────────────────────────────────────────
        self._content_area = tk.Frame(self.root, bg=self.C['content_bg'])
        self._content_area.pack(fill='both', expand=True)

        # ── Barra de estado inferior ───────────────────────────────────────
        status_bar = tk.Frame(self.root, bg='#dde3ec', height=22)
        status_bar.pack(fill='x', side='bottom')
        status_bar.pack_propagate(False)
        # Icono de actividad (punto animado)
        self._status_ico = tk.Label(status_bar, text='●',
            font=('Arial', 8), bg='#dde3ec', fg='#9ca3af', padx=6)
        self._status_ico.pack(side='left')
        # Texto principal
        self._status_lbl = tk.Label(status_bar, text='Listo',
            font=('Arial', 8), bg='#dde3ec', fg='#6b7280', anchor='w')
        self._status_lbl.pack(side='left', fill='x', expand=True)
        # Contador de registros (lado derecho)
        self._status_count = tk.Label(status_bar, text='',
            font=('Arial', 8), bg='#dde3ec', fg='#9ca3af', padx=8)
        self._status_count.pack(side='right')
        # Separador vertical
        tk.Frame(status_bar, bg='#c5ccd8', width=1).pack(
            side='right', fill='y', pady=3)

        # Crear todas las secciones (frames apilados)
        self._secciones = {}
        self.dashboard = Dashboard(self)
        self.dashboard.crear_seccion()
        self.cotizaciones_ui = CotizacionesUI(self)
        self.cotizaciones_ui.crear_seccion()
        self.catalogos = Catalogos(self)
        self.catalogos.crear_seccion()
        self._facturacion = SeccionFacturacion(self)
        self._stock = SeccionStock(self)

        # Mostrar dashboard al inicio
        self._navegar('dashboard')
        self.actualizar_dashboard()


    # ── Delegaciones a Catalogos ──────────────────────────────────────────────
    def _ventana_producto_prefill(self, datos, callback=None):
        """Delegado a Catalogos — llamado desde vinculacion."""
        self.catalogos._ventana_producto_prefill(datos, callback)

    def _ventana_proveedor(self, modo='nuevo', prov_id=None, _prefill=None, _callback=None):
        """Delegado a Catalogos."""
        self.catalogos._ventana_proveedor(modo, prov_id, _prefill, _callback)

    def ventana_cliente(self, modo='nuevo', cliente_id=None, _prefill=None, _callback=None):
        """Delegado a Catalogos."""
        self.catalogos.ventana_cliente(modo, cliente_id, _prefill, _callback)

    def ventana_producto(self, modo='nuevo', producto_id=None):
        """Delegado a Catalogos."""
        self.catalogos.ventana_producto(modo, producto_id)

    def cargar_clientes(self):
        """Delegado a Catalogos."""
        if hasattr(self, 'catalogos'): self.catalogos.cargar_clientes()

    def cargar_productos(self):
        """Delegado a Catalogos."""
        if hasattr(self, 'catalogos'): self.catalogos.cargar_productos()

    def cargar_proveedores(self):
        """Delegado a Catalogos."""
        if hasattr(self, 'catalogos'): self.catalogos.cargar_proveedores()

    def cargar_compras(self):
        """Delegado a Catalogos."""
        if hasattr(self, 'catalogos'): self.catalogos.cargar_compras()

    def nueva_compra(self):
        """Delegado a Catalogos."""
        self.catalogos.nueva_compra()

    def editar_compra(self):
        """Delegado a Catalogos."""
        self.catalogos.editar_compra()

    def ver_compra(self):
        """Delegado a Catalogos."""
        self.catalogos.ver_compra()

    def gestionar_categorias(self):
        """Delegado a Catalogos."""
        self.catalogos.gestionar_categorias()

    def generar_presupuesto_compra(self):
        """Delegado a Catalogos."""
        self.catalogos.generar_presupuesto_compra()

    def actualizar_dashboard(self):
        """Delega al componente Dashboard."""
        if hasattr(self, 'dashboard'):
            self.dashboard.actualizar_dashboard()

    def _set_status(self, texto, tipo='info', count=None):
        """Actualiza la barra de estado inferior.
        tipo: 'info' | 'ok' | 'warn' | 'busy'
        """
        colores = {
            'info':  ('#6b7280', '#9ca3af'),
            'ok':    ('#16a34a', '#16a34a'),
            'warn':  ('#d97706', '#d97706'),
            'busy':  ('#1a4b8c', '#1a4b8c'),
        }
        fg_txt, fg_ico = colores.get(tipo, colores['info'])
        if hasattr(self, '_status_lbl'):
            self._status_lbl.config(text=texto, fg=fg_txt)
            self._status_ico.config(fg=fg_ico,
                text='⟳' if tipo == 'busy' else '●')
            if count is not None:
                self._status_count.config(text=count)
            self.root.update_idletasks()

    def _navegar(self, seccion):
        """Muestra la sección seleccionada, actualiza botones y refresca datos"""
        self._seccion_actual.set(seccion)

        # Ocultar todas las secciones
        for f in self._secciones.values():
            f.pack_forget()

        # Mostrar la seleccionada
        self._secciones[seccion].pack(fill='both', expand=True)

        # Actualizar estilos de botones
        for key, btn in self._nav_botones.items():
            if key == seccion:
                btn.config(bg=self.C['nav_active'],
                           fg=self.C['nav_active_text'])
            else:
                btn.config(bg=self.C['nav_bg'],
                           fg=self.C['nav_text'])

        # ── Refrescar datos de la sección al navegar ───────────────────────
        nombres = {
            'dashboard':   'Dashboard',
            'cotizaciones':'Cotizaciones',
            'facturacion': 'Facturación',
            'catalogos':   'Catálogos',
            'stock':       'Stock',
        }
        self._set_status(f'Cargando {nombres.get(seccion, seccion)}…', 'busy')
        self.root.config(cursor='watch')
        try:
            if seccion == 'dashboard':
                self.actualizar_dashboard()
                self._set_status('Dashboard actualizado', 'ok')
            elif seccion == 'cotizaciones':
                self.cargar_cotizaciones()
                self.actualizar_dashboard()
                n = len(self.cotizaciones_ui.tree_cotizaciones.get_children())                     if hasattr(self, 'cotizaciones_ui') else 0
                self._set_status('Cotizaciones cargadas', 'ok',
                                  count=f'{n} registro{"s" if n!=1 else ""}')
            elif seccion == 'facturacion':
                if hasattr(self, '_facturacion'):
                    self._facturacion.cargar_facturas()
                self._set_status('Facturación cargada', 'ok')
            elif seccion == 'catalogos':
                self.cargar_clientes()
                self.cargar_productos()
                self.cargar_proveedores()
                self.cargar_compras()
                self._set_status('Catálogos cargados', 'ok')
            elif seccion == 'stock':
                if hasattr(self, '_stock'):
                    self._stock.cargar_vista_stock()
                    self._stock.cargar_historial()
                self._set_status('Stock actualizado', 'ok')
        except Exception:
            self._set_status('Error al cargar sección', 'warn')
        finally:
            self.root.config(cursor='')

    def _toolbar_sep(self, parent):
        """Inserta un separador vertical en el toolbar"""
        tk.Frame(parent, bg=self.C['toolbar_border'],
                 width=1).pack(side='left', fill='y', pady=4, padx=4)

    def _toolbar_btn(self, parent, texto, comando, color=None, peligro=False):
        """Botón estilo toolbar ERP"""
        bg = color or self.C['toolbar_bg']
        fg = 'white' if color else self.C['text_dark']
        if peligro:
            bg, fg = self.C['danger'], 'white'
        b = tk.Button(
            parent, text=texto,
            command=comando,
            font=('Arial', 9),
            bg=bg, fg=fg,
            activebackground=self.C['nav_hover'], activeforeground='white',
            bd=1, relief='raised',
            cursor='hand2', padx=8, pady=3
        )
        b.pack(side='left', padx=2, pady=3)
        return b

    def _toolbar_menu(self, parent, texto, opciones, color=None):
        """Menubutton estilo toolbar"""
        bg = color or self.C['toolbar_bg']
        fg = 'white' if color else self.C['text_dark']
        mb = tk.Menubutton(
            parent, text=texto,
            font=('Arial', 9),
            bg=bg, fg=fg,
            activebackground=self.C['nav_hover'], activeforeground='white',
            bd=1, relief='raised',
            cursor='hand2', padx=8, pady=3
        )
        mb.pack(side='left', padx=2, pady=3)
        menu = tk.Menu(mb, tearoff=0)
        mb['menu'] = menu
        for item in opciones:
            if item is None:
                menu.add_separator()
            else:
                lbl, cmd = item
                menu.add_command(label=lbl, command=cmd)
        return mb

    # ── SECCIÓN: COTIZACIONES ──────────────────────────────────────────────

    # ── Delegaciones a CotizacionesUI ────────────────────────────────────────
    def cargar_cotizaciones(self):
        if hasattr(self, 'cotizaciones_ui'): self.cotizaciones_ui.cargar_cotizaciones()

    def nueva_cotizacion(self):
        self.cotizaciones_ui.nueva_cotizacion()

    def editar_cotizacion(self):
        self.cotizaciones_ui.editar_cotizacion()

    def ver_cotizacion(self):
        self.cotizaciones_ui.ver_cotizacion()

    def generar_pdf_cotizacion(self):
        self.cotizaciones_ui.generar_pdf_cotizacion()

    def generar_pdf_cotizacion_nueva(self):
        self.cotizaciones_ui.generar_pdf_cotizacion_nueva()

    def generar_nota_remision(self):
        self.cotizaciones_ui.generar_nota_remision()

    def marcar_entregada(self):
        self.cotizaciones_ui.marcar_entregada()

    def marcar_entregada_completa(self):
        self.cotizaciones_ui.marcar_entregada_completa()

    def marcar_entregada_parcial(self):
        self.cotizaciones_ui.marcar_entregada_parcial()

    def cancelar_cotizacion(self):
        self.cotizaciones_ui.cancelar_cotizacion()

    def ver_detalle_cotizacion(self):
        self.cotizaciones_ui.ver_detalle_cotizacion()

    def vincular_orden_compra(self):
        self.cotizaciones_ui.vincular_orden_compra()

    def cambiar_estado_rapido(self, nuevo_estado):
        self.cotizaciones_ui.cambiar_estado_rapido(nuevo_estado)

    def marcar_facturada(self):
        self.cotizaciones_ui.marcar_facturada()

    def marcar_pagada(self):
        self.cotizaciones_ui.marcar_pagada()

    def ver_seguimiento_cotizacion(self):
        self.cotizaciones_ui.ver_seguimiento_cotizacion()

    def ver_estado_cuenta(self):
        self.cotizaciones_ui.ver_estado_cuenta()

    def gestionar_documentos_cotizacion(self):
        self.cotizaciones_ui.gestionar_documentos_cotizacion()

    def _abrir_centro_vinculacion(self):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._abrir_centro_vinculacion()

    def _actualizar_badge_vinculacion(self):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._actualizar_badge_vinculacion()

    def _build_cotizacion_preview_panel(self, parent):
        return self.cotizaciones_ui._build_cotizacion_preview_panel(parent)

    def _on_select_cotizacion(self):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._on_select_cotizacion()

    def _actualizar_preview_cot(self, cot_id):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._actualizar_preview_cot(cot_id)

    def _doble_clic_cotizacion(self, event):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._doble_clic_cotizacion(event)

    def _hover_icono_cotizacion(self, event):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._hover_icono_cotizacion(event)

    def _click_icono_documento_cotizacion(self, event):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._click_icono_documento_cotizacion(event)

    def _mostrar_detalle_factura_xml(self, cot_id, parent_win=None):
        if hasattr(self, 'cotizaciones_ui'):
            self.cotizaciones_ui._mostrar_detalle_factura_xml(cot_id, parent_win)

    def _sync_seguimiento_desde_estado(self, cotizacion_id, nuevo_estado, fecha=None):
        self.cotizaciones_ui._sync_seguimiento_desde_estado(cotizacion_id, nuevo_estado, fecha)

    def _sync_estado_desde_seguimiento(self, cotizacion_id, etapa, completada):
        self.cotizaciones_ui._sync_estado_desde_seguimiento(cotizacion_id, etapa, completada)

    def _cambiar_empresa(self):
        """Cierra la sesión actual y regresa al selector de empresa."""
        if not messagebox.askyesno(
            'Cambiar empresa',
            '¿Deseas cerrar la sesión actual y regresar al selector de empresa?',
            parent=self.root
        ):
            return
        # Cerrar BD actual
        try:
            self.conn.close()
        except Exception:
            pass
        # Destruir ventana principal
        self.root.destroy()
        # Abrir selector de empresa de nuevo
        from selector_empresa import mostrar_selector
        empresa = mostrar_selector()
        if empresa is None:
            return  # Cerró sin elegir → terminar
        # Abrir sistema con la nueva empresa
        new_root = tk.Tk()
        SistemaGestion(new_root, empresa=empresa)
        new_root.mainloop()

    # ── SECCIÓN: DASHBOARD ─────────────────────────────────────────────────
    def __del__(self):
        """Cierra la conexión a la base de datos al cerrar la aplicación"""
        if hasattr(self, 'conn'):
            self.conn.close()

if __name__ == '__main__':
    # ── Selector de empresa ───────────────────────────────────────────────────
    empresa = mostrar_selector()

    if empresa is None:
        # Usuario cerró el selector sin elegir → no arrancar
        import sys
        sys.exit(0)

    # ── Sistema principal ─────────────────────────────────────────────────────
    root = tk.Tk()
    app  = SistemaGestion(root, empresa=empresa)
    root.mainloop()
