# -*- coding: utf-8 -*-
"""
web_app/rbac.py
Control de acceso basado en roles (RBAC).

Roles disponibles (en orden de jerarquia):
  Administrador > Operador = Almacenista > Solo lectura

Uso en rutas:
    from web_app.rbac import require_rol, require_permiso

    @app.get("/admin/usuarios")
    async def admin_panel(user=Depends(require_rol("Administrador"))):
        ...

    @app.post("/stock/entrada")
    async def entrada(user=Depends(require_permiso("stock.entrada_manual"))):
        ...
"""

from fastapi import HTTPException, Request, status

from web_app.dependencies import get_usuario_actual

# ── Jerarquía de roles ────────────────────────────────────────────────────────
ROLES: dict[str, int] = {
    "Administrador": 3,
    "Operador":      2,
    "Almacenista":   2,   # mismo nivel numérico; distinción por nombre
    "Solo lectura":  1,
}

# ── Permisos por defecto (configurable por empresa vía /admin/permisos) ───────
PERMISOS_DEFAULT: dict[str, list[str]] = {
    "cotizacion.crear":          ["Administrador", "Operador"],
    "cotizacion.editar":         ["Administrador", "Operador"],
    "cotizacion.cambiar_estado": ["Administrador", "Operador"],
    "cotizacion.marcar_pagada":  ["Administrador"],
    "cotizacion.ver_precios":    ["Administrador", "Operador", "Almacenista"],
    "factura.importar":          ["Administrador", "Operador"],
    "factura.vincular":          ["Administrador", "Operador"],
    "factura.ver_montos":        ["Administrador", "Operador", "Almacenista"],
    "stock.entrada_manual":      ["Administrador"],
    "stock.salida_manual":       ["Administrador"],
    "catalogo.crear_editar":     ["Administrador", "Operador"],
    "catalogo.eliminar":         ["Administrador"],
    "preinventario.capturar":    ["Administrador", "Operador", "Almacenista"],
    "preinventario.aprobar":     ["Administrador"],
    "estudio.gestionar":         ["Administrador", "Operador"],
    "estudio.aplicar_catalogo":  ["Administrador"],
}

# Etiquetas legibles para la pantalla de configuración
PERMISOS_LABELS: dict[str, str] = {
    "cotizacion.crear":          "Cotización: Crear nueva",
    "cotizacion.editar":         "Cotización: Editar",
    "cotizacion.cambiar_estado": "Cotización: Cambiar estado",
    "cotizacion.marcar_pagada":  "Cotización: Marcar como Pagada",
    "cotizacion.ver_precios":    "Cotización: Ver precios y totales",
    "factura.importar":          "Factura: Importar XML",
    "factura.vincular":          "Factura: Vincular a cotización",
    "factura.ver_montos":        "Factura: Ver montos e importes",
    "stock.entrada_manual":      "Stock: Registrar entrada manual",
    "stock.salida_manual":       "Stock: Registrar salida manual",
    "catalogo.crear_editar":     "Catálogo: Crear y editar registros",
    "catalogo.eliminar":         "Catálogo: Eliminar registros",
    "preinventario.capturar":    "Pre-Inventario: Capturar conteos",
    "preinventario.aprobar":     "Pre-Inventario: Aprobar / rechazar sesión",
    "estudio.gestionar":         "Estudio de Mercado: Crear y capturar",
    "estudio.aplicar_catalogo":  "Estudio de Mercado: Aplicar precio al catálogo",
}


def _get_user_or_401(request: Request) -> dict:
    """Obtiene el usuario actual o lanza 401."""
    user = get_usuario_actual(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion no valida o expirada.",
        )
    return user


def require_rol(*roles: str):
    """
    Dependency factory que verifica que el usuario tenga uno de los roles indicados.
    Si no hay sesion → 401.  Si el rol no alcanza → 403.

    Ejemplo:
        Depends(require_rol("Administrador", "Operador"))
    """
    roles_set = set(roles)

    async def _check(request: Request) -> dict:
        user = _get_user_or_401(request)
        if user.get("rol") not in roles_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso restringido. Se requiere uno de: {', '.join(roles_set)}.",
            )
        return user

    return _check


# ── Sistema de permisos configurables ─────────────────────────────────────────

def _get_permisos_empresa(empresa_db: str) -> dict[str, set[str]]:
    """
    Carga los permisos efectivos para una empresa.
    Usa cache en memoria (TTL 5 min). Si la empresa tiene overrides en DB,
    esos reemplazan los defaults para esa clave. Administrador siempre incluido.
    """
    from web_app.cache import cache as _cache
    cached = _cache.get(f"permisos:{empresa_db}")
    if cached is not None:
        return cached

    from web_app.database import get_pool_empresa
    try:
        with get_pool_empresa(empresa_db).conexion() as (_, cur):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS config_permisos (
                    permiso_key TEXT NOT NULL,
                    rol         TEXT NOT NULL,
                    PRIMARY KEY (permiso_key, rol)
                )
            """)
            cur.execute("SELECT permiso_key, rol FROM config_permisos")
            rows = cur.fetchall()
    except Exception:
        rows = []

    overrides: dict[str, set[str]] = {}
    for key, rol in rows:
        overrides.setdefault(key, set()).add(rol)

    result: dict[str, set[str]] = {}
    for key, default_roles in PERMISOS_DEFAULT.items():
        roles = overrides[key] if key in overrides else set(default_roles)
        roles.add("Administrador")   # Admin siempre tiene acceso, no puede restringirse
        result[key] = roles

    _cache.set(f"permisos:{empresa_db}", result, ttl=300)
    return result


def invalidar_cache_permisos(empresa_db: str) -> None:
    """Llama esto después de cualquier escritura en config_permisos."""
    from web_app.cache import cache as _cache
    _cache.invalidar(f"permisos:{empresa_db}")


def require_permiso(key: str):
    """
    Dependency factory basada en clave de permiso (configurable vía /admin/permisos).
    Si no hay sesion → 401. Si el rol no tiene el permiso → 403.

    Ejemplo:
        Depends(require_permiso("stock.entrada_manual"))
    """
    async def _check(request: Request) -> dict:
        user = _get_user_or_401(request)
        empresa_db = user.get("empresa_db")
        if not empresa_db:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="empresa_db faltante en token.",
            )
        permisos = _get_permisos_empresa(empresa_db)
        if user.get("rol") not in permisos.get(key, {"Administrador"}):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sin permiso para esta acción ({key}).",
            )
        return user

    return _check


# ── Shortcuts ─────────────────────────────────────────────────────────────────

def solo_admin(request: Request) -> dict:
    """Dependency directa para rutas solo de Administrador."""
    return _get_user_or_401(request)


def usuario_activo(request: Request) -> dict:
    """Dependency que solo exige sesion valida (cualquier rol)."""
    return _get_user_or_401(request)
