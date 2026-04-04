from __future__ import annotations
"""Proveedor compuesto con fallback en cascada (Strategy Pattern).

Orden de prioridad:
1. Bolsa de Santiago API (datos real-time oficiales)
2. Yahoo Finance vía yfinance (datos real-time, fundamentales incluidos)
3. EODHD (datos end-of-day, tier gratuito)
4. Mock data (desarrollo / último recurso)

Si un proveedor falla, pasa al siguiente automáticamente.
Loguea qué fuente se usó para cada request.
"""

import logging
from datetime import datetime

from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.entities.stock import Stock, StockPrice
from app.domain.exceptions import ExternalAPIError, TickerNotFoundError

logger = logging.getLogger(__name__)


class CompositeMarketProvider(MarketDataProvider):
    """Proveedor que itera sobre múltiples fuentes en orden de prioridad."""

    def __init__(self, providers: list[tuple[str, MarketDataProvider]]):
        """
        Args:
            providers: Lista de tuplas (nombre, proveedor) en orden de prioridad.
                       Ejemplo: [("bolsa", bolsa_client), ("yahoo", yahoo_client)]
        """
        self._providers = providers
        self._last_source: str = "none"

    @property
    def last_source(self) -> str:
        """Nombre del último proveedor que respondió exitosamente."""
        return self._last_source

    async def get_price(self, ticker: str) -> StockPrice:
        """Intenta obtener precio de cada proveedor en cascada."""
        errors: list[str] = []

        for name, provider in self._providers:
            try:
                price = await provider.get_price(ticker)
                self._last_source = name
                logger.info(f"Price for {ticker} from [{name}]")
                return price
            except TickerNotFoundError:
                # Si el ticker no existe, no tiene sentido probar otro proveedor
                raise
            except (ExternalAPIError, Exception) as e:
                errors.append(f"{name}: {str(e)}")
                logger.warning(f"Provider [{name}] failed for {ticker}: {e}")
                continue

        # Todos los proveedores fallaron
        raise ExternalAPIError(
            message=f"All providers failed for '{ticker}'",
            details={
                "ticker": ticker,
                "errors": errors,
                "providers_tried": [name for name, _ in self._providers],
            },
        )

    async def get_constituents(self, index: str = "IPSA") -> list[Stock]:
        """Intenta obtener constituyentes de cada proveedor en cascada."""
        for name, provider in self._providers:
            try:
                result = await provider.get_constituents(index)
                if result:  # Solo acepta si retorna datos
                    self._last_source = name
                    logger.info(
                        f"Constituents for {index} from [{name}]: {len(result)} stocks"
                    )
                    return result
            except Exception as e:
                logger.warning(f"Provider [{name}] constituents failed: {e}")
                continue

        return []

    async def search(self, query: str) -> list[Stock]:
        """Busca en cada proveedor hasta encontrar resultados."""
        for name, provider in self._providers:
            try:
                result = await provider.search(query)
                if result:
                    self._last_source = name
                    return result
            except Exception:
                continue
        return []


def build_composite_provider() -> CompositeMarketProvider:
    """Factory que construye el proveedor compuesto con todos los disponibles.

    Detecta automáticamente qué librerías están instaladas.
    """
    providers: list[tuple[str, MarketDataProvider]] = []

    # 1. Bolsa de Santiago API (siempre disponible, tiene fallback a mock)
    from app.infrastructure.external.bolsa_santiago.client import BolsaSantiagoClient
    providers.append(("bolsa_santiago", BolsaSantiagoClient()))

    # 2. Yahoo Finance (si yfinance está instalado)
    try:
        from app.infrastructure.external.yahoo_finance.client import (
            YahooFinanceClient,
            YFINANCE_AVAILABLE,
        )
        if YFINANCE_AVAILABLE:
            providers.append(("yahoo_finance", YahooFinanceClient()))
            logger.info("Yahoo Finance provider enabled")
    except ImportError:
        logger.info("yfinance not available, skipping Yahoo Finance provider")

    # 3. EODHD (siempre disponible, usa httpx)
    from app.infrastructure.external.eodhd.client import EODHDClient
    providers.append(("eodhd", EODHDClient()))

    logger.info(
        f"Composite provider initialized with {len(providers)} sources: "
        f"{[name for name, _ in providers]}"
    )

    return CompositeMarketProvider(providers)
