# -*- coding: utf-8 -*-
"""
tests/test_auth.py
Pruebas de los endpoints de autenticacion y seguridad.

Ejecutar:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    pytest tests/ -v
"""

import pytest


# ── Login ─────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_login_exitoso_redirige_dashboard(client):
    """Login con credenciales correctas → redirige a /dashboard."""
    resp = await client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "/dashboard"


@pytest.mark.anyio
async def test_login_exitoso_setea_cookie(client):
    """Login correcto → cookie access_token httponly presente."""
    resp = await client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    cookie = resp.cookies.get("access_token")
    assert cookie is not None
    # Verificar que es un JWT (3 partes separadas por punto)
    assert len(cookie.split(".")) == 3


@pytest.mark.anyio
async def test_login_password_incorrecta(client):
    """Password incorrecta → 200 con mensaje de error (no redirige)."""
    resp = await client.post(
        "/auth/login",
        data={"username": "admin", "password": "mal_password"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "incorrectos" in resp.text.lower()


@pytest.mark.anyio
async def test_login_usuario_inexistente(client):
    """Usuario que no existe → 200 con mensaje de error."""
    resp = await client.post(
        "/auth/login",
        data={"username": "nadie", "password": "algo"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "incorrectos" in resp.text.lower()


# ── Rutas protegidas ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_dashboard_sin_sesion_redirige_login(client):
    """/dashboard sin cookie → redirige a /."""
    resp = await client.get("/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_dashboard_con_sesion(client_admin):
    """/dashboard con sesion valida → 200."""
    resp = await client_admin.get("/dashboard")
    assert resp.status_code == 200
    assert "Dashboard" in resp.text


@pytest.mark.anyio
async def test_raiz_sin_sesion_muestra_login(client):
    """/ sin sesion → pagina de login."""
    resp = await client.get("/", follow_redirects=False)
    assert resp.status_code == 200
    assert "action=\"/auth/login\"" in resp.text


@pytest.mark.anyio
async def test_raiz_con_sesion_redirige_dashboard(client_admin):
    """/ con sesion activa → redirige al dashboard."""
    resp = await client_admin.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/dashboard" in resp.headers.get("location", "")


# ── Logout ────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_logout_elimina_cookie(client_admin):
    """Logout → redirige a / y la cookie queda borrada."""
    resp = await client_admin.get("/auth/logout", follow_redirects=False)
    assert resp.status_code in (302, 307)
    # La cookie debe tener max-age=0 o estar ausente
    set_cookie = resp.headers.get("set-cookie", "")
    assert "access_token" in set_cookie
    assert "max-age=0" in set_cookie.lower() or "expires" in set_cookie.lower()


# ── Seguridad ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_security_headers_presentes(client):
    """Todas las respuestas incluyen los headers de seguridad."""
    resp = await client.get("/")
    headers = resp.headers
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert "strict-origin" in headers.get("referrer-policy", "")


@pytest.mark.anyio
async def test_cookie_httponly(client):
    """La cookie JWT debe ser httponly (no accesible por JS)."""
    resp = await client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    set_cookie = resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


# ── Health check ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health_endpoint(client):
    """/health → JSON con estado de la aplicacion."""
    resp = await client.get("/health")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "estado" in data
    assert "db" in data
    assert "version" in data


# ── Paginas de error ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_404_pagina_html(client):
    """Ruta inexistente → 404 con HTML (no JSON)."""
    resp = await client.get("/esta-ruta-no-existe")
    assert resp.status_code == 404
    assert "404" in resp.text
    assert "text/html" in resp.headers.get("content-type", "")
