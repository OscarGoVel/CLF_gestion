# -*- coding: utf-8 -*-
"""
core/constants.py
Constantes de dominio compartidas entre escritorio y web.
"""

# ── Estados de cotización ─────────────────────────────────────────────────────

ESTADOS_COTIZACION = [
    "Pendiente",
    "Programada",
    "Parcialmente Entregada",
    "Entregada",
    "Facturada",
    "Pagada",
    "Cancelada",
]

# Estados que representan una venta confirmada (cliente autorizó el pedido)
ESTADOS_VENTA_CONFIRMADA = frozenset([
    "Programada",
    "Parcialmente Entregada",
    "Entregada",
    "Facturada",
    "Pagada",
])

# Estados con saldo pendiente de cobro (confirmados pero no pagados completamente)
ESTADOS_PENDIENTE_COBRO = frozenset([
    "Programada",
    "Parcialmente Entregada",
    "Entregada",
    "Facturada",
])

# Clases Tailwind para badges en la web
ESTADO_COLOR_CSS: dict[str, tuple[str, str]] = {
    "Pendiente":              ("bg-amber-100",   "text-amber-800"),
    "Programada":             ("bg-purple-100",  "text-purple-800"),
    "Parcialmente Entregada": ("bg-violet-100",  "text-violet-800"),
    "Entregada":              ("bg-green-100",   "text-green-800"),
    "Facturada":              ("bg-cyan-100",    "text-cyan-800"),
    "Pagada":                 ("bg-blue-100",    "text-blue-800"),
    "Cancelada":              ("bg-red-100",     "text-red-700"),
}

# Colores hex para gráficas (Chart.js / analisis)
ESTADO_COLOR_HEX: dict[str, str] = {
    "Pendiente":              "#f59e0b",
    "Programada":             "#a855f7",
    "Parcialmente Entregada": "#8b5cf6",
    "Entregada":              "#22c55e",
    "Facturada":              "#06b6d4",
    "Pagada":                 "#3b82f6",
    "Cancelada":              "#ef4444",
}

# Colores tkinter para la app de escritorio
ESTADO_COLOR_TK: dict[str, str] = {
    "Pendiente":              "#f59e0b",
    "Programada":             "#a855f7",
    "Parcialmente Entregada": "#8b5cf6",
    "Entregada":              "#22c55e",
    "Facturada":              "#06b6d4",
    "Pagada":                 "#3b82f6",
    "Cancelada":              "#ef4444",
}

# ── Movimientos de stock ──────────────────────────────────────────────────────

MOTIVOS_SALIDA = [
    "Merma / Daño",
    "Uso interno",
    "Devolución a proveedor",
    "Ajuste de inventario",
    "Muestra / Demo",
    "Pérdida",
    "Otro",
]

# ── Formato de folio ──────────────────────────────────────────────────────────

FOLIO_PREFIJO = "COT"


def formato_folio(año: int, consecutivo: int) -> str:
    """Retorna el folio formateado: COT-YYYY-NNNN."""
    return f"{FOLIO_PREFIJO}-{año}-{consecutivo:04d}"
