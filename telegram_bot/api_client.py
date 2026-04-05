"""Cliente HTTP para llamar a la API FastAPI desde el bot."""
from __future__ import annotations

import httpx

from telegram_bot.config import API_BASE_URL, API_PREFIX

_BASE = f"{API_BASE_URL}{API_PREFIX}"
_TIMEOUT = 30.0


async def get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(f"{_BASE}{path}")
        r.raise_for_status()
        return r.json()


async def post(path: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(f"{_BASE}{path}", json=body or {})
        r.raise_for_status()
        return r.json()
