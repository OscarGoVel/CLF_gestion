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

# Permite importar db_connection, app_config, etc. desde el directorio raiz
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from web_app.routers import auth as auth_router
from web_app.dependencies import get_usuario_actual
from web_app import audit

# ── Rate limiter global ───────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CLF Gestion Web",
    docs_url=None,
    redoc_url=None,
)

app.state.limiter = limiter

async def _rate_limit_html_handler(request: Request, exc: RateLimitExceeded):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Demasiados intentos. Espera un momento e intenta de nuevo."},
        status_code=429,
    )

app.add_exception_handler(RateLimitExceeded, _rate_limit_html_handler)

# ── Templates ─────────────────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR    = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ── Middleware: security headers ──────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"]       = "1; mode=block"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]     = "geolocation=(), microphone=(), camera=()"
        return response

app.add_middleware(SecurityHeadersMiddleware)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)


# ── Manejadores de error ──────────────────────────────────────────────────────
@app.exception_handler(401)
async def handler_401(request: Request, exc: HTTPException):
    return RedirectResponse("/?next=" + str(request.url.path))


@app.exception_handler(403)
async def handler_403(request: Request, exc: HTTPException):
    user = get_usuario_actual(request)
    audit.registrar(
        audit.ACCESO_DENEGADO,
        username=user.get("username") if user else None,
        detalle=str(request.url.path),
        ip=request.client.host if request.client else None,
    )
    return templates.TemplateResponse(
        request=request,
        name="403.html",
        context={"user": user, "path": request.url.path},
        status_code=403,
    )


@app.exception_handler(404)
async def handler_404(request: Request, exc: HTTPException):
    user = get_usuario_actual(request)
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        context={"user": user, "path": request.url.path},
        status_code=404,
    )


@app.exception_handler(500)
async def handler_500(request: Request, exc: Exception):
    user = get_usuario_actual(request)
    return templates.TemplateResponse(
        request=request,
        name="500.html",
        context={"user": user},
        status_code=500,
    )


# ── Startup: inicializar tabla de auditoria ───────────────────────────────────
@app.on_event("startup")
async def startup():
    audit._asegurar_tabla()


# ── Rutas principales ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_usuario_actual(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user},
    )


# ── Ruta de ejemplo con RBAC ──────────────────────────────────────────────────
@app.get("/admin/audit", response_class=HTMLResponse)
async def admin_audit(request: Request):
    """Solo Administrador puede ver el log de auditoria."""
    from fastapi import Depends
    from web_app.rbac import require_rol
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403)
    eventos = audit.obtener_ultimos(100)
    return templates.TemplateResponse(
        request=request,
        name="audit.html",
        context={"user": user, "eventos": eventos},
    )
