"""Registry de scrapers de IR.

Factory pattern: mapea ticker → scraper específico.
Permite agregar nuevas empresas sin modificar el código existente.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .base_scraper import BaseIRScraper
from .sqm_scraper import SQMScraper

logger = logging.getLogger(__name__)

# Registry de scrapers disponibles
_SCRAPER_REGISTRY: dict[str, type] = {
    "SQM-B": SQMScraper,
    # Futuros:
    # "FALABELLA": FalabellaScraper,
    # "CAP": CAPScraper,
    # "BCI": BCIScraper,
    # "CENCOSUD": CencosudScraper,
}

# Tickers que usan el mismo scraper (aliases)
_TICKER_ALIASES: dict[str, str] = {
    "SQM": "SQM-B",
    "SQM-A": "SQM-B",
}


def get_scraper(ticker: str, data_dir: Path | None = None) -> BaseIRScraper:
    """Factory: obtiene el scraper correcto para un ticker.

    Args:
        ticker: Nemo/ticker de la empresa (ej: "SQM-B", "FALABELLA")
        data_dir: Directorio base para almacenar reportes descargados.
                  Default: data/reports/ en la raíz del proyecto.

    Returns:
        Instancia del scraper específico para esa empresa.

    Raises:
        ValueError: Si no hay scraper registrado para el ticker.
    """
    if data_dir is None:
        data_dir = Path("data/reports")

    # Resolver alias
    resolved = _TICKER_ALIASES.get(ticker.upper(), ticker.upper())

    scraper_class = _SCRAPER_REGISTRY.get(resolved)
    if scraper_class is None:
        available = list(_SCRAPER_REGISTRY.keys())
        raise ValueError(
            f"No hay scraper registrado para '{ticker}'. "
            f"Tickers disponibles: {available}"
        )

    return scraper_class(data_dir=data_dir)


def list_available_scrapers() -> list[str]:
    """Lista todos los tickers con scraper disponible."""
    return list(_SCRAPER_REGISTRY.keys())


def register_scraper(ticker: str, scraper_class: type):
    """Registra un nuevo scraper para un ticker.

    Permite extensión sin modificar este archivo.
    """
    _SCRAPER_REGISTRY[ticker.upper()] = scraper_class
    logger.info(f"Scraper registrado: {ticker} → {scraper_class.__name__}")
