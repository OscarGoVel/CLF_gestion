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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from contextlib import asynccontextmanager
from web_app.routers import auth as auth_router
from web_app.routers import cotizaciones as cotizaciones_router
from web_app.routers import catalogos as catalogos_router
from web_app.routers import facturas as facturas_router
from web_app.routers import stock as stock_router
from web_app.routers import analisis as analisis_router
from web_app.routers import admin as admin_router
from web_app.routers import preinventario as preinventario_router
from web_app.routers import estudio_mercado as estudio_mercado_router
from web_app.routers import compras as compras_router
from web_app.routers import estado_cuenta as estado_cuenta_router
from web_app.routers import herramientas as herramientas_router
from web_app.routers import api_dashboard as api_dashboard_router
from web_app.routers import api_cotizaciones as api_cotizaciones_router
from web_app.routers import api_catalogos as api_catalogos_router
from web_app.routers import api_compras as api_compras_router
from web_app.routers import api_stock as api_stock_router
from web_app.routers import api_facturas as api_facturas_router
from web_app.routers import api_ajustes as api_ajustes_router
from web_app.routers import api_analisis as api_analisis_router
from web_app.routers import api_estado_cuenta as api_estado_cuenta_router
from web_app.routers import api_preinventario as api_preinventario_router
from web_app.routers import api_costos_fijos as api_costos_fijos_router
from web_app.routers import api_estudio_mercado as api_estudio_mercado_router
from web_app.routers import api_crm as api_crm_router
from web_app.routers import api_devoluciones as api_devoluciones_router
from web_app.routers import api_cuentas_pagar as api_cuentas_pagar_router
from web_app.dependencies import get_usuario_actual
from web_app import audit, logger
from web_app.database import pool_empresa, pool_usuarios, get_pool_empresa, get_empresas, cerrar_todos_pools_empresa
from web_app.metrics import registry as metrics
from web_app.config import settings

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
        _log.info("Pools de conexion PostgreSQL listos")
    except Exception as e:
        _log.error(f"Error iniciando pool: {e}")

    # Migraciones incrementales por empresa
    _MIGRACIONES = [
        "ALTER TABLE producto_precio_historial ADD COLUMN IF NOT EXISTS proveedor_id INTEGER REFERENCES proveedores(id)",
        "ALTER TABLE clientes ADD COLUMN IF NOT EXISTS activo BOOLEAN DEFAULT TRUE",
        "ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS utilidad_pct NUMERIC(6,2) DEFAULT 0",
        # Tabla de asignación de costos de compra a cotizaciones (módulo compras web)
        """
        CREATE TABLE IF NOT EXISTS compra_detalle_cotizacion (
            id                SERIAL PRIMARY KEY,
            compra_detalle_id INTEGER NOT NULL REFERENCES compra_detalle(id),
            cotizacion_id     INTEGER REFERENCES cotizaciones(id),
            cantidad          NUMERIC(14,4) NOT NULL,
            notas             TEXT,
            fecha_registro    TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        # Compradores: múltiples contactos de compra por cliente
        """
        CREATE TABLE IF NOT EXISTS compradores (
            id             SERIAL PRIMARY KEY,
            cliente_id     INTEGER NOT NULL REFERENCES clientes(id),
            nombre         TEXT NOT NULL,
            cargo          TEXT,
            telefono       TEXT,
            email          TEXT,
            activo         BOOLEAN DEFAULT TRUE,
            fecha_registro TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS comprador_id INTEGER REFERENCES compradores(id)",
        # Línea libre en cotización (sin producto del catálogo)
        "ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS descripcion_libre TEXT",
        "ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS pendiente_catalogo BOOLEAN DEFAULT FALSE",
        "ALTER TABLE cotizacion_detalle ALTER COLUMN producto_id DROP NOT NULL",
        # Costo promedio ponderado por producto (se actualiza en cada compra)
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS costo_promedio NUMERIC(14,4) DEFAULT 0",
        # Snapshot del costo al momento de entregar la cotización
        "ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS costo_entrega NUMERIC(14,4)",
        "ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS costo_entrega_tipo TEXT",
        # Estudio de mercado: margen configurable y vínculo a cotización de origen
        "ALTER TABLE estudios_mercado ADD COLUMN IF NOT EXISTS margen_pct NUMERIC(5,4) DEFAULT 0.35",
        "ALTER TABLE estudios_mercado ADD COLUMN IF NOT EXISTS cotizacion_id INTEGER REFERENCES cotizaciones(id)",
        # Precio de venta sugerido en catálogo (calculado desde estudio de mercado)
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_venta NUMERIC(14,4)",
        # Log de aplicaciones de precios del estudio a cotizaciones
        """
        CREATE TABLE IF NOT EXISTS estudio_aplicaciones (
            id             SERIAL PRIMARY KEY,
            estudio_id     INTEGER NOT NULL REFERENCES estudios_mercado(id) ON DELETE CASCADE,
            cotizacion_id  INTEGER NOT NULL REFERENCES cotizaciones(id),
            aplicado_por   INTEGER REFERENCES usuarios(id),
            forzado        BOOLEAN DEFAULT FALSE,
            estado_cot     TEXT,
            fecha          TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        # Costos fijos mensuales (módulo nuevo)
        """
        CREATE TABLE IF NOT EXISTS costos_fijos (
            id           SERIAL PRIMARY KEY,
            periodo      TEXT NOT NULL,
            categoria    TEXT NOT NULL,
            descripcion  TEXT NOT NULL,
            monto        NUMERIC(14,2) NOT NULL,
            created_by   TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        # Fase 4: margen por línea de cotización (costo_snapshot ya prioriza costo_promedio)
        "ALTER TABLE cotizacion_detalle ADD COLUMN IF NOT EXISTS margen_pct NUMERIC(8,4)",
        # Fase 5: resultado de cotización y motivo de pérdida (tasa de conversión)
        "ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS resultado VARCHAR(20)",
        "ALTER TABLE cotizaciones ADD COLUMN IF NOT EXISTS motivo_perdida VARCHAR(50)",
        # Fase 5: alerta de precio de venta desactualizado por aumento de costo de compra
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_desactualizado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS precio_venta_fecha TIMESTAMPTZ",
        # Fase 10: tabla de pagos (historial de cobros por cotización)
        """
        CREATE TABLE IF NOT EXISTS pagos (
            id              SERIAL PRIMARY KEY,
            cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id),
            monto           NUMERIC(14,2) NOT NULL,
            fecha_pago      DATE NOT NULL,
            metodo          TEXT,
            referencia      TEXT,
            registrado_por  INTEGER REFERENCES usuarios(id),
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_pagos_cotizacion ON pagos(cotizacion_id)",
        # Fase 10: cancelación de facturas CFDI
        "ALTER TABLE facturas ADD COLUMN IF NOT EXISTS cancelada BOOLEAN DEFAULT FALSE",
        "ALTER TABLE facturas ADD COLUMN IF NOT EXISTS motivo_cancelacion TEXT",
        # Fase 11: recepción física de compras
        "ALTER TABLE compras ADD COLUMN IF NOT EXISTS estado TEXT DEFAULT 'Creada'",
        "ALTER TABLE compra_detalle ADD COLUMN IF NOT EXISTS cantidad_recibida NUMERIC(14,4) DEFAULT 0",
        # Fase 11: devoluciones de cliente
        """
        CREATE TABLE IF NOT EXISTS devoluciones (
            id              SERIAL PRIMARY KEY,
            folio           TEXT NOT NULL,
            cotizacion_id   INTEGER REFERENCES cotizaciones(id),
            cliente_id      INTEGER REFERENCES clientes(id),
            fecha           DATE NOT NULL,
            motivo          TEXT,
            estado          TEXT DEFAULT 'Abierta',
            total           NUMERIC(14,2) DEFAULT 0,
            notas           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS devolucion_detalle (
            id              SERIAL PRIMARY KEY,
            devolucion_id   INTEGER NOT NULL REFERENCES devoluciones(id) ON DELETE CASCADE,
            producto_id     INTEGER NOT NULL REFERENCES productos(id),
            cantidad        NUMERIC(14,4) NOT NULL,
            precio_unitario NUMERIC(14,4) NOT NULL,
            total           NUMERIC(14,2) NOT NULL,
            retorna_stock   BOOLEAN DEFAULT TRUE
        )
        """,
        # Fase 11: lotes y vencimientos
        "ALTER TABLE productos ADD COLUMN IF NOT EXISTS maneja_lotes BOOLEAN DEFAULT FALSE",
        """
        CREATE TABLE IF NOT EXISTS lotes (
            id                SERIAL PRIMARY KEY,
            producto_id       INTEGER NOT NULL REFERENCES productos(id),
            numero_lote       TEXT NOT NULL,
            fecha_vencimiento DATE,
            cantidad          NUMERIC(14,4) NOT NULL DEFAULT 0,
            fecha_entrada     DATE,
            notas             TEXT,
            created_at        TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        # Fase 11: carta porte / traslados
        """
        CREATE TABLE IF NOT EXISTS traslados (
            id              SERIAL PRIMARY KEY,
            cotizacion_id   INTEGER NOT NULL REFERENCES cotizaciones(id),
            origen          TEXT,
            destino         TEXT,
            transportista   TEXT,
            placas          TEXT,
            fecha_traslado  DATE,
            notas           TEXT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        # Fase 12-B: campo origen en inscripciones de secuencia (para rastrear trigger automático)
        "ALTER TABLE crm_secuencia_inscripciones ADD COLUMN IF NOT EXISTS origen TEXT",
        # Fase 13-CRM: pipeline comercial (prospectos / kanban)
        """
        CREATE TABLE IF NOT EXISTS prospectos (
            id                     SERIAL PRIMARY KEY,
            nombre                 TEXT NOT NULL,
            cliente_id             INTEGER REFERENCES clientes(id),
            contacto_nombre        TEXT,
            contacto_email         TEXT,
            contacto_tel           TEXT,
            etapa                  TEXT NOT NULL DEFAULT 'nuevo',
            valor_estimado         NUMERIC(14,2),
            probabilidad           INTEGER DEFAULT 0,
            responsable_id         INTEGER REFERENCES usuarios(id),
            notas                  TEXT,
            fecha_estimada_cierre  DATE,
            motivo_perdida         TEXT,
            created_at             TIMESTAMPTZ DEFAULT NOW(),
            updated_at             TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_prospectos_etapa ON prospectos(etapa)",
        # Fase 10: cuentas por pagar a proveedores
        """
        CREATE TABLE IF NOT EXISTS cuentas_por_pagar (
            id                SERIAL PRIMARY KEY,
            compra_id         INTEGER REFERENCES compras(id),
            proveedor_id      INTEGER NOT NULL REFERENCES proveedores(id),
            monto_total       NUMERIC(14,2) NOT NULL,
            monto_pagado      NUMERIC(14,2) DEFAULT 0,
            fecha_vencimiento DATE,
            estado            TEXT DEFAULT 'Pendiente',
            referencia_pago   TEXT,
            notas             TEXT,
            created_at        TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_cxp_proveedor ON cuentas_por_pagar(proveedor_id)",
        "CREATE INDEX IF NOT EXISTS idx_cxp_estado ON cuentas_por_pagar(estado)",
        # Fase 12-D: atribuciones de campañas CRM (ROI)
        """
        CREATE TABLE IF NOT EXISTS crm_campana_atribuciones (
            id               SERIAL PRIMARY KEY,
            campana_id       INTEGER NOT NULL REFERENCES crm_campanas(id) ON DELETE CASCADE,
            cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
            cotizacion_id    INTEGER NOT NULL REFERENCES cotizaciones(id),
            monto            NUMERIC(14,2) NOT NULL,
            dias_desde_envio INTEGER,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(campana_id, cotizacion_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_crm_attr_campana ON crm_campana_atribuciones(campana_id)",
    ]
    for emp in get_empresas():
        db = emp.get("pg_database") or emp.get("empresa_db") or emp.get("db")
        if not db:
            continue
        for sql in _MIGRACIONES:
            try:
                with get_pool_empresa(db).conexion() as (_, cur):
                    cur.execute(sql)
            except Exception as e:
                _log.warning(f"Migracion en {db}: {e}")
    # Migración global: jwt_blacklist (en clf_usuarios)
    try:
        with pool_usuarios.conexion() as (_, cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jwt_blacklist (
                    id         SERIAL PRIMARY KEY,
                    jti        TEXT NOT NULL UNIQUE,
                    exp        TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jbl_jti ON jwt_blacklist(jti)")
    except Exception as e:
        _log.warning(f"Migración jwt_blacklist: {e}")

    # Scheduler CRM (solo si APScheduler instalado y módulo disponible)
    _crm_scheduler = None
    try:
        import importlib
        if importlib.util.find_spec("apscheduler"):
            from core.crm.scheduler import iniciar as crm_iniciar
            _crm_scheduler = crm_iniciar(get_pool_empresa, get_empresas)
    except Exception as e:
        _log.warning(f"CRM scheduler no iniciado: {e}")

    yield
    # shutdown
    if _crm_scheduler:
        try:
            from core.crm.scheduler import detener as crm_detener
            crm_detener()
        except Exception:
            pass
    cerrar_todos_pools_empresa()
    pool_usuarios.cerrar()
    logger.get("clf.startup").info("Servidor detenido. Pools cerrados.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CLF Gestion Web",
    docs_url=None if settings.es_produccion else "/docs",
    redoc_url=None if settings.es_produccion else "/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter

async def _rate_limit_html_handler(request: Request, exc: RateLimitExceeded):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": "Demasiados intentos. Espera un momento e intenta de nuevo.",
            "empresas": get_empresas(),
        },
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
        response.headers["Permissions-Policy"]     = "geolocation=(), microphone=(), camera=(self)"
        response.headers["X-Response-Time"]        = f"{elapsed_ms:.1f}ms"
        return response


app.add_middleware(MonitorMiddleware)

# CORS — permite peticiones desde Firebase Hosting y desarrollo local
_CORS_ORIGINS = settings.cors_origins if hasattr(settings, "cors_origins") else [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
    "https://clf-gestion.web.app",
    "https://clf-gestion.firebaseapp.com",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(cotizaciones_router.router)
app.include_router(catalogos_router.router)
app.include_router(facturas_router.router)
app.include_router(stock_router.router)
app.include_router(analisis_router.router)
app.include_router(admin_router.router)
app.include_router(preinventario_router.router)
app.include_router(estudio_mercado_router.router)
app.include_router(compras_router.router)
app.include_router(estado_cuenta_router.router)
app.include_router(herramientas_router.router)
app.include_router(api_dashboard_router.router)
app.include_router(api_cotizaciones_router.router)
app.include_router(api_catalogos_router.router)
app.include_router(api_compras_router.router)
app.include_router(api_stock_router.router)
app.include_router(api_facturas_router.router)
app.include_router(api_ajustes_router.router)
app.include_router(api_analisis_router.router)
app.include_router(api_estado_cuenta_router.router)
app.include_router(api_preinventario_router.router)
app.include_router(api_costos_fijos_router.router)
app.include_router(api_estudio_mercado_router.router)
app.include_router(api_crm_router.router)
app.include_router(api_devoluciones_router.router)
app.include_router(api_cuentas_pagar_router.router)


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
    import traceback
    _log = logger.get("clf.error")
    _log.error(f"500 {request.method} {request.url.path} — {exc!r}\n{traceback.format_exc()}")
    user = get_usuario_actual(request)
    return templates.TemplateResponse(
        request=request,
        name="500.html",
        context={"user": user},
        status_code=500,
    )




# ── PWA ───────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "CLF Gestión"}


@app.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "name":             "CLF Gestión",
        "short_name":       "CLF",
        "description":      "Sistema de gestión comercial CLF",
        "start_url":        "/dashboard",
        "display":          "standalone",
        "background_color": "#141f30",
        "theme_color":      "#0f7b5e",
        "orientation":      "portrait-primary",
        "icons": [
            {
                "src":   "/static/logo_clf.jpg",
                "sizes": "any",
                "type":  "image/jpeg",
                "purpose": "any maskable",
            }
        ],
        "screenshots": [],
    })


_SW_JS = """
const CACHE_NAME = 'clf-v1';
const STATIC_URLS = [
    'https://cdn.tailwindcss.com',
    'https://unpkg.com/htmx.org@1.9.12',
];

self.addEventListener('install', evt => {
    self.skipWaiting();
});

self.addEventListener('activate', evt => {
    evt.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

/* Network-first: siempre intenta la red; usa caché solo si falla */
self.addEventListener('fetch', evt => {
    if (evt.request.method !== 'GET') return;
    evt.respondWith(
        fetch(evt.request)
            .then(resp => {
                if (resp && resp.status === 200 && resp.type === 'basic') {
                    const clone = resp.clone();
                    caches.open(CACHE_NAME).then(c => c.put(evt.request, clone));
                }
                return resp;
            })
            .catch(() => caches.match(evt.request))
    );
});
""".strip()


@app.get("/sw.js")
async def service_worker():
    return Response(
        content=_SW_JS,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


# ── Rutas principales ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_usuario_actual(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(
        request=request, name="login.html",
        context={"empresas": get_empresas()},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = get_usuario_actual(request)
    if not user:
        return RedirectResponse("/")

    rol = user.get("rol", "")
    empresa_db = user["empresa_db"]

    bloques = {}
    kpis = {}
    _log_dash = logger.get("clf.dashboard")

    try:
        with get_pool_empresa(empresa_db).conexion() as (_, cur):

            # ── KPIs de montos ────────────────────────────────────────────────
            if rol in ("Administrador", "Operador"):
                cur.execute("""
                    SELECT
                        COALESCE(SUM(total) FILTER (
                            WHERE estado IN (
                                'Programada','Parcialmente Entregada',
                                'Entregada','Facturada','Pagada'
                            )
                        ), 0) AS monto_vendido,
                        COALESCE(SUM(total - COALESCE(monto_pagado, 0)) FILTER (
                            WHERE estado IN (
                                'Programada','Parcialmente Entregada',
                                'Entregada','Facturada'
                            )
                              AND (total - COALESCE(monto_pagado, 0)) > 0.01
                        ), 0) AS pendiente_cobrar
                    FROM cotizaciones
                """)
                r = cur.fetchone()
                kpis = {"monto_vendido": float(r[0]), "pendiente_cobrar": float(r[1])}

            # ── Proceso Comercial ─────────────────────────────────────────────
            if rol in ("Administrador", "Operador"):
                cur.execute("""
                    SELECT c.id, c.folio, c.fecha, cl.nombre_comercial, c.total
                    FROM cotizaciones c
                    LEFT JOIN clientes cl ON cl.id = c.cliente_id
                    WHERE c.estado = 'Pendiente'
                      AND c.fecha < CURRENT_DATE - INTERVAL '15 days'
                    ORDER BY c.fecha ASC
                    LIMIT 20
                """)
                cols = [d[0] for d in cur.description]
                sin_respuesta = [dict(zip(cols, r)) for r in cur.fetchall()]

                cur.execute("""
                    SELECT c.id, c.folio, c.fecha, cl.nombre_comercial, c.total
                    FROM cotizaciones c
                    LEFT JOIN clientes cl ON cl.id = c.cliente_id
                    WHERE c.estado = 'Programada'
                      AND (c.orden_compra IS NULL OR c.orden_compra = '')
                    ORDER BY c.fecha ASC
                    LIMIT 20
                """)
                cols = [d[0] for d in cur.description]
                sin_oc = [dict(zip(cols, r)) for r in cur.fetchall()]

                bloques["comercial"] = {
                    "sin_respuesta": sin_respuesta,
                    "sin_oc": sin_oc,
                }

            # ── Proceso Logístico ─────────────────────────────────────────────
            if rol in ("Administrador", "Operador", "Almacenista"):
                cur.execute("""
                    SELECT DISTINCT c.id, c.folio, c.fecha_entrega,
                           cl.nombre_comercial, c.total
                    FROM cotizaciones c
                    LEFT JOIN clientes cl ON cl.id = c.cliente_id
                    JOIN cotizacion_detalle cd ON cd.cotizacion_id = c.id
                    JOIN productos p ON p.id = cd.producto_id
                    WHERE c.estado = 'Programada'
                      AND cd.cantidad > COALESCE(p.stock_actual, 0)
                    ORDER BY c.fecha_entrega ASC NULLS LAST
                    LIMIT 20
                """)
                cols = [d[0] for d in cur.description]
                sin_stock = [dict(zip(cols, r)) for r in cur.fetchall()]

                cur.execute("""
                    SELECT c.id, c.folio, c.fecha_entrega,
                           cl.nombre_comercial, c.total, c.estado
                    FROM cotizaciones c
                    LEFT JOIN clientes cl ON cl.id = c.cliente_id
                    WHERE c.estado IN ('Programada', 'Parcialmente Entregada')
                    ORDER BY c.fecha_entrega ASC NULLS LAST
                    LIMIT 20
                """)
                cols = [d[0] for d in cur.description]
                entregas_pendientes = [dict(zip(cols, r)) for r in cur.fetchall()]

                bloques["logistico"] = {
                    "sin_stock": sin_stock,
                    "entregas_pendientes": entregas_pendientes,
                }

            # ── Proceso Administrativo ────────────────────────────────────────
            if rol == "Administrador":
                cur.execute("""
                    SELECT c.id, c.folio, c.fecha, cl.nombre_comercial,
                           c.total, COALESCE(c.monto_pagado, 0) AS monto_pagado
                    FROM cotizaciones c
                    LEFT JOIN clientes cl ON cl.id = c.cliente_id
                    WHERE c.estado = 'Entregada'
                      AND (c.monto_pagado IS NULL OR c.monto_pagado < c.total)
                      AND EXISTS (
                          SELECT 1 FROM facturas f WHERE f.cotizacion_id = c.id
                      )
                    ORDER BY c.fecha ASC
                    LIMIT 20
                """)
                cols = [d[0] for d in cur.description]
                facturas_sin_pago = [dict(zip(cols, r)) for r in cur.fetchall()]

                bloques["administrativo"] = {
                    "facturas_sin_pago": facturas_sin_pago,
                }

    except Exception as e:
        _log_dash.exception("Error cargando dashboard para %s: %s", empresa_db, e)

    from core.constants import ESTADO_COLOR_CSS
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "user": user,
            "bloques": bloques,
            "kpis": kpis,
            "estado_color": ESTADO_COLOR_CSS,
        },
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
