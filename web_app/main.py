#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
web_app/main.py
Punto de entrada de la aplicacion web CLF Gestion.

Arrancar con:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    uvicorn web_app.main:app --reload --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path

# Permite importar db_connection, app_config, sesion, etc. desde el directorio raiz
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web_app.routers import auth as auth_router
from web_app.dependencies import get_usuario_actual

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CLF Gestion Web",
    docs_url=None,   # deshabilitar Swagger en produccion
    redoc_url=None,
)

# ── Templates y archivos estaticos ───────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR    = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)


# ── Rutas principales ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirige al dashboard si hay sesion activa, si no muestra login."""
    user = get_usuario_actual(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard principal — requiere sesion valida."""
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"user": user})
