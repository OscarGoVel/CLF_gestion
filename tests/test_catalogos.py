# -*- coding: utf-8 -*-
"""
tests/test_catalogos.py
Pruebas de los endpoints de catálogos (clientes, productos, proveedores).

Ejecutar:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    pytest tests/test_catalogos.py -v
"""

import pytest


# ── Clientes ──────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_lista_clientes_requiere_sesion(client):
    resp = await client.get("/catalogos/clientes", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_lista_clientes_con_sesion(client_admin):
    resp = await client_admin.get("/catalogos/clientes")
    assert resp.status_code == 200
    assert "Clientes" in resp.text


@pytest.mark.anyio
async def test_nuevo_cliente_form(client_admin):
    resp = await client_admin.get("/catalogos/clientes/nuevo")
    assert resp.status_code == 200
    assert "form" in resp.text.lower()


@pytest.mark.anyio
async def test_nuevo_cliente_nombre_vacio(client_admin):
    """POST sin nombre → re-renderiza formulario con error (no redirige)."""
    resp = await client_admin.post(
        "/catalogos/clientes/nuevo",
        data={"nombre_comercial": "", "tipo": "Empresa"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "obligatorio" in resp.text.lower()


@pytest.mark.anyio
async def test_detalle_cliente_inexistente(client_admin):
    resp = await client_admin.get("/catalogos/clientes/999999")
    assert resp.status_code == 404


# ── Productos ─────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_lista_productos_con_sesion(client_admin):
    resp = await client_admin.get("/catalogos/productos")
    assert resp.status_code == 200
    assert "Productos" in resp.text


@pytest.mark.anyio
async def test_nuevo_producto_form(client_admin):
    resp = await client_admin.get("/catalogos/productos/nuevo")
    assert resp.status_code == 200
    assert "form" in resp.text.lower()


@pytest.mark.anyio
async def test_nuevo_producto_nombre_vacio(client_admin):
    """POST sin nombre → re-renderiza formulario con error."""
    resp = await client_admin.post(
        "/catalogos/productos/nuevo",
        data={"nombre": "", "precio_base": "0"},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "obligatorio" in resp.text.lower()


@pytest.mark.anyio
async def test_detalle_producto_inexistente(client_admin):
    resp = await client_admin.get("/catalogos/productos/999999")
    assert resp.status_code == 404


# ── Proveedores ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_lista_proveedores_requiere_sesion(client):
    resp = await client.get("/catalogos/proveedores", follow_redirects=False)
    assert resp.status_code in (302, 307)


@pytest.mark.anyio
async def test_lista_proveedores_con_sesion(client_admin):
    resp = await client_admin.get("/catalogos/proveedores")
    assert resp.status_code == 200
    assert "Proveedores" in resp.text


@pytest.mark.anyio
async def test_nuevo_proveedor_form(client_admin):
    resp = await client_admin.get("/catalogos/proveedores/nuevo")
    assert resp.status_code == 200
    assert "form" in resp.text.lower()


@pytest.mark.anyio
async def test_nuevo_proveedor_nombre_vacio(client_admin):
    """POST sin nombre → re-renderiza formulario con error."""
    resp = await client_admin.post(
        "/catalogos/proveedores/nuevo",
        data={"nombre": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "obligatorio" in resp.text.lower()


@pytest.mark.anyio
async def test_detalle_proveedor_inexistente(client_admin):
    resp = await client_admin.get("/catalogos/proveedores/999999")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_editar_proveedor_inexistente(client_admin):
    resp = await client_admin.get("/catalogos/proveedores/999999/editar")
    assert resp.status_code == 404


# ── RBAC: Solo lectura no puede crear ────────────────────────────────────────

@pytest.mark.anyio
async def test_crear_proveedor_sin_sesion(client):
    """POST sin sesión → redirige o 403."""
    resp = await client.post(
        "/catalogos/proveedores/nuevo",
        data={"nombre": "Test Proveedor"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 307, 403)
