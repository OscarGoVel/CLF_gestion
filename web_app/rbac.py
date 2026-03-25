# -*- coding: utf-8 -*-
"""
web_app/rbac.py
Control de acceso basado en roles (RBAC).

Roles disponibles (en orden de jerarquia):
  Administrador > Operador > Solo lectura

Uso en rutas:
    from web_app.rbac import require_rol, LoginRequerido

    @app.get("/admin/usuarios")
    async def admin_panel(user=Depends(require_rol("Administrador"))):
        ...

    @app.get("/cotizaciones")
    async def cotizaciones(user=Depends(require_rol("Administrador", "Operador"))):
        ...
"""

from typing import Optional
from fastapi import Depends, HTTPException, Request, status

from web_app.dependencies import get_usuario_actual

# ── Jerarquía de roles ────────────────────────────────────────────────────────
ROLES: dict[str, int] = {
    "Administrador": 3,
    "Operador":      2,
    "Solo lectura":  1,
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


# ── Shortcuts ─────────────────────────────────────────────────────────────────

def solo_admin(request: Request) -> dict:
    """Dependency directa para rutas solo de Administrador."""
    return _get_user_or_401(request)


def usuario_activo(request: Request) -> dict:
    """Dependency que solo exige sesion valida (cualquier rol)."""
    return _get_user_or_401(request)
