# -*- coding: utf-8 -*-
"""
app_config.py (web)
Subconjunto mínimo de app_config para la web app.
Solo expone BASE_DIR y PDF_CONFIG — sin dependencias de escritorio.
"""

import json
import os
from pathlib import Path

BASE_DIR    = str(Path(__file__).parent)
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

# ── PDF_CONFIG: valores por defecto ──────────────────────────────────────────
PDF_CONFIG: dict = {
    'logo_path':      'assets/logo_clf.jpg',
    'vigencia':       '30 DÍAS',
    'lugar_entrega':  'MÉRIDA',
    'tiempo_entrega': '15 DÍAS, A PARTIR DEL ANTICIPO DEL 60% Y SALDO CONTRAENTREGA',
    'moneda':         'TODOS LOS PRECIOS DE ESTA COTIZACIÓN SON EN MONEDA NACIONAL',
    'cambios':        'PRECIO SUJETO A CAMBIO SIN PREVIO AVISO',
}

# Cargar preferencias desde config.json si existen
try:
    with open(CONFIG_PATH, encoding='utf-8') as _f:
        _cfg = json.load(_f)
    _prefs_all = _cfg.get('preferencias', {})
    if _prefs_all:
        _first = next(iter(_prefs_all.values()), {})
        _pdf = _first.get('pdf', {})
        if _pdf:
            PDF_CONFIG.update(_pdf)
except Exception:
    pass
