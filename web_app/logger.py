# -*- coding: utf-8 -*-
"""
web_app/logger.py
Configuracion de logging estructurado para la web app.
Escribe a consola Y a logs/web_app.log con rotacion diaria.
"""

import logging
import logging.handlers
from pathlib import Path

_LOG_DIR  = Path(__file__).parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "web_app.log"

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE   = "%Y-%m-%d %H:%M:%S"


def configurar():
    """Llama una sola vez al arrancar la app (en startup de FastAPI)."""
    _LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Evitar duplicar handlers si se llama varias veces (ej. --reload)
    if root.handlers:
        return

    fmt = logging.Formatter(_FORMAT, datefmt=_DATE)

    # ── Consola ───────────────────────────────────────────────────────────
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # ── Archivo con rotacion diaria (7 dias de historial) ─────────────────
    fh = logging.handlers.TimedRotatingFileHandler(
        _LOG_FILE, when="midnight", backupCount=7, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.getLogger("uvicorn.access").propagate = False  # evitar duplicados


def get(name: str) -> logging.Logger:
    return logging.getLogger(name)
