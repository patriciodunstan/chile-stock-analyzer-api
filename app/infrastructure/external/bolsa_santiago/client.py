from __future__ import annotations
"""Cliente HTTP para la API de la Bolsa de Santiago.

Endpoints documentados:
- POST /rest/indices/getConstituents  → constituyentes de un índice (IPSA, IGPA)
- POST /rest/stocksDetail/getStockDetail → detalle de una acción
- POST /rest/stocksDetail/getStockHistory → historial de precios

La API usa POST con JSON body para todos los endpoints.

Fallback: Si la API no está disponible, usa datos mock realistas
para desarrollo y testing local.
"""

import logging
from datetime import datetime

import httpx

from app.application.interfaces.market_data_provider import MarketDataProvider
from app.config import get_settings
from app.domain.entities.stock import Stock, StockPrice
from app.domain.exceptions import ExternalAPIError, TickerNotFoundError
from app.infrastructure.external.bolsa_santiago.mock_data import (
    IPSA_CONSTITUENTS,
    get_mock_history,
    get_mock_price,
)

logger = logging.getLogger(__name__)


class BolsaSantiagoClient(MarketDataProvider):
    """Proveedor de datos de la Bolsa de Santiago con fallback a mock."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        settings = get_settings()
        self._base_url = base_url or settings.bolsa_santiago_base_url
        self._timeout = timeout
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ChileStockAnalyzer/0.1",
        }
        self._using_mock = False

    @property
    def is_using_mock(self) -> bool:
        return self._using_mock

    async def _request(
        self, endpoint: str, payload: dict | None = None
    ) -> dict:
        """Ejecuta request POST a la API de la Bolsa."""
        url = f"{self._base_url}{endpoint}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                # Bypass proxy para conexiones externas si hay SOCKS configurado
                proxy=None,
            ) as client:
                response = await client.post(
                    url,
                    json=payload or {},
                    headers=self._headers,
                )
                response.raise_for_status()
                self._using_mock = False
                return response.json()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError, ImportError) as e:
            logger.warning(
                f"Bolsa API unavailable ({type(e).__name__}), falling back to mock data"
            )
            self._using_mock = True
            raise ExternalAPIError(
                message=f"Bolsa de Santiago API unavailable",
                details={"endpoint": endpoint, "error": str(e)},
            )

    async def get_price(self, ticker: str) -> StockPrice:
        """Obtiene precio actual. Intenta API real, fallback a mock."""
        ticker_upper = ticker.upper()

        try:
            data = await self._request(
                "/rest/stocksDetail/getStockDetail",
                payload={"nemo": ticker_upper},
            )
            if not data or "nemo" not in data:
                raise TickerNotFoundError(
                    message=f"Ticker '{ticker_upper}' not found",
                    details={"ticker": ticker_upper},
                )
            return self._parse_stock_detail(data)

        except ExternalAPIError:
            # Fallback a datos mock
            logger.info(f"Using mock data for {ticker_upper}")
            mock = get_mock_price(ticker_upper)
            if not mock:
                raise TickerNotFoundError(
                    message=f"Ticker '{ticker_upper}' not found (mock mode)",
                    details={"ticker": ticker_upper, "source": "mock"},
                )
            return self._parse_stock_detail(mock)

    async def get_constituents(self, index: str = "IPSA") -> list[Stock]:
        """Obtiene constituyentes de un índice."""
        try:
            data = await self._request(
                "/rest/indices/getConstituents",
                payload={"index": index},
            )
            constituents = data.get("constituents", [])
        except ExternalAPIError:
            logger.info(f"Using mock constituents for {index}")
            constituents = IPSA_CONSTITUENTS

        return [
            Stock(
                ticker=item.get("nemo", ""),
                name=item.get("companyName", ""),
                sector=item.get("sector", ""),
                market=index,
            )
            for item in constituents
            if item.get("nemo")
        ]

    async def search(self, query: str) -> list[Stock]:
        """Busca acciones por nombre o ticker."""
        all_stocks = await self.get_constituents("IPSA")
        query_lower = query.lower()
        return [
            s
            for s in all_stocks
            if query_lower in s.ticker.lower()
            or query_lower in s.name.lower()
        ]

    async def get_price_history(
        self, ticker: str, days: int = 365
    ) -> list[StockPrice]:
        """Obtiene historial de precios."""
        try:
            data = await self._request(
                "/rest/stocksDetail/getStockHistory",
                payload={"nemo": ticker.upper(), "days": days},
            )
            history = data.get("history", [])
        except ExternalAPIError:
            logger.info(f"Using mock history for {ticker.upper()}")
            history = get_mock_history(ticker.upper(), days)

        return [self._parse_history_item(ticker, item) for item in history]

    def _parse_stock_detail(self, data: dict) -> StockPrice:
        """Parsea respuesta de getStockDetail a entidad StockPrice."""
        return StockPrice(
            ticker=data.get("nemo", ""),
            price=self._safe_float(data.get("lastPrice", 0)),
            open_price=self._safe_float(data.get("openPrice", 0)),
            high=self._safe_float(data.get("highPrice", 0)),
            low=self._safe_float(data.get("lowPrice", 0)),
            close_price=self._safe_float(data.get("closePrice", 0)),
            volume=int(data.get("volume", 0)),
            market_cap=self._safe_float(data.get("marketCap", 0)),
            change_percent=self._safe_float(data.get("changePercent", 0)),
            timestamp=datetime.utcnow(),
            currency="CLP",
        )

    def _parse_history_item(self, ticker: str, item: dict) -> StockPrice:
        """Parsea un item del historial de precios."""
        return StockPrice(
            ticker=ticker,
            price=self._safe_float(item.get("close", 0)),
            open_price=self._safe_float(item.get("open", 0)),
            high=self._safe_float(item.get("high", 0)),
            low=self._safe_float(item.get("low", 0)),
            close_price=self._safe_float(item.get("close", 0)),
            volume=int(item.get("volume", 0)),
            timestamp=datetime.fromisoformat(item["date"])
            if "date" in item
            else datetime.utcnow(),
        )

    @staticmethod
    def _safe_float(value) -> float:
        """Convierte valor a float de forma segura."""
        if value is None:
            return 0.0
        try:
            if isinstance(value, str):
                value = value.replace(".", "").replace(",", ".")
            return float(value)
        except (ValueError, TypeError):
            return 0.0
