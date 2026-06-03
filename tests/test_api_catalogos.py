# -*- coding: utf-8 -*-
"""
tests/test_api_catalogos.py
Pruebas de los endpoints /api/catalogos (búsqueda global, clientes, productos).
"""

import pytest


# ── Búsqueda global ───────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_buscar_global_sin_token(client):
    """Búsqueda global sin token → 401."""
    resp = await client.get("/api/catalogos/buscar?q=test")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_buscar_global_con_token(client, auth_headers):
    """Búsqueda global → 200 con secciones de resultados."""
    resp = await client.get("/api/catalogos/buscar?q=a", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "resultados" in data


@pytest.mark.anyio
async def test_buscar_global_query_vacia(client, auth_headers):
    """Query vacía → 200 (no debe romper)."""
    resp = await client.get("/api/catalogos/buscar?q=", headers=auth_headers)
    assert resp.status_code in (200, 422)


# ── Clientes ──────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_listar_clientes_sin_token(client):
    """Lista de clientes sin token → 401."""
    resp = await client.get("/api/catalogos/clientes")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_listar_clientes_con_token(client, auth_headers):
    """Lista de clientes → 200 con lista."""
    resp = await client.get("/api/catalogos/clientes", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "clientes" in data
    assert isinstance(data["clientes"], list)


# ── Productos ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_listar_productos_con_token(client, auth_headers):
    """Lista de productos → 200 con lista."""
    resp = await client.get("/api/catalogos/productos", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "productos" in data
    assert isinstance(data["productos"], list)


# ── Categorías ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_categorias_con_token(client, auth_headers):
    """Categorías → 200 con categorias y subcategorias."""
    resp = await client.get("/api/catalogos/categorias", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "categorias" in data
    assert "subcategorias" in data
