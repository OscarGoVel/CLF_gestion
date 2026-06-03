# -*- coding: utf-8 -*-
"""
tests/conftest.py
Fixtures compartidos para toda la suite de pruebas.
"""

import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from web_app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Cliente HTTP asíncrono apuntando a la app FastAPI en memoria."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def client_admin(client):
    """Cliente ya autenticado como admin (cookie Jinja)."""
    await client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    return client


# ── Fixtures para endpoints /api/* (Bearer token) ────────────────────────────

@pytest.fixture
async def bearer_token(client):
    """Obtiene un JWT válido para usar en cabeceras Authorization: Bearer."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, f"Login API falló: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
async def auth_headers(bearer_token):
    """Cabeceras con Bearer token listas para usar en requests API."""
    return {"Authorization": f"Bearer {bearer_token}"}
