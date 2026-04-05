"""Configuración del bot de Telegram.

Variables de entorno requeridas:
  TELEGRAM_BOT_TOKEN  — token del bot (BotFather)
  API_BASE_URL        — URL base de la API FastAPI (ej: https://tu-app.railway.app)
"""
import os

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
API_BASE_URL: str = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_PREFIX = "/api/v1"
