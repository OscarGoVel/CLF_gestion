# -*- coding: utf-8 -*-
"""
tests/test_api_cotizaciones.py
Pruebas de los endpoints /api/cotizaciones.
"""

import pytest


# ── GET /api/cotizaciones ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_listar_cotizaciones_sin_token(client):
    """Sin token → 401."""
    resp = await client.get("/api/cotizaciones")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_listar_cotizaciones_con_token(client, auth_headers):
    """Con token válido → 200 con estructura esperada."""
    resp = await client.get("/api/cotizaciones", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "cotizaciones" in data
    assert "total" in data
    assert isinstance(data["cotizaciones"], list)


@pytest.mark.anyio
async def test_listar_cotizaciones_paginacion(client, auth_headers):
    """Parámetros de paginación son respetados."""
    resp = await client.get("/api/cotizaciones?pagina=1", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_listar_cotizaciones_filtro_estado(client, auth_headers):
    """Filtro por estado no rompe el endpoint."""
    resp = await client.get("/api/cotizaciones?estado=Pendiente", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    for cot in data["cotizaciones"]:
        assert cot["estado"] == "Pendiente"


# ── GET /api/cotizaciones/:id ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_detalle_cotizacion_inexistente(client, auth_headers):
    """ID inexistente → 404."""
    resp = await client.get("/api/cotizaciones/999999", headers=auth_headers)
    assert resp.status_code == 404


# ── POST /api/cotizaciones ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_crear_cotizacion_payload_invalido(client, auth_headers):
    """Payload incompleto → 422 (validación Pydantic)."""
    resp = await client.post("/api/cotizaciones", json={}, headers=auth_headers)
    assert resp.status_code == 422


# ── Búsqueda de productos ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_buscar_producto_sin_token(client):
    """Búsqueda sin token → 401."""
    resp = await client.get("/api/comercial/cotizaciones/buscar-producto?q=agua")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_buscar_producto_query_corta(client, auth_headers):
    """Query de 1 carácter → 200 con resultados vacíos (mínimo es 2)."""
    resp = await client.get(
        "/api/comercial/cotizaciones/buscar-producto?q=a",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "resultados" in data
