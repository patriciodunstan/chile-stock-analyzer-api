"""Configuración de tests."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.infrastructure.persistence.database import init_db


@pytest_asyncio.fixture
async def async_client():
    """Cliente HTTP de test contra la app FastAPI."""
    await init_db()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
