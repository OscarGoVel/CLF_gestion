#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo: dialogo_impresion.py
Diálogo para elegir impresión COMPLETA o PARCIAL de cotización/nota de remisión.

Impresión parcial:
  - Permite ocultar productos seleccionados del PDF.
  - El precio de los productos ocultos se "disuelve" proporcionalmente
    entre los productos visibles, según estas reglas:

      * Producto oculto SIN IVA  → su importe se distribuye entre TODOS
        los productos visibles (sin importar si llevan IVA o no).

      * Producto oculto CON IVA  → su importe se distribuye entre los
        productos visibles que TAMBIÉN tengan IVA, para conservar la
        correcta aplicación del impuesto.
        Si NO queda ningún producto visible con IVA, el importe se
        distribuye entre TODOS los visibles (sin IVA) sin agregar
        impuesto — el total del documento sigue siendo el mismo.

  - Los totales finales (SUBTOTAL, IVA, TOTAL) siempre coinciden con
    los de la cotización original.
"""

import tkinter as tk
from tkinter import ttk, messagebox


# ─────────────────────────────────────────────────────────────────────────────
#  LÓGICA DE DISTRIBUCIÓN DE PRECIOS
# ─────────────────────────────────────────────────────────────────────────────

def calcular_productos_visibles(productos_completos: list, ids_ocultos: set) -> list:
    """
    Distribuye el importe TOTAL (base + IVA) de los productos ocultos
    entre los productos visibles de forma proporcional.

    Reglas de distribución:
      - Oculto CON IVA  → su importe_total va a los visibles CON IVA
                          (el IVA sigue siendo parte del precio de esos visibles).
                          Si no quedan visibles con IVA, cae sobre TODOS los
                          visibles (sin añadir impuesto extra).
      - Oculto SIN IVA  → su importe_total va a los visibles SIN IVA.
                          Si no quedan visibles sin IVA, cae sobre TODOS los
                          visibles con IVA (sin añadir impuesto extra).

    Siempre se modifica `subtotal` e `importe_total` del visible;
    `aplica_iva` nunca se altera. El total del documento siempre cuadra.
    """
    import copy

    visibles = [p for p in productos_completos if p['producto_id'] not in ids_ocultos]
    ocultos  = [p for p in productos_completos if p['producto_id'] in ids_ocultos]

    if not visibles:
        return []

    ocultos_con_iva = [p for p in ocultos if p['aplica_iva']]
    ocultos_sin_iva = [p for p in ocultos if not p['aplica_iva']]

    monto_con_iva_a_dist = sum(p['importe_total'] for p in ocultos_con_iva)
    monto_sin_iva_a_dist = sum(p['importe_total'] for p in ocultos_sin_iva)

    visibles_con_iva = [p for p in visibles if p['aplica_iva']]
    visibles_sin_iva = [p for p in visibles if not p['aplica_iva']]

    visibles_ajustados = copy.deepcopy(visibles)
    idx = {p['producto_id']: p for p in visibles_ajustados}

    def _distribuir_sobre(monto: float, receptores_orig: list):
        """
        Suma `monto` a los visibles en `receptores_orig`,
        proporcional a su importe_total original.
        Actualiza subtotal, importe_total y precio_unitario.
        """
        base = sum(p['importe_total'] for p in receptores_orig)
        if base > 0:
            for p_orig in receptores_orig:
                p_adj = idx[p_orig['producto_id']]
                inc = monto * (p_orig['importe_total'] / base)
                p_adj['subtotal']       += inc
                p_adj['importe_total']  += inc
                p_adj['precio_unitario'] = p_adj['subtotal'] / p_adj['cantidad'] if p_adj['cantidad'] else 0
        else:
            parte = monto / len(receptores_orig)
            for p_orig in receptores_orig:
                p_adj = idx[p_orig['producto_id']]
                p_adj['subtotal']       += parte
                p_adj['importe_total']  += parte
                p_adj['precio_unitario'] = p_adj['subtotal'] / p_adj['cantidad'] if p_adj['cantidad'] else 0

    # ── Ocultos CON IVA → receptores con IVA; si no hay, todos los visibles ──
    if monto_con_iva_a_dist > 0:
        if visibles_con_iva:
            _distribuir_sobre(monto_con_iva_a_dist, visibles_con_iva)
        else:
            _distribuir_sobre(monto_con_iva_a_dist, visibles)

    # ── Ocultos SIN IVA → receptores sin IVA; si no hay, todos los visibles ──
    if monto_sin_iva_a_dist > 0:
        if visibles_sin_iva:
            _distribuir_sobre(monto_sin_iva_a_dist, visibles_sin_iva)
        else:
            _distribuir_sobre(monto_sin_iva_a_dist, visibles)

    return visibles_ajustados


def _calcular_totales(productos_visibles: list) -> dict:
    """
    Recalcula subtotal, IVA y total a partir de los productos visibles ajustados.

    Cada producto guarda por separado `subtotal` (base) e `iva` (ya calculado
    en BD). Tras el ajuste, `subtotal` crece con el importe redistribuido.
    Para los productos con IVA, el IVA sobre el incremento se recalcula
    aplicando la tasa del 16 % sobre la nueva base.
    """
    TASA_IVA = 0.16

    subtotal_total = 0.0
    iva_total      = 0.0

    for p in productos_visibles:
        base = p['subtotal']          # base ajustada (sin IVA)
        subtotal_total += base
        if p['aplica_iva']:
            iva_total += base * TASA_IVA

    return {
        'subtotal': round(subtotal_total, 2),
        'iva':      round(iva_total, 2),
        'total':    round(subtotal_total + iva_total, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  DIÁLOGO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class DialogoImpresion:
    """
    Ventana modal que pregunta al usuario si desea impresión COMPLETA o PARCIAL.

    Uso:
        dlg = DialogoImpresion(parent, conn, cotizacion_id, tipo='cotizacion')
        dlg.ventana.wait_window()

        if dlg.resultado == 'completa':
            # generar PDF sin cambios
        elif dlg.resultado == 'parcial':
            productos_pdf = dlg.productos_para_pdf   # lista ajustada
            totales_pdf   = dlg.totales_para_pdf     # subtotal/iva/total recalculados
    """

    COLOR_OCULTO  = '#ffe0e0'
    COLOR_VISIBLE = '#ffffff'

    def __init__(self, parent, conn, cotizacion_id: int, tipo: str = 'cotizacion'):
        """
        tipo: 'cotizacion' | 'remision'  (solo afecta el título del diálogo)
        """
        self.conn           = conn
        self.cotizacion_id  = cotizacion_id
        self.tipo           = tipo
        self.resultado           = None   # 'completa' | 'parcial' | None (cancelado)
        self.productos_para_pdf  = []     # productos ajustados (impresión parcial)
        self.totales_originales  = {}     # totales tal como están en la BD
        self.totales_para_pdf    = {}     # totales recalculados según visibles

        # ── Cargar datos ─────────────────────────────────────────────
        self._cargar_datos()

        # ── Crear ventana ────────────────────────────────────────────
        titulo = "Imprimir Cotización" if tipo == 'cotizacion' else "Imprimir Nota de Remisión"
        self.ventana = tk.Toplevel(parent)
        self.ventana.withdraw()
        self.ventana.title(titulo)
        self.ventana.geometry("860x560")
        self.ventana.resizable(True, True)
        self.ventana.configure(bg='#ecf0f1')

        self._construir_ui()

        self.ventana.transient(parent)
        self.ventana.grab_set()
        self.ventana.focus_set()
        self.ventana.after(0, self.ventana.deiconify)

    # ── Carga de datos desde BD ──────────────────────────────────────────────
    def _cargar_datos(self):
        cursor = self.conn.cursor()

        # Totales de la cotización
        cursor.execute("""
            SELECT subtotal, iva, total
            FROM cotizaciones
            WHERE id = ?
        """, (self.cotizacion_id,))
        row = cursor.fetchone()
        self.totales_originales = {
            'subtotal': row[0] if row else 0.0,
            'iva':      row[1] if row else 0.0,
            'total':    row[2] if row else 0.0,
        }

        # Productos — se carga cd.total (subtotal+iva) para que la distribución
        # incluya el IVA del producto oculto y el total impreso cuadre exactamente.
        cursor.execute("""
            SELECT p.id, p.nombre, p.unidad_medida,
                   cd.cantidad, cd.precio_unitario, cd.subtotal,
                   p.aplica_iva, cd.iva, cd.total
            FROM cotizacion_detalle cd
            JOIN productos p ON cd.producto_id = p.id
            WHERE cd.cotizacion_id = ?
            ORDER BY p.aplica_iva ASC, p.nombre
        """, (self.cotizacion_id,))

        self.productos_completos = []
        for r in cursor.fetchall():
            pid, nombre, unidad, cantidad, precio_u, subtotal_p, aplica_iva, iva_p, total_p = r
            self.productos_completos.append({
                'producto_id':     pid,
                'nombre':          nombre,
                'unidad':          unidad or '',
                'cantidad':        float(cantidad),
                'precio_unitario': float(precio_u),
                'subtotal':        float(subtotal_p),   # importe sin IVA
                'iva':             float(iva_p or 0),
                'importe_total':   float(total_p),      # subtotal + iva → lo que se distribuye
                'aplica_iva':      bool(aplica_iva),
            })

    # ── Construcción de UI ───────────────────────────────────────────────────
    def _construir_ui(self):
        pad = dict(padx=14, pady=10)

        # ── Título ────────────────────────────────────────────────────
        frame_titulo = tk.Frame(self.ventana, bg='#2c3e50', pady=12)
        frame_titulo.pack(fill='x')
        tk.Label(
            frame_titulo,
            text="🖨  Opciones de Impresión",
            font=('Arial', 14, 'bold'),
            bg='#2c3e50', fg='white'
        ).pack()

        # ── Selector de modo ──────────────────────────────────────────
        frame_modo = tk.LabelFrame(
            self.ventana, text="Modo de impresión",
            font=('Arial', 10, 'bold'), bg='#ecf0f1'
        )
        frame_modo.pack(fill='x', **pad)

        self.var_modo = tk.StringVar(value='completa')

        rb_completa = tk.Radiobutton(
            frame_modo, text="✅  Completa  — incluir todos los productos",
            variable=self.var_modo, value='completa',
            font=('Arial', 10), bg='#ecf0f1',
            command=self._on_modo_cambio
        )
        rb_completa.pack(anchor='w', padx=10, pady=(6, 2))

        rb_parcial = tk.Radiobutton(
            frame_modo,
            text="✂️  Parcial  — ocultar productos seleccionados y distribuir su precio",
            variable=self.var_modo, value='parcial',
            font=('Arial', 10), bg='#ecf0f1',
            command=self._on_modo_cambio
        )
        rb_parcial.pack(anchor='w', padx=10, pady=(2, 6))

        # ── Frame de productos (visible solo en modo parcial) ─────────
        self.frame_productos = tk.LabelFrame(
            self.ventana,
            text="Selecciona los productos a OCULTAR del PDF  "
                 "(su precio se distribuirá entre los visibles)",
            font=('Arial', 9, 'bold'), bg='#ecf0f1'
        )
        self.frame_productos.pack(fill='both', expand=True, padx=14, pady=(0, 6))

        # Instrucción
        tk.Label(
            self.frame_productos,
            text="☑  Marca los artículos que NO deben aparecer en el documento impreso.",
            font=('Arial', 9, 'italic'), fg='#555555', bg='#ecf0f1'
        ).pack(anchor='w', padx=8, pady=(4, 2))

        # Tabla
        cols = ('ocultar', 'nombre', 'unidad', 'cantidad', 'precio_u', 'subtotal', 'iva')
        frame_tree = tk.Frame(self.frame_productos, bg='#ecf0f1')
        frame_tree.pack(fill='both', expand=True, padx=8, pady=(0, 6))

        self.tree = ttk.Treeview(
            frame_tree,
            columns=cols,
            show='headings',
            selectmode='browse',
            height=9
        )

        self.tree.heading('ocultar',  text='Ocultar')
        self.tree.heading('nombre',   text='Producto')
        self.tree.heading('unidad',   text='Unidad')
        self.tree.heading('cantidad', text='Cantidad')
        self.tree.heading('precio_u', text='P.U. Original')
        self.tree.heading('subtotal', text='Subtotal')
        self.tree.heading('iva',      text='IVA')

        self.tree.column('ocultar',  width=64,  anchor='center', stretch=False)
        self.tree.column('nombre',   width=310, anchor='w')
        self.tree.column('unidad',   width=68,  anchor='center', stretch=False)
        self.tree.column('cantidad', width=72,  anchor='center', stretch=False)
        self.tree.column('precio_u', width=100, anchor='e',      stretch=False)
        self.tree.column('subtotal', width=100, anchor='e',      stretch=False)
        self.tree.column('iva',      width=54,  anchor='center', stretch=False)

        # Tags de color
        self.tree.tag_configure('oculto',  background=self.COLOR_OCULTO)
        self.tree.tag_configure('visible', background=self.COLOR_VISIBLE)
        self.tree.tag_configure('sin_iva', foreground='#555555')

        sb = ttk.Scrollbar(frame_tree, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        # Clic en fila → toggle ocultar
        self.tree.bind('<ButtonRelease-1>', self._on_click_fila)
        self.tree.bind('<Return>',          self._on_click_fila)

        # Estado de cada producto: True = ocultar, False = mostrar
        self._estado_oculto = {}  # producto_id → bool

        # Poblar tabla
        for prod in self.productos_completos:
            pid = prod['producto_id']
            self._estado_oculto[pid] = False
            tag = 'visible' if prod['aplica_iva'] else 'sin_iva'
            self.tree.insert('', 'end', iid=str(pid), values=(
                '☐',
                prod['nombre'],
                prod['unidad'],
                f"{prod['cantidad']:g}",
                f"$ {prod['precio_unitario']:,.2f}",
                f"$ {prod['subtotal']:,.2f}",
                'Sí' if prod['aplica_iva'] else 'No',
            ), tags=(tag,))

        # ── Panel de preview de totales ───────────────────────────────
        self.frame_preview = tk.Frame(self.frame_productos, bg='#ecf0f1')
        self.frame_preview.pack(fill='x', padx=8, pady=(2, 6))

        tk.Label(self.frame_preview, text="Preview de totales ajustados:",
                 font=('Arial', 8, 'bold'), bg='#ecf0f1', fg='#34495e').pack(side='left', padx=(0, 10))

        self.lbl_sub  = tk.Label(self.frame_preview, font=('Arial', 8), bg='#ecf0f1', fg='#555')
        self.lbl_iva  = tk.Label(self.frame_preview, font=('Arial', 8), bg='#ecf0f1', fg='#555')
        self.lbl_tot  = tk.Label(self.frame_preview, font=('Arial', 9, 'bold'), bg='#ecf0f1', fg='#c0392b')
        self.lbl_sub.pack(side='left', padx=6)
        self.lbl_iva.pack(side='left', padx=6)
        self.lbl_tot.pack(side='left', padx=6)

        self._actualizar_preview()

        # Estado inicial: frame productos deshabilitado
        self._on_modo_cambio()

        # ── Botones ───────────────────────────────────────────────────
        frame_btn = tk.Frame(self.ventana, bg='#ecf0f1')
        frame_btn.pack(fill='x', padx=14, pady=(4, 12))

        tk.Button(
            frame_btn, text="🖨  Generar PDF",
            command=self._confirmar,
            bg='#27ae60', fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2', padx=20, pady=8, relief='flat'
        ).pack(side='left', padx=(0, 8))

        tk.Button(
            frame_btn, text="❌  Cancelar",
            command=self._cancelar,
            bg='#e74c3c', fg='white',
            font=('Arial', 11, 'bold'),
            cursor='hand2', padx=20, pady=8, relief='flat'
        ).pack(side='left')

    # ── Callbacks ────────────────────────────────────────────────────────────
    def _on_modo_cambio(self):
        """Habilita/deshabilita la tabla según el modo seleccionado."""
        modo = self.var_modo.get()
        state = 'normal' if modo == 'parcial' else 'disabled'
        # En Tkinter no hay 'disabled' para Treeview directamente;
        # controlamos con el binding y el color del frame.
        if modo == 'completa':
            self.frame_productos.configure(
                fg='#aaaaaa',
                text="Selecciona los productos a OCULTAR del PDF  "
                     "(disponible en modo Parcial)"
            )
        else:
            self.frame_productos.configure(
                fg='#333333',
                text="Selecciona los productos a OCULTAR del PDF  "
                     "(su precio se distribuirá entre los visibles)"
            )

    def _on_click_fila(self, event=None):
        """Toggle del estado ocultar/mostrar al hacer clic en una fila."""
        if self.var_modo.get() != 'parcial':
            return

        sel = self.tree.focus()
        if not sel:
            return

        pid = int(sel)
        nuevo_estado = not self._estado_oculto[pid]

        # Validar: no se puede ocultar TODOS los productos
        visibles_tras_cambio = [
            p for p in self.productos_completos
            if not (self._estado_oculto[p['producto_id']]
                    if p['producto_id'] != pid else nuevo_estado)
        ]
        if not visibles_tras_cambio:
            messagebox.showwarning(
                "Operación no válida",
                "Debe quedar al menos un producto visible en el PDF.",
                parent=self.ventana
            )
            return

        self._estado_oculto[pid] = nuevo_estado

        # Actualizar icono y color
        valores = list(self.tree.item(sel, 'values'))
        prod = next(p for p in self.productos_completos if p['producto_id'] == pid)

        if nuevo_estado:
            valores[0] = '☑'
            self.tree.item(sel, values=valores, tags=('oculto',))
        else:
            valores[0] = '☐'
            tag = 'visible' if prod['aplica_iva'] else 'sin_iva'
            self.tree.item(sel, values=valores, tags=(tag,))

        self._actualizar_preview()

    def _actualizar_preview(self):
        """Recalcula y muestra los totales ajustados en el panel de preview."""
        ids_ocultos = {pid for pid, oculto in self._estado_oculto.items() if oculto}

        if not ids_ocultos:
            t = self.totales_originales
            self.lbl_sub.config(text=f"Subtotal: ${t['subtotal']:,.2f}")
            self.lbl_iva.config(text=f"IVA: ${t['iva']:,.2f}")
            self.lbl_tot.config(text=f"TOTAL: ${t['total']:,.2f}")
            return

        # Recalcular con los productos realmente visibles
        visibles = calcular_productos_visibles(self.productos_completos, ids_ocultos)
        t = _calcular_totales(visibles)
        self.lbl_sub.config(text=f"Subtotal: ${t['subtotal']:,.2f}")
        self.lbl_iva.config(text=f"IVA: ${t['iva']:,.2f}")
        self.lbl_tot.config(text=f"TOTAL: ${t['total']:,.2f}")

    def _ids_ocultos(self) -> set:
        return {pid for pid, oculto in self._estado_oculto.items() if oculto}

    def _confirmar(self):
        modo = self.var_modo.get()

        if modo == 'completa':
            self.resultado = 'completa'
            self.ventana.destroy()
            return

        # Modo parcial
        ids_ocultos = self._ids_ocultos()

        if not ids_ocultos:
            # Ningún producto marcado → equivale a completa
            respuesta = messagebox.askyesno(
                "Sin productos ocultos",
                "No marcaste ningún producto para ocultar.\n\n"
                "¿Deseas generar el PDF completo de todas formas?",
                parent=self.ventana
            )
            if respuesta:
                self.resultado = 'completa'
                self.ventana.destroy()
            return

        # Calcular y guardar productos ajustados
        self.productos_para_pdf = calcular_productos_visibles(
            self.productos_completos, ids_ocultos
        )

        # ── Recalcular totales reales según los productos visibles ────
        # No se usan los totales de la BD porque el IVA puede cambiar:
        # si los únicos productos con IVA fueron ocultados, el IVA impreso
        # debe ser $0 aunque la cotización en BD tenga IVA registrado.
        self.totales_para_pdf = _calcular_totales(self.productos_para_pdf)

        # Mostrar resumen antes de confirmar
        ocultos_nombres = [
            p['nombre'] for p in self.productos_completos
            if p['producto_id'] in ids_ocultos
        ]
        t = self.totales_para_pdf
        msg = (
            f"Se ocultarán {len(ocultos_nombres)} producto(s):\n\n"
            + "\n".join(f"  • {n}" for n in ocultos_nombres)
            + f"\n\nSu precio se distribuirá entre los "
              f"{len(self.productos_para_pdf)} productos visibles.\n\n"
              f"Subtotal: $ {t['subtotal']:,.2f}\n"
              f"IVA:      $ {t['iva']:,.2f}\n"
              f"Total:    $ {t['total']:,.2f}\n\n"
              f"¿Generar el PDF?"
        )
        if messagebox.askyesno("Confirmar impresión parcial", msg, parent=self.ventana):
            self.resultado = 'parcial'
            self.ventana.destroy()

    def _cancelar(self):
        self.resultado = None
        self.ventana.destroy()
