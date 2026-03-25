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
import time
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

from contextlib import asynccontextmanager
from web_app.routers import auth as auth_router
from web_app.routers import cotizaciones as cotizaciones_router
from web_app.routers import catalogos as catalogos_router
from web_app.routers import facturas as facturas_router
from web_app.dependencies import get_usuario_actual
from web_app import audit, logger
from web_app.database import pool_empresa, pool_usuarios
from web_app.metrics import registry as metrics

# ── Rate limiter global ───────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    logger.configurar()
    _log = logger.get("clf.startup")
    _log.info("Iniciando CLF Gestion Web...")
    audit._asegurar_tabla()
    try:
        pool_usuarios._init()
        pool_empresa._init()
        _log.info("Pools de conexion PostgreSQL listos")
    except Exception as e:
        _log.error(f"Error iniciando pool: {e}")
    yield
    # shutdown
    pool_empresa.cerrar()
    pool_usuarios.cerrar()
    logger.get("clf.startup").info("Servidor detenido. Pools cerrados.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CLF Gestion Web",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
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
_log_requests = logger.get("clf.request")
_SLOW_MS = 2000   # log si la peticion tarda mas de 2 segundos


class MonitorMiddleware(BaseHTTPMiddleware):
    """Middleware unico: metricas + headers de seguridad + log de peticiones lentas."""

    async def dispatch(self, request: Request, call_next):
        t0 = metrics.request_inicio()   # tambien llama a time.monotonic() internamente
        try:
            response = await call_next(request)
        except Exception as exc:
            metrics.registrar_excepcion(request.method, request.url.path, str(exc))
            raise

        elapsed_ms = (time.monotonic() - t0) * 1000
        metrics.request_fin(t0, request.method, request.url.path, response.status_code)

        if elapsed_ms > _SLOW_MS:
            _log_requests.warning(
                f"SLOW {request.method} {request.url.path} "
                f"-> {response.status_code} en {elapsed_ms:.0f}ms"
            )

        response.headers["X-Frame-Options"]        = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"]       = "1; mode=block"
        response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]     = "geolocation=(), microphone=(), camera=()"
        response.headers["X-Response-Time"]        = f"{elapsed_ms:.1f}ms"
        return response


app.add_middleware(MonitorMiddleware)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(cotizaciones_router.router)
app.include_router(catalogos_router.router)
app.include_router(facturas_router.router)


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

    kpis = {}
    try:
        with pool_empresa.conexion() as (_, cur):
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE estado IN ('Pendiente','Programada')) AS activas,
                    COUNT(*) FILTER (WHERE estado = 'Entregada'
                                    AND (monto_pagado IS NULL OR monto_pagado < total)) AS por_cobrar,
                    COUNT(*) FILTER (WHERE estado NOT IN ('Cancelada','Pagada')
                                    AND fecha_entrega < CURRENT_DATE) AS vencidas,
                    COALESCE(SUM(total) FILTER (
                        WHERE DATE_TRUNC('month', fecha) = DATE_TRUNC('month', CURRENT_DATE)
                        AND estado != 'Cancelada'), 0) AS ventas_mes
                FROM cotizaciones
            """)
            row = cur.fetchone()
            kpis = {
                "activas":    row[0],
                "por_cobrar": row[1],
                "vencidas":   row[2],
                "ventas_mes": float(row[3]),
            }
    except Exception:
        kpis = {"activas": "—", "por_cobrar": "—", "vencidas": "—", "ventas_mes": "—"}

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user, "kpis": kpis},
    )


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """
    Estado del sistema. Util para monitoreo y para verificar que el servidor responde.
    No requiere autenticacion (para que los scripts de monitoreo puedan usarlo).
    """
    import time
    from fastapi.responses import JSONResponse
    from web_app.config import settings

    db_ok = False
    db_msg = ""
    try:
        with pool_usuarios.conexion() as (_, cursor):
            cursor.execute("SELECT 1")
            db_ok = True
    except Exception as e:
        db_msg = str(e)

    estado = {
        "estado":      "ok" if db_ok else "degradado",
        "version":     "1.0.0",
        "entorno":     settings.ENVIRONMENT,
        "ssl":         settings.ssl_disponible,
        "db":          "ok" if db_ok else f"error: {db_msg}",
        "pool_usuarios": pool_usuarios.estado(),
        "pool_empresa":  pool_empresa.estado(),
        "ts":          time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return JSONResponse(estado, status_code=200 if db_ok else 503)


# ── Metricas (solo Administrador) ────────────────────────────────────────────
@app.get("/admin/metrics", response_class=HTMLResponse)
async def admin_metrics(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")
    if user.get("rol") != "Administrador":
        raise HTTPException(status_code=403)
    snap = metrics.snapshot()
    snap["pool_usuarios"] = pool_usuarios.estado()
    snap["pool_empresa"]  = pool_empresa.estado()
    return templates.TemplateResponse(
        request=request,
        name="metrics.html",
        context={"user": user, "m": snap},
    )


# ── Audit log (solo Administrador) ───────────────────────────────────────────
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
