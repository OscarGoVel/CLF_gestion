# -*- coding: utf-8 -*-
"""
tests/test_stock.py
Pruebas de los endpoints de stock e inventario.

Ejecutar:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    pytest tests/test_stock.py -v
"""

import pytest


# ── Vista de inventario ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_stock_requiere_sesion(client):
    """/stock sin sesión → redirige."""
    resp = await client.get("/stock", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_stock_con_sesion(client_admin):
    """/stock con sesión → 200 con tabla de inventario."""
    resp = await client_admin.get("/stock")
    assert resp.status_code == 200
    assert "Stock" in resp.text


@pytest.mark.anyio
async def test_stock_filtro_busqueda(client_admin):
    """Búsqueda por nombre devuelve 200."""
    resp = await client_admin.get("/stock?buscar=test")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_stock_filtro_bajo_minimo(client_admin):
    """Filtro bajo mínimo devuelve 200."""
    resp = await client_admin.get("/stock?bajo_minimo=1")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_stock_htmx_parcial(client_admin):
    """Con header HX-Request → fragmento sin <html>."""
    resp = await client_admin.get("/stock", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "<html" not in resp.text.lower()


# ── Movimientos ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_movimientos_requiere_sesion(client):
    """/stock/movimientos sin sesión → redirige."""
    resp = await client.get("/stock/movimientos", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_movimientos_con_sesion(client_admin):
    """/stock/movimientos con sesión → 200."""
    resp = await client_admin.get("/stock/movimientos")
    assert resp.status_code == 200
    assert "Movimientos" in resp.text


@pytest.mark.anyio
async def test_movimientos_paginacion(client_admin):
    """Paginación: /stock/movimientos?pagina=1 → 200."""
    resp = await client_admin.get("/stock/movimientos?pagina=1")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_movimientos_pagina_invalida(client_admin):
    """Página fuera de rango no rompe el endpoint."""
    resp = await client_admin.get("/stock/movimientos?pagina=9999")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_movimientos_filtro_tipo(client_admin):
    """Filtro por tipo (entrada/salida) devuelve 200."""
    for tipo in ("entrada", "salida", ""):
        resp = await client_admin.get(f"/stock/movimientos?tipo={tipo}")
        assert resp.status_code == 200


@pytest.mark.anyio
async def test_movimientos_htmx_parcial(client_admin):
    """Con HX-Request → fragmento sin <html>."""
    resp = await client_admin.get(
        "/stock/movimientos", headers={"HX-Request": "true"}
    )
    assert resp.status_code == 200
    assert "<html" not in resp.text.lower()


# ── Búsqueda de producto (autocomplete) ──────────────────────────────────────

@pytest.mark.anyio
async def test_buscar_producto_requiere_sesion(client):
    """/stock/buscar-producto sin sesión → 401 o redirige."""
    resp = await client.get("/stock/buscar-producto?q=test", follow_redirects=False)
    assert resp.status_code in (302, 307, 401)


@pytest.mark.anyio
async def test_buscar_producto_retorna_json(client_admin):
    """/stock/buscar-producto con sesión → JSON list."""
    resp = await client_admin.get("/stock/buscar-producto?q=test")
    assert resp.status_code == 200
    assert resp.headers.get("content-type", "").startswith("application/json")
    data = resp.json()
    assert isinstance(data, list)


# ── Entrada de stock ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_entrada_stock_sin_sesion(client):
    """POST /stock/entrada sin sesión → redirige o 403."""
    resp = await client.post(
        "/stock/entrada",
        data={"producto_id": "1", "cantidad": "10", "referencia": "TEST"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307, 403)


@pytest.mark.anyio
async def test_entrada_stock_producto_inexistente(client_admin):
    """Entrada a producto que no existe → 404."""
    resp = await client_admin.post(
        "/stock/entrada",
        data={"producto_id": "999999", "cantidad": "1", "referencia": "X"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303, 404, 422)
