from __future__ import annotations
"""Proveedor de datos vía EODHD (End of Day Historical Data).

Tier gratuito: datos end-of-day con 20 llamadas/día sin API key
(usando demo token). Acciones chilenas usan sufijo .SN.

Docs: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
"""

import logging
from datetime import datetime

import httpx

from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.entities.stock import Stock, StockPrice
from app.domain.exceptions import ExternalAPIError, TickerNotFoundError
from app.infrastructure.external.yahoo_finance.ticker_map import to_yahoo_ticker

logger = logging.getLogger(__name__)

EODHD_BASE_URL = "https://eodhd.com/api"
# Token demo gratuito — 20 requests/día, solo datos EOD
EODHD_DEMO_TOKEN = "demo"


class EODHDClient(MarketDataProvider):
    """Proveedor de datos end-of-day vía EODHD. Sin registro requerido."""

    def __init__(self, api_token: str = EODHD_DEMO_TOKEN, timeout: float = 15.0):
        self._token = api_token
        self._timeout = timeout

    async def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """GET request a EODHD API."""
        url = f"{EODHD_BASE_URL}{endpoint}"
        base_params = {"api_token": self._token, "fmt": "json"}
        if params:
            base_params.update(params)

        try:
            async with httpx.AsyncClient(timeout=self._timeout, proxy=None) as client:
                response = await client.get(url, params=base_params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, httpx.RequestError) as e:
            logger.error(f"EODHD API error: {e}")
            raise ExternalAPIError(
                message="EODHD API error",
                details={"endpoint": endpoint, "error": str(e)},
            )

    async def get_price(self, ticker: str) -> StockPrice:
        """Obtiene último precio end-of-day desde EODHD."""
        nemo = ticker.upper()
        # EODHD usa el mismo formato que Yahoo: TICKER.SN
        eodhd_ticker = to_yahoo_ticker(nemo)

        try:
            data = await self._get(f"/real-time/{eodhd_ticker}")

            if not data or isinstance(data, list):
                raise TickerNotFoundError(
                    message=f"No EODHD data for '{nemo}'",
                    details={"ticker": nemo},
                )

            return StockPrice(
                ticker=nemo,
                price=float(data.get("close", 0)),
                open_price=float(data.get("open", 0)),
                high=float(data.get("high", 0)),
                low=float(data.get("low", 0)),
                close_price=float(data.get("previousClose", data.get("close", 0))),
                volume=int(data.get("volume", 0)),
                market_cap=0.0,  # EODHD free no incluye market cap
                change_percent=float(data.get("change_p", 0)),
                timestamp=datetime.utcnow(),
                currency="CLP",
            )
        except (TickerNotFoundError, ExternalAPIError):
            raise
        except Exception as e:
            logger.error(f"EODHD parse error for {nemo}: {e}")
            raise ExternalAPIError(
                message=f"EODHD error for {nemo}",
                details={"ticker": nemo, "error": str(e)},
            )

    async def get_constituents(self, index: str = "IPSA") -> list[Stock]:
        """EODHD free no soporta listado de constituyentes.

        Retorna lista vacía para que el strategy pattern
        pase al siguiente proveedor.
        """
        return []

    async def search(self, query: str) -> list[Stock]:
        """EODHD free no soporta búsqueda."""
        return []
