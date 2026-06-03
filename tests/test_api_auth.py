# -*- coding: utf-8 -*-
"""
tests/test_api_auth.py
Pruebas de los endpoints JSON de autenticación (/api/auth/*).
"""

import pytest


# ── POST /api/auth/login ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_login_exitoso(client):
    """Login correcto → 200 con access_token y user."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" in data
    assert data["user"]["username"] == "admin"
    # Token tiene formato JWT (3 partes separadas por punto)
    assert len(data["access_token"].split(".")) == 3


@pytest.mark.anyio
async def test_api_login_password_incorrecta(client):
    """Password incorrecta → 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong_password"},
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


@pytest.mark.anyio
async def test_api_login_usuario_inexistente(client):
    """Usuario que no existe → 401."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "no_existe_xyzabc", "password": "cualquiera"},
    )
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_api_login_setea_cookie(client):
    """Login API también setea cookie httponly (para compatibilidad)."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "access_token" in set_cookie
    assert "httponly" in set_cookie.lower()


# ── GET /api/auth/empresas ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_empresas_no_requiere_auth(client):
    """/api/auth/empresas es público (para mostrar el selector en login)."""
    resp = await client.get("/api/auth/empresas")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        assert "id" in data[0]
        assert "nombre" in data[0]


# ── POST /api/auth/logout ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_logout_invalida_token(client, bearer_token):
    """Logout con Bearer token → 200 y token queda en blacklist."""
    resp = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    assert resp.status_code == 200

    # El mismo token ya no debe funcionar
    resp2 = await client.get(
        "/api/cotizaciones",
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    assert resp2.status_code == 401


# ── Rutas protegidas sin token ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_sin_token_rechazado(client):
    """Request a endpoint /api/* sin Authorization header → 401."""
    resp = await client.get("/api/cotizaciones")
    assert resp.status_code == 401
