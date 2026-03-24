#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui/analisis.py
Sección de Análisis con gráficas matplotlib embebidas en Tkinter.

Tabs:
  1. Ventas y Cobros  — ingresos por mes, cotizaciones por estado, top clientes
  2. Productos        — top cotizados, productos sin movimiento
  3. Compras y Costos — compras por mes, top proveedores
  4. Rentabilidad     — margen esperado vs real, utilidad acumulada
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, date
import calendar

try:
    import matplotlib
    matplotlib.use('TkAgg')
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.ticker as mticker
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ── Paleta consistente con el sistema ─────────────────────────────────────────
_COLORS = {
    'primary':   '#1a4b8c',
    'accent':    '#0f7b5e',
    'warn':      '#d97706',
    'danger':    '#c0392b',
    'purple':    '#7c3aed',
    'teal':      '#0891b2',
    'muted':     '#94a3b8',
    'bg':        '#f8fafc',
    'grid':      '#e2e8f0',
    'text':      '#1e2d45',
}

_PALETTE = [
    '#1a4b8c', '#0f7b5e', '#d97706', '#c0392b',
    '#7c3aed', '#0891b2', '#16a34a', '#9333ea',
]


def _periodo_sql(periodo: str):
    """Devuelve (fecha_desde, fecha_hasta) como strings 'YYYY-MM-DD'."""
    hoy = date.today()
    if periodo == 'Este mes':
        inicio = hoy.replace(day=1)
        ultimo = hoy.replace(day=calendar.monthrange(hoy.year, hoy.month)[1])
        return str(inicio), str(ultimo)
    elif periodo == 'Últimos 3 meses':
        if hoy.month <= 3:
            inicio = date(hoy.year - 1, hoy.month + 9, 1)
        else:
            inicio = date(hoy.year, hoy.month - 3, 1)
        return str(inicio), str(hoy)
    elif periodo == 'Últimos 6 meses':
        if hoy.month <= 6:
            inicio = date(hoy.year - 1, hoy.month + 6, 1)
        else:
            inicio = date(hoy.year, hoy.month - 6, 1)
        return str(inicio), str(hoy)
    elif periodo == 'Este año':
        return str(date(hoy.year, 1, 1)), str(hoy)
    else:  # Todo
        return '2000-01-01', str(hoy)


def _fmt_mxn(v):
    """$1,234,567.89"""
    if v >= 1_000_000:
        return f'${v/1_000_000:.1f}M'
    if v >= 1_000:
        return f'${v/1_000:.0f}K'
    return f'${v:,.0f}'


def _apply_style(ax, title='', xlabel='', ylabel='', yformat_mxn=False):
    ax.set_title(title, fontsize=11, fontweight='bold',
                 color=_COLORS['text'], pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color=_COLORS['muted'])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=_COLORS['muted'])
    ax.set_facecolor(_COLORS['bg'])
    ax.grid(axis='y', color=_COLORS['grid'], linewidth=0.8, zorder=0)
    ax.tick_params(colors=_COLORS['text'], labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COLORS['grid'])
    if yformat_mxn:
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(
            lambda x, _: _fmt_mxn(x)))


# ──────────────────────────────────────────────────────────────────────────────

