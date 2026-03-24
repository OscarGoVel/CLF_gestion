# -*- coding: utf-8 -*-
"""
app_config.py
Configuración centralizada de la aplicación:
  - Porcentajes de utilidad por tipo de cliente
  - Paleta de colores principal
  - Rutas base de almacenamiento
  - Carga/guardado de preferencias por empresa (config.json)
"""

import os
import json
import copy
import sqlite3

# Directorio raíz del proyecto (mismo nivel que este archivo)
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
USERS_DB    = os.path.join(BASE_DIR, 'app_usuarios.db')

# Carpetas de datos
FACTURAS_XML_DIR = os.path.join(BASE_DIR, 'facturas_xml')
DOCUMENTOS_DIR   = os.path.join(BASE_DIR, 'documentos')

# ── Preferencias por defecto ───────────────────────────────────────────────────
PREFS_DEFAULT = {
    'comercial': {
        'iva_default': 16,
        'utilidad': {'Gobierno': 40, 'Hotel': 35, 'Empresa': 35},
    },
    'pdf': {
        'logo_path':      'logo_clf.jpg',
        'vigencia':       '30 DÍAS',
        'lugar_entrega':  'MÉRIDA',
        'tiempo_entrega': '15 DÍAS, A PARTIR DEL ANTICIPO DEL 60% Y SALDO CONTRAENTREGA',
        'moneda':         'TODOS LOS PRECIOS DE ESTA COTIZACIÓN SON EN MONEDA NACIONAL',
        'cambios':        'PRECIO SUJETO A CAMBIO SIN PREVIO AVISO',
    },
    'respaldo': {
        'carpeta': '',
    },
}

# ── Dicts mutables — se actualizan in-place al cargar/guardar prefs ────────────
# Todos los módulos que ya importaron estas referencias verán los cambios.

UTILIDAD: dict = {'Gobierno': 40, 'Hotel': 35, 'Empresa': 35}

PDF_CONFIG: dict = {
    'logo_path':      'logo_clf.jpg',
    'vigencia':       '30 DÍAS',
    'lugar_entrega':  'MÉRIDA',
    'tiempo_entrega': '15 DÍAS, A PARTIR DEL ANTICIPO DEL 60% Y SALDO CONTRAENTREGA',
    'moneda':         'TODOS LOS PRECIOS DE ESTA COTIZACIÓN SON EN MONEDA NACIONAL',
    'cambios':        'PRECIO SUJETO A CAMBIO SIN PREVIO AVISO',
}

IVA_DEFAULT: list = [16]   # lista para poder mutar el valor in-place


# ── Funciones de carga/guardado ────────────────────────────────────────────────

def cargar_preferencias(empresa_id: str) -> dict:
    """Lee las preferencias de una empresa desde config.json.
    Actualiza UTILIDAD, PDF_CONFIG e IVA_DEFAULT in-place.
    Devuelve el dict de preferencias (copia profunda de los valores cargados).
    """
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    prefs_guardadas = cfg.get('preferencias', {}).get(empresa_id, {})
    # Fusionar sobre los defaults para garantizar que existan todas las claves
    prefs = copy.deepcopy(PREFS_DEFAULT)
    _merge(prefs, prefs_guardadas)

    # Actualizar dicts mutables in-place
    UTILIDAD.clear()
    UTILIDAD.update(prefs['comercial']['utilidad'])

    PDF_CONFIG.clear()
    PDF_CONFIG.update(prefs['pdf'])

    IVA_DEFAULT[0] = int(prefs['comercial'].get('iva_default', 16))

    return prefs


def guardar_preferencias(empresa_id: str, prefs: dict) -> None:
    """Guarda las preferencias de una empresa en config.json
    y actualiza UTILIDAD, PDF_CONFIG e IVA_DEFAULT in-place.
    """
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}

    if 'preferencias' not in cfg:
        cfg['preferencias'] = {}
    cfg['preferencias'][empresa_id] = copy.deepcopy(prefs)

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    # Sincronizar dicts mutables
    UTILIDAD.clear()
    UTILIDAD.update(prefs['comercial']['utilidad'])

    PDF_CONFIG.clear()
    PDF_CONFIG.update(prefs['pdf'])

    IVA_DEFAULT[0] = int(prefs['comercial'].get('iva_default', 16))


