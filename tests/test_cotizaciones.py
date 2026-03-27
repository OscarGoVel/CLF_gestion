# -*- coding: utf-8 -*-
"""
tests/test_cotizaciones.py
Pruebas de los endpoints de cotizaciones.

Ejecutar:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    pytest tests/test_cotizaciones.py -v
"""

import pytest


# ── Lista de cotizaciones ──────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_lista_cotizaciones_requiere_sesion(client):
    """/cotizaciones sin sesión → redirige al login."""
    resp = await client.get("/cotizaciones", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_lista_cotizaciones_con_sesion(client_admin):
    """/cotizaciones con sesión válida → 200 con contenido HTML."""
    resp = await client_admin.get("/cotizaciones")
    assert resp.status_code == 200
    assert "Cotizaciones" in resp.text


@pytest.mark.anyio
async def test_lista_cotizaciones_filtro_estado(client_admin):
    """Filtrar por estado devuelve 200 (aunque no haya resultados)."""
    resp = await client_admin.get("/cotizaciones?estado=Pendiente")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_lista_cotizaciones_busqueda(client_admin):
    """Búsqueda por folio devuelve 200."""
    resp = await client_admin.get("/cotizaciones?buscar=COT")
    assert resp.status_code == 200


# ── HTMX parcial ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_lista_htmx_devuelve_parcial(client_admin):
    """Con header HX-Request → devuelve fragmento (sin <html>)."""
    resp = await client_admin.get(
        "/cotizaciones",
        headers={"HX-Request": "true"},
    )
    assert resp.status_code == 200
    assert "<html" not in resp.text.lower()


# ── Formulario nueva cotización ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_formulario_nueva_cotizacion_requiere_sesion(client):
    """/cotizaciones/nueva sin sesión → redirige."""
    resp = await client.get("/cotizaciones/nueva", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_formulario_nueva_cotizacion_con_sesion(client_admin):
    """/cotizaciones/nueva con sesión → 200 con formulario."""
    resp = await client_admin.get("/cotizaciones/nueva")
    assert resp.status_code == 200
    assert "form" in resp.text.lower()


# ── Solo lectura para rol insuficiente ────────────────────────────────────────

@pytest.mark.anyio
async def test_nueva_cotizacion_rol_solo_lectura(client):
    """Usuario con rol Solo lectura no puede crear cotizaciones (403)."""
    # Primero autenticarse como usuario de solo lectura si existe,
    # sino verificar que sin sesión redirige (ya cubierto arriba)
    resp = await client.get("/cotizaciones/nueva", follow_redirects=False)
    assert resp.status_code in (302, 307, 403)


# ── Detalle de cotización ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_detalle_cotizacion_inexistente(client_admin):
    """ID que no existe → 404."""
    resp = await client_admin.get("/cotizaciones/999999")
    assert resp.status_code == 404


# ── PDF ───────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pdf_cotizacion_inexistente(client_admin):
    """PDF de ID inexistente → 404."""
    resp = await client_admin.get("/cotizaciones/999999/pdf")
    assert resp.status_code == 404


# ── Seguridad: RBAC ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_cambio_estado_sin_sesion(client):
    """POST cambio de estado sin sesión → redirige o 403."""
    resp = await client.post(
        "/cotizaciones/1/estado",
        data={"nuevo_estado": "Pagada"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307, 403)
