# -*- coding: utf-8 -*-
"""
tests/conftest.py
Fixtures compartidos para toda la suite de pruebas.
"""

import sys
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

# Agregar raiz al path para importar db_connection, etc.
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from web_app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Cliente HTTP asincrono apuntando a la app FastAPI en memoria (sin servidor real)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def client_admin(client):
    """Cliente ya autenticado como admin."""
    await client.post("/auth/login", data={"username": "admin", "password": "admin123"})
    return client