def guardar_empresa(empresa_id: str, datos: dict) -> None:
    """Actualiza los datos de la empresa en config.json (nombre, email, etc.)."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {'empresas': [], 'ultima_empresa': ''}

    for emp in cfg.get('empresas', []):
        if emp.get('id') == empresa_id:
            emp.update(datos)
            break

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _merge(base: dict, override: dict) -> None:
    """Fusión recursiva: override sobreescribe base sin eliminar claves ausentes."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _merge(base[k], v)
        else:
            base[k] = v


# ── Preferencias por usuario (rutas de PDFs) ──────────────────────────────────

# Rutas por defecto — se usan si el usuario no configuró las suyas
RUTAS_PDF_DEFAULT = {
    'ruta_cotizaciones': r'C:\Users\oscar\OneDrive\Documentos\CLF Sistema\cotizaciones',
    'ruta_remisiones':   r'C:\Users\oscar\OneDrive\Documentos\Gestion CLF\notas de remision',
}


def cargar_prefs_usuario(usuario_id: int) -> dict:
    """Lee las rutas PDF configuradas por el usuario desde la BD de usuarios.
    Devuelve un dict con al menos las claves de RUTAS_PDF_DEFAULT.
    """
    import db_connection
    prefs = dict(RUTAS_PDF_DEFAULT)
    if not usuario_id:
        return prefs
    try:
        conn, cursor = db_connection.conectar_usuarios()
        cursor.execute(
            'SELECT clave, valor FROM preferencias_usuario WHERE usuario_id = ?',
            (usuario_id,)
        )
        for clave, valor in cursor.fetchall():
            prefs[clave] = valor
        conn.close()
    except Exception:
        pass
    return prefs


def guardar_prefs_usuario(usuario_id: int, prefs: dict) -> None:
    """Guarda las rutas PDF del usuario en la BD de usuarios."""
    import db_connection
    conn, cursor = db_connection.conectar_usuarios()
    for clave, valor in prefs.items():
        cursor.execute('''
            INSERT INTO preferencias_usuario (usuario_id, clave, valor)
            VALUES (?, ?, ?)
            ON CONFLICT(usuario_id, clave) DO UPDATE SET valor = excluded.valor
        ''', (usuario_id, clave, str(valor)))
    conn.commit()
    conn.close()


# ── Paleta de colores principal (coincide con self.C en SistemaGestion) ────────
COLORES = {
    # Navegación
    'nav_bg':          '#1e2d45',
    'nav_active':      '#eceff4',
    'nav_hover':       '#2b3a55',
    'nav_text':        '#94a3b8',
    'nav_active_text': '#1e2d45',
    # Layout principal
    'kpi_bg':          '#f7f9fc',
    'kpi_border':      '#d0d7e4',
    'toolbar_bg':      '#d8dde8',
    'toolbar_border':  '#c5ccd8',
    'content_bg':      '#eceff4',
    'card_bg':         'white',
    # Acento / acciones
    'accent':          '#0f7b5e',
    'accent2':         '#1a4b8c',
    'accent3':         '#1e3a5f',
    'accent_dark':     '#065f46',
    'purple':          '#7c3aed',
    'success':         '#27ae60',
    'success2':        '#16a34a',
    'success_alt':     '#16a085',
    'warn':            '#d97706',
    'danger':          '#c0392b',
    'danger2':         '#dc2626',
    'dark2':           '#2c3e50',
    # Texto
    'text_dark':       '#1e2d45',
    'text_secondary':  '#374151',
    'text_muted':      '#6b7e99',
    'text_muted2':     '#6b7280',
    'text_faint':      '#9ca3af',
    # Fondos de UI
    'modal_bg':        '#f1f5f9',
    'form_bg':         '#f8fafc',
    'border':          '#e2e8f0',
    'bg_success':      '#f0fdf4',
    'bg_warn':         '#fef3c7',
}