class Analisis:
    """Sección 📈 Análisis."""

    PERIODOS = ['Este mes', 'Últimos 3 meses', 'Últimos 6 meses',
                'Este año', 'Todo']

    def __init__(self, sistema):
        self.sistema = sistema
        self.cursor  = sistema.cursor
        self.C       = sistema.C
        self._notebook = None
        self._periodo_var = None
        self._tab_frames  = {}   # tab_key → tk.Frame
        self._canvases    = {}   # tab_key → FigureCanvasTkAgg

    # ── Construcción del frame principal ──────────────────────────────────────

    def crear_seccion(self):
        sec = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['analisis'] = sec

        if not MATPLOTLIB_OK:
            tk.Label(sec,
                     text='⚠  matplotlib no está instalado.\n\n'
                          'Ejecuta:  pip install matplotlib',
                     font=('Arial', 12), bg=self.C['content_bg'],
                     fg=self.C.get('warn', '#d97706'), justify='center'
                     ).pack(expand=True)
            return

        # ── Toolbar ───────────────────────────────────────────────────────────
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], relief='flat', bd=0)
        tb.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        tk.Label(tb, text='Período:', font=('Arial', 9),
                 bg=self.C['toolbar_bg'],
                 fg=self.C['text_dark']).pack(side='left', padx=(8, 2), pady=4)

        self._periodo_var = tk.StringVar(value='Últimos 6 meses')
        cmb = ttk.Combobox(tb, textvariable=self._periodo_var,
                           values=self.PERIODOS, state='readonly', width=16)
        cmb.pack(side='left', padx=2, pady=4)
        cmb.bind('<<ComboboxSelected>>', lambda e: self._refresh_tab_actual())

        self.sistema._toolbar_btn(tb, '🔄 Actualizar',
                                  self._refresh_tab_actual)

        # ── Notebook (tabs) ───────────────────────────────────────────────────
        nb = ttk.Notebook(sec)
        nb.pack(fill='both', expand=True, padx=6, pady=6)
        self._notebook = nb

        tabs = [
            ('ventas',       '💰 Ventas y Cobros'),
            ('productos',    '🏷 Productos'),
            ('compras',      '🛒 Compras y Costos'),
            ('rentabilidad', '📊 Rentabilidad'),
        ]
        for key, label in tabs:
            frame = tk.Frame(nb, bg=_COLORS['bg'])
            nb.add(frame, text=f'  {label}  ')
            self._tab_frames[key] = frame

        nb.bind('<<NotebookTabChanged>>', self._on_tab_change)

    # ── Navegación entre tabs ─────────────────────────────────────────────────

    def _on_tab_change(self, event=None):
        idx = self._notebook.index('current')
        keys = ['ventas', 'productos', 'compras', 'rentabilidad']
        if idx < len(keys):
            self._render_tab(keys[idx])

    def _refresh_tab_actual(self):
        if not self._notebook:
            return
        idx = self._notebook.index('current')
        keys = ['ventas', 'productos', 'compras', 'rentabilidad']
        if idx < len(keys):
            # Destruir canvas existente para forzar re-render
            key = keys[idx]
            if key in self._canvases:
                try:
                    self._canvases[key].get_tk_widget().destroy()
                except Exception:
                    pass
                del self._canvases[key]
            self._render_tab(key)

    def refresh(self):
        """Llamado desde _navegar() al entrar a la sección."""
        self._refresh_tab_actual()

    def _render_tab(self, key):
        if key in self._canvases:
            return  # ya dibujado
        frame = self._tab_frames.get(key)
        if frame is None:
            return
        # Limpiar frame antes de redibujar
        for w in frame.winfo_children():
            w.destroy()
        periodo = self._periodo_var.get() if self._periodo_var else 'Este año'
        fecha_desde, fecha_hasta = _periodo_sql(periodo)
        try:
            if key == 'ventas':
                fig = self._fig_ventas(fecha_desde, fecha_hasta)
            elif key == 'productos':
                fig = self._fig_productos(fecha_desde, fecha_hasta)
            elif key == 'compras':
                fig = self._fig_compras(fecha_desde, fecha_hasta)
            elif key == 'rentabilidad':
                fig = self._fig_rentabilidad(fecha_desde, fecha_hasta)
            else:
                return
        except Exception as exc:
            tk.Label(frame, text=f'Error al generar gráfica:\n{exc}',
                     bg=_COLORS['bg'], fg=_COLORS['danger'],
                     font=('Arial', 10), justify='center').pack(expand=True)
            return

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        widget = canvas.get_tk_widget()
        widget.pack(fill='both', expand=True)
        self._canvases[key] = canvas

    # ── Tab 1: Ventas y Cobros ─────────────────────────────────────────────────

    def _fig_ventas(self, f_desde, f_hasta):
        fig = Figure(figsize=(14, 6), dpi=90, facecolor=_COLORS['bg'])
        fig.subplots_adjust(left=0.07, right=0.98, top=0.88,
                            bottom=0.15, wspace=0.35)

        # ── 1a: Cotizaciones por mes (total + cobrado) ────────────────────────
        self.cursor.execute('''
            SELECT strftime('%Y-%m', fecha) AS mes,
                   SUM(total)            AS total_cot,
                   SUM(monto_pagado)     AS cobrado
            FROM   cotizaciones
            WHERE  estado NOT IN ('Cancelada')
              AND  fecha BETWEEN ? AND ?
            GROUP BY mes
            ORDER BY mes
        ''', (f_desde, f_hasta))
        rows = self.cursor.fetchall()

        ax1 = fig.add_subplot(1, 3, 1)
        if rows:
            meses  = [r[0] for r in rows]
            totals = [r[1] or 0 for r in rows]
            cobrad = [r[2] or 0 for r in rows]
            x = range(len(meses))
            w = 0.38
            ax1.bar([i - w/2 for i in x], totals, width=w,
                    color=_COLORS['primary'], label='Cotizado', zorder=3)
            ax1.bar([i + w/2 for i in x], cobrad, width=w,
                    color=_COLORS['accent'], label='Cobrado', zorder=3)
            ax1.set_xticks(list(x))
            etqs = [m[5:] + '\n' + m[:4] for m in meses]
            ax1.set_xticklabels(etqs, fontsize=7)
            ax1.legend(fontsize=7, framealpha=0.7)
        else:
            ax1.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax1.transAxes, color=_COLORS['muted'])
        _apply_style(ax1, 'Cotizaciones por mes', yformat_mxn=True)

        # ── 1b: Pie — cotizaciones por estado ─────────────────────────────────
        self.cursor.execute('''
            SELECT estado, COUNT(*) AS n
            FROM   cotizaciones
            WHERE  fecha BETWEEN ? AND ?
            GROUP BY estado
            ORDER BY n DESC
        ''', (f_desde, f_hasta))
        rows2 = self.cursor.fetchall()

        ax2 = fig.add_subplot(1, 3, 2)
        if rows2:
            labels = [r[0] for r in rows2]
            sizes  = [r[1] for r in rows2]
            colors_pie = _PALETTE[:len(sizes)]
            wedges, texts, autotexts = ax2.pie(
                sizes, labels=labels, colors=colors_pie,
                autopct='%1.0f%%', startangle=90,
                textprops={'fontsize': 8, 'color': _COLORS['text']})
            for at in autotexts:
                at.set_fontsize(7)
                at.set_color('white')
        else:
            ax2.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax2.transAxes, color=_COLORS['muted'])
        ax2.set_title('Cotizaciones por estado', fontsize=11,
                      fontweight='bold', color=_COLORS['text'], pad=8)
        ax2.set_facecolor(_COLORS['bg'])

        # ── 1c: Top 10 clientes por monto ─────────────────────────────────────
        self.cursor.execute('''
            SELECT cl.nombre_comercial,
                   SUM(c.total)        AS total_cot,
                   SUM(c.monto_pagado) AS cobrado
            FROM   cotizaciones c
            JOIN   clientes cl ON cl.id = c.cliente_id
            WHERE  c.estado NOT IN ('Cancelada')
              AND  c.fecha BETWEEN ? AND ?
            GROUP BY cl.id
            ORDER BY total_cot DESC
            LIMIT  10
        ''', (f_desde, f_hasta))
        rows3 = self.cursor.fetchall()

        ax3 = fig.add_subplot(1, 3, 3)
        if rows3:
            nombres = [r[0][:18] for r in rows3][::-1]
            totals3 = [r[1] or 0 for r in rows3][::-1]
            cobr3   = [r[2] or 0 for r in rows3][::-1]
            y = range(len(nombres))
            ax3.barh(list(y), totals3, color=_COLORS['primary'],
                     label='Cotizado', zorder=3, height=0.55)
            ax3.barh(list(y), cobr3, color=_COLORS['accent'],
                     label='Cobrado', zorder=3, height=0.55, alpha=0.85)
            ax3.set_yticks(list(y))
            ax3.set_yticklabels(nombres, fontsize=7)
            ax3.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: _fmt_mxn(x)))
            ax3.tick_params(axis='x', labelsize=7)
            ax3.legend(fontsize=7, framealpha=0.7)
            ax3.grid(axis='x', color=_COLORS['grid'], zorder=0)
            for spine in ax3.spines.values():
                spine.set_edgecolor(_COLORS['grid'])
        else:
            ax3.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax3.transAxes, color=_COLORS['muted'])
        ax3.set_title('Top 10 clientes', fontsize=11, fontweight='bold',
                      color=_COLORS['text'], pad=8)
        ax3.set_facecolor(_COLORS['bg'])

        return fig

    # ── Tab 2: Productos ───────────────────────────────────────────────────────

    def _fig_productos(self, f_desde, f_hasta):
        fig = Figure(figsize=(14, 6), dpi=90, facecolor=_COLORS['bg'])
        fig.subplots_adjust(left=0.18, right=0.97, top=0.88,
                            bottom=0.12, wspace=0.4)

        # ── 2a: Top 20 productos más cotizados (por monto) ────────────────────
        self.cursor.execute('''
            SELECT p.nombre,
                   SUM(cd.cantidad)  AS cant_total,
                   SUM(cd.total)     AS monto_total
            FROM   cotizacion_detalle cd
            JOIN   productos p ON p.id = cd.producto_id
            JOIN   cotizaciones c ON c.id = cd.cotizacion_id
            WHERE  c.estado NOT IN ('Cancelada')
              AND  c.fecha BETWEEN ? AND ?
            GROUP BY p.id
            ORDER BY monto_total DESC
            LIMIT  20
        ''', (f_desde, f_hasta))
        rows = self.cursor.fetchall()

        ax1 = fig.add_subplot(1, 2, 1)
        if rows:
            nombres = [r[0][:22] for r in rows][::-1]
            montos  = [r[2] or 0 for r in rows][::-1]
            y = range(len(nombres))
            bars = ax1.barh(list(y), montos, color=_COLORS['primary'],
                            zorder=3, height=0.65)
            ax1.set_yticks(list(y))
            ax1.set_yticklabels(nombres, fontsize=7)
            ax1.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: _fmt_mxn(x)))
            ax1.tick_params(axis='x', labelsize=7)
            ax1.grid(axis='x', color=_COLORS['grid'], zorder=0)
            for spine in ax1.spines.values():
                spine.set_edgecolor(_COLORS['grid'])
        else:
            ax1.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax1.transAxes, color=_COLORS['muted'])
        ax1.set_title('Top 20 productos más cotizados', fontsize=11,
                      fontweight='bold', color=_COLORS['text'], pad=8)
        ax1.set_facecolor(_COLORS['bg'])

        # ── 2b: Productos bajo stock mínimo ───────────────────────────────────
        self.cursor.execute('''
            SELECT p.nombre, p.stock_actual, p.stock_minimo
            FROM   productos p
            WHERE  p.stock_minimo > 0
              AND  p.stock_actual < p.stock_minimo
            ORDER BY (p.stock_minimo - p.stock_actual) DESC
            LIMIT  15
        ''')
        rows2 = self.cursor.fetchall()

        ax2 = fig.add_subplot(1, 2, 2)
        if rows2:
            nombres2  = [r[0][:22] for r in rows2][::-1]
            actuales  = [r[1] or 0 for r in rows2][::-1]
            minimos   = [r[2] or 0 for r in rows2][::-1]
            y2 = range(len(nombres2))
            ax2.barh(list(y2), minimos, color=_COLORS['grid'],
                     label='Mínimo', zorder=2, height=0.55)
            ax2.barh(list(y2), actuales, color=_COLORS['danger'],
                     label='Actual', zorder=3, height=0.55, alpha=0.9)
            ax2.set_yticks(list(y2))
            ax2.set_yticklabels(nombres2, fontsize=7)
            ax2.tick_params(axis='x', labelsize=7)
            ax2.legend(fontsize=7, framealpha=0.7)
            ax2.grid(axis='x', color=_COLORS['grid'], zorder=0)
            for spine in ax2.spines.values():
                spine.set_edgecolor(_COLORS['grid'])
        else:
            ax2.text(0.5, 0.5, 'Sin productos bajo stock mínimo ✓',
                     ha='center', va='center',
                     transform=ax2.transAxes, color=_COLORS['accent'],
                     fontsize=10)
        ax2.set_title('Productos bajo stock mínimo', fontsize=11,
                      fontweight='bold', color=_COLORS['text'], pad=8)
        ax2.set_facecolor(_COLORS['bg'])

        return fig

    # ── Tab 3: Compras y Costos ────────────────────────────────────────────────

    def _fig_compras(self, f_desde, f_hasta):
        fig = Figure(figsize=(14, 6), dpi=90, facecolor=_COLORS['bg'])
        fig.subplots_adjust(left=0.08, right=0.98, top=0.88,
                            bottom=0.15, wspace=0.38)

        # ── 3a: Compras por mes ───────────────────────────────────────────────
        self.cursor.execute('''
            SELECT strftime('%Y-%m', fecha_compra) AS mes,
                   SUM(total) AS total_compra
            FROM   compras
            WHERE  fecha_compra BETWEEN ? AND ?
            GROUP BY mes
            ORDER BY mes
        ''', (f_desde, f_hasta))
        rows = self.cursor.fetchall()

        ax1 = fig.add_subplot(1, 3, 1)
        if rows:
            meses  = [r[0] for r in rows]
            totals = [r[1] or 0 for r in rows]
            x = range(len(meses))
            ax1.bar(list(x), totals, color=_COLORS['warn'], zorder=3)
            ax1.set_xticks(list(x))
            etqs = [m[5:] + '\n' + m[:4] for m in meses]
            ax1.set_xticklabels(etqs, fontsize=7)
        else:
            ax1.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax1.transAxes, color=_COLORS['muted'])
        _apply_style(ax1, 'Compras por mes', yformat_mxn=True)

        # ── 3b: Top proveedores por monto ─────────────────────────────────────
        self.cursor.execute('''
            SELECT pv.nombre,
                   COUNT(c.id)   AS num_compras,
                   SUM(c.total)  AS total
            FROM   compras c
            JOIN   proveedores pv ON pv.id = c.proveedor_id
            WHERE  c.fecha_compra BETWEEN ? AND ?
            GROUP BY pv.id
            ORDER BY total DESC
            LIMIT  12
        ''', (f_desde, f_hasta))
        rows2 = self.cursor.fetchall()

        ax2 = fig.add_subplot(1, 3, 2)
        if rows2:
            nombres = [r[0][:20] for r in rows2][::-1]
            totals2 = [r[2] or 0 for r in rows2][::-1]
            y = range(len(nombres))
            ax2.barh(list(y), totals2, color=_COLORS['warn'], zorder=3)
            ax2.set_yticks(list(y))
            ax2.set_yticklabels(nombres, fontsize=7)
            ax2.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: _fmt_mxn(x)))
            ax2.tick_params(axis='x', labelsize=7)
            ax2.grid(axis='x', color=_COLORS['grid'], zorder=0)
            for spine in ax2.spines.values():
                spine.set_edgecolor(_COLORS['grid'])
        else:
            ax2.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax2.transAxes, color=_COLORS['muted'])
        ax2.set_title('Top proveedores por monto', fontsize=11,
                      fontweight='bold', color=_COLORS['text'], pad=8)
        ax2.set_facecolor(_COLORS['bg'])

        # ── 3c: Costo real vs cotizado por producto (top 10) ──────────────────
        self.cursor.execute('''
            SELECT p.nombre,
                   SUM(cd.costo_snapshot * cd.cantidad) AS costo_cot,
                   SUM(cpd.costo_unitario * cpd.cantidad) AS costo_real
            FROM   cotizacion_detalle cd
            JOIN   productos p ON p.id = cd.producto_id
            JOIN   cotizaciones c ON c.id = cd.cotizacion_id
            LEFT JOIN compra_detalle_cotizacion cdc ON cdc.cotizacion_id = c.id
            LEFT JOIN compra_detalle cpd ON cpd.id = cdc.compra_detalle_id
                                        AND cpd.producto_id = cd.producto_id
            WHERE  c.fecha BETWEEN ? AND ?
              AND  c.estado NOT IN ('Cancelada')
              AND  cd.costo_snapshot IS NOT NULL
            GROUP BY p.id
            HAVING costo_cot > 0
            ORDER BY costo_cot DESC
            LIMIT 10
        ''', (f_desde, f_hasta))
        rows3 = self.cursor.fetchall()

        ax3 = fig.add_subplot(1, 3, 3)
        if rows3:
            nombres3  = [r[0][:18] for r in rows3][::-1]
            costos_c  = [r[1] or 0 for r in rows3][::-1]
            costos_r  = [r[2] or 0 for r in rows3][::-1]
            y3 = range(len(nombres3))
            w = 0.4
            ax3.barh([i + w/2 for i in y3], costos_c, height=w,
                     color=_COLORS['primary'], label='Cotizado', zorder=3)
            ax3.barh([i - w/2 for i in y3], costos_r, height=w,
                     color=_COLORS['danger'], label='Real', zorder=3, alpha=0.85)
            ax3.set_yticks(list(y3))
            ax3.set_yticklabels(nombres3, fontsize=7)
            ax3.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: _fmt_mxn(x)))
            ax3.tick_params(axis='x', labelsize=7)
            ax3.legend(fontsize=7, framealpha=0.7)
            ax3.grid(axis='x', color=_COLORS['grid'], zorder=0)
            for spine in ax3.spines.values():
                spine.set_edgecolor(_COLORS['grid'])
        else:
            ax3.text(0.5, 0.5, 'Sin datos de costo\ncapturados',
                     ha='center', va='center',
                     transform=ax3.transAxes, color=_COLORS['muted'],
                     fontsize=9)
        ax3.set_title('Costo cotizado vs real (top 10)', fontsize=11,
                      fontweight='bold', color=_COLORS['text'], pad=8)
        ax3.set_facecolor(_COLORS['bg'])

        return fig

    # ── Tab 4: Rentabilidad ────────────────────────────────────────────────────

    def _fig_rentabilidad(self, f_desde, f_hasta):
        fig = Figure(figsize=(14, 6), dpi=90, facecolor=_COLORS['bg'])
        fig.subplots_adjust(left=0.08, right=0.98, top=0.88,
                            bottom=0.15, wspace=0.38)

        # ── 4a: Utilidad acumulada por mes ────────────────────────────────────
        self.cursor.execute('''
            SELECT strftime('%Y-%m', c.fecha)                    AS mes,
                   SUM(c.total)                                  AS ingreso,
                   SUM(COALESCE(cd.costo_snap, 0))               AS costo_est
            FROM   cotizaciones c
            LEFT JOIN (
                SELECT cotizacion_id,
                       SUM(costo_snapshot * cantidad) AS costo_snap
                FROM   cotizacion_detalle
                WHERE  costo_snapshot IS NOT NULL
                GROUP BY cotizacion_id
            ) cd ON cd.cotizacion_id = c.id
            WHERE  c.estado NOT IN ('Cancelada')
              AND  c.fecha BETWEEN ? AND ?
            GROUP BY mes
            ORDER BY mes
        ''', (f_desde, f_hasta))
        rows = self.cursor.fetchall()

        ax1 = fig.add_subplot(1, 3, 1)
        if rows:
            meses    = [r[0] for r in rows]
            ingresos = [r[1] or 0 for r in rows]
            costos   = [r[2] or 0 for r in rows]
            utilidad = [i - c for i, c in zip(ingresos, costos)]
            # Utilidad acumulada
            acum = []
            s = 0
            for u in utilidad:
                s += u
                acum.append(s)
            x = range(len(meses))
            ax1.bar(list(x), utilidad,
                    color=[_COLORS['accent'] if u >= 0 else _COLORS['danger']
                           for u in utilidad],
                    label='Mes', zorder=3, alpha=0.8)
            ax1b = ax1.twinx()
            ax1b.plot(list(x), acum, color=_COLORS['primary'],
                      linewidth=2, marker='o', markersize=5, label='Acum.')
            ax1b.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: _fmt_mxn(x)))
            ax1b.tick_params(labelsize=7, colors=_COLORS['primary'])
            ax1.set_xticks(list(x))
            etqs = [m[5:] + '\n' + m[:4] for m in meses]
            ax1.set_xticklabels(etqs, fontsize=7)
            # Leyenda combinada
            lines1, lbl1 = ax1.get_legend_handles_labels()
            lines2, lbl2 = ax1b.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, lbl1 + lbl2,
                       fontsize=7, framealpha=0.7)
        else:
            ax1.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax1.transAxes, color=_COLORS['muted'])
        _apply_style(ax1, 'Utilidad estimada por mes', yformat_mxn=True)

        # ── 4b: Margen % por tipo de cliente ──────────────────────────────────
        self.cursor.execute('''
            SELECT cl.tipo,
                   AVG(
                     CASE WHEN c.total > 0
                          THEN ((c.total - COALESCE(cd.costo_snap, 0)) / c.total) * 100
                          ELSE NULL
                     END
                   ) AS margen_pct
            FROM   cotizaciones c
            JOIN   clientes cl ON cl.id = c.cliente_id
            LEFT JOIN (
                SELECT cotizacion_id,
                       SUM(costo_snapshot * cantidad) AS costo_snap
                FROM   cotizacion_detalle
                WHERE  costo_snapshot IS NOT NULL
                GROUP BY cotizacion_id
            ) cd ON cd.cotizacion_id = c.id
            WHERE  c.estado NOT IN ('Cancelada')
              AND  c.fecha BETWEEN ? AND ?
            GROUP BY cl.tipo
            ORDER BY margen_pct DESC
        ''', (f_desde, f_hasta))
        rows2 = self.cursor.fetchall()

        ax2 = fig.add_subplot(1, 3, 2)
        if rows2:
            tipos   = [r[0] for r in rows2]
            margenes = [r[1] or 0 for r in rows2]
            colors2 = [_COLORS['accent'] if m >= 30 else
                       (_COLORS['warn'] if m >= 15 else _COLORS['danger'])
                       for m in margenes]
            x2 = range(len(tipos))
            bars = ax2.bar(list(x2), margenes, color=colors2, zorder=3)
            ax2.set_xticks(list(x2))
            ax2.set_xticklabels(tipos, fontsize=8)
            ax2.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: f'{x:.0f}%'))
            # Línea de referencia 30%
            ax2.axhline(30, color=_COLORS['accent'], linestyle='--',
                        linewidth=1, alpha=0.6, label='30%')
            ax2.legend(fontsize=7)
            # Etiquetas en barras
            for bar, m in zip(bars, margenes):
                ax2.text(bar.get_x() + bar.get_width() / 2,
                         bar.get_height() + 0.5,
                         f'{m:.1f}%', ha='center', va='bottom',
                         fontsize=8, color=_COLORS['text'])
        else:
            ax2.text(0.5, 0.5, 'Sin datos de costo\ncapturados',
                     ha='center', va='center',
                     transform=ax2.transAxes, color=_COLORS['muted'],
                     fontsize=9)
        _apply_style(ax2, 'Margen % por tipo de cliente')

        # ── 4c: Top 10 clientes por utilidad estimada ─────────────────────────
        self.cursor.execute('''
            SELECT cl.nombre_comercial,
                   SUM(c.total) AS ingreso,
                   SUM(COALESCE(cd.costo_snap, 0)) AS costo_est
            FROM   cotizaciones c
            JOIN   clientes cl ON cl.id = c.cliente_id
            LEFT JOIN (
                SELECT cotizacion_id,
                       SUM(costo_snapshot * cantidad) AS costo_snap
                FROM   cotizacion_detalle
                WHERE  costo_snapshot IS NOT NULL
                GROUP BY cotizacion_id
            ) cd ON cd.cotizacion_id = c.id
            WHERE  c.estado NOT IN ('Cancelada')
              AND  c.fecha BETWEEN ? AND ?
            GROUP BY cl.id
            ORDER BY (ingreso - costo_est) DESC
            LIMIT 10
        ''', (f_desde, f_hasta))
        rows3 = self.cursor.fetchall()

        ax3 = fig.add_subplot(1, 3, 3)
        if rows3:
            nombres3 = [r[0][:20] for r in rows3][::-1]
            util3    = [(r[1] or 0) - (r[2] or 0) for r in rows3][::-1]
            colors3  = [_COLORS['accent'] if u >= 0 else _COLORS['danger']
                        for u in util3]
            y3 = range(len(nombres3))
            ax3.barh(list(y3), util3, color=colors3, zorder=3)
            ax3.set_yticks(list(y3))
            ax3.set_yticklabels(nombres3, fontsize=7)
            ax3.xaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: _fmt_mxn(x)))
            ax3.tick_params(axis='x', labelsize=7)
            ax3.axvline(0, color=_COLORS['muted'], linewidth=0.8)
            ax3.grid(axis='x', color=_COLORS['grid'], zorder=0)
            for spine in ax3.spines.values():
                spine.set_edgecolor(_COLORS['grid'])
        else:
            ax3.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                     transform=ax3.transAxes, color=_COLORS['muted'])
        ax3.set_title('Top 10 clientes por utilidad estimada', fontsize=11,
                      fontweight='bold', color=_COLORS['text'], pad=8)
        ax3.set_facecolor(_COLORS['bg'])

        return fig
