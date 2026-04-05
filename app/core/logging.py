"""Configuración centralizada de logging para Railway y producción.

Formato legible en Railway con nivel, timestamp, módulo y mensaje.
Nivel configurable via LOG_LEVEL env var (default: INFO).
"""
import logging
import sys
from app.config import get_settings


def setup_logging() -> None:
    """Configura el sistema de logging de la aplicación."""
    settings = get_settings()
    log_level = logging.DEBUG if settings.debug else logging.INFO

    fmt = "%(levelname)s | %(name)s | %(message)s"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )

    # Silenciar loggers ruidosos de librerías externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging configurado | level={'DEBUG' if settings.debug else 'INFO'} | "
        f"service={settings.app_name}"
    )
