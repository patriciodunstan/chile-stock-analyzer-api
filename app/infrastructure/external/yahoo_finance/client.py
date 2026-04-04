from __future__ import annotations
"""Proveedor de datos de mercado vía Yahoo Finance (yfinance).

No requiere API key. Acciones chilenas usan sufijo .SN.
Incluye datos fundamentales (P/E, ROE, book value, etc.) que los
otros proveedores no tienen.

Dependencia: pip install yfinance
"""

import logging
from datetime import datetime

from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.entities.stock import Stock, StockPrice
from app.domain.exceptions import ExternalAPIError, TickerNotFoundError
from app.infrastructure.external.yahoo_finance.ticker_map import (
    SANTIAGO_TO_YAHOO,
    to_santiago_nemo,
    to_yahoo_ticker,
)

logger = logging.getLogger(__name__)

try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed. Run: pip install yfinance")


class YahooFinanceClient(MarketDataProvider):
    """Proveedor de datos vía Yahoo Finance. Sin API key."""

    def __init__(self):
        if not YFINANCE_AVAILABLE:
            raise ImportError(
                "yfinance is required. Install with: pip install yfinance"
            )

    async def get_price(self, ticker: str) -> StockPrice:
        """Obtiene precio actual desde Yahoo Finance.

        yfinance es sync, pero como las llamadas son rápidas
        y el GIL se libera en I/O, funciona bien en async context.
        Para producción se podría wrappear con asyncio.to_thread().
        """
        yahoo_ticker = to_yahoo_ticker(ticker)
        nemo = ticker.upper()

        try:
            stock = yf.Ticker(yahoo_ticker)
            info = stock.fast_info

            price = info.last_price
            if price is None or price <= 0:
                raise TickerNotFoundError(
                    message=f"No price data for '{nemo}' (Yahoo: {yahoo_ticker})",
                    details={"ticker": nemo, "yahoo_ticker": yahoo_ticker},
                )

            return StockPrice(
                ticker=nemo,
                price=float(price),
                open_price=float(getattr(info, "open", 0) or 0),
                high=float(getattr(info, "day_high", 0) or 0),
                low=float(getattr(info, "day_low", 0) or 0),
                close_price=float(getattr(info, "previous_close", 0) or 0),
                volume=int(getattr(info, "last_volume", 0) or 0),
                market_cap=float(getattr(info, "market_cap", 0) or 0),
                change_percent=self._calc_change(
                    float(price),
                    float(getattr(info, "previous_close", 0) or 0),
                ),
                timestamp=datetime.utcnow(),
                currency=getattr(info, "currency", "CLP") or "CLP",
            )

        except TickerNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Yahoo Finance error for {yahoo_ticker}: {e}")
            raise ExternalAPIError(
                message=f"Yahoo Finance error for {nemo}",
                details={
                    "ticker": nemo,
                    "yahoo_ticker": yahoo_ticker,
                    "error": str(e),
                },
            )

    async def get_constituents(self, index: str = "IPSA") -> list[Stock]:
        """Retorna constituyentes conocidos del IPSA.

        Yahoo Finance no tiene endpoint de constituyentes para Santiago,
        así que usamos el mapeo estático de tickers conocidos.
        """
        stocks = []
        for nemo, yahoo_ticker in SANTIAGO_TO_YAHOO.items():
            try:
                stock = yf.Ticker(yahoo_ticker)
                info = stock.info
                stocks.append(
                    Stock(
                        ticker=nemo,
                        name=info.get("longName", info.get("shortName", nemo)),
                        sector=info.get("sector", ""),
                        market=index,
                    )
                )
            except Exception as e:
                logger.warning(f"Could not fetch info for {yahoo_ticker}: {e}")
                stocks.append(
                    Stock(ticker=nemo, name=nemo, sector="", market=index)
                )
        return stocks

    async def search(self, query: str) -> list[Stock]:
        """Busca acciones filtrando sobre tickers conocidos."""
        all_stocks = await self.get_constituents("IPSA")
        q = query.lower()
        return [
            s
            for s in all_stocks
            if q in s.ticker.lower() or q in s.name.lower()
        ]

    def get_fundamentals(self, ticker: str) -> dict:
        """Obtiene datos fundamentales de Yahoo Finance.

        Esto es un bonus que solo yfinance tiene: P/E, ROE, book value,
        earnings, dividendos, etc. Útil para la calculadora de métricas.
        """
        yahoo_ticker = to_yahoo_ticker(ticker)
        try:
            stock = yf.Ticker(yahoo_ticker)
            info = stock.info
            return {
                "pe_ratio": info.get("trailingPE"),
                "forward_pe": info.get("forwardPE"),
                "pb_ratio": info.get("priceToBook"),
                "ps_ratio": info.get("priceToSalesTrailing12Months"),
                "ev_ebitda": info.get("enterpriseToEbitda"),
                "ev_revenue": info.get("enterpriseToRevenue"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                "profit_margin": info.get("profitMargins"),
                "operating_margin": info.get("operatingMargins"),
                "gross_margin": info.get("grossMargins"),
                "debt_to_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "dividend_yield": info.get("dividendYield"),
                "payout_ratio": info.get("payoutRatio"),
                "revenue": info.get("totalRevenue"),
                "net_income": info.get("netIncomeToCommon"),
                "total_debt": info.get("totalDebt"),
                "total_cash": info.get("totalCash"),
                "book_value": info.get("bookValue"),
                "earnings_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "market_cap": info.get("marketCap"),
                "enterprise_value": info.get("enterpriseValue"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "beta": info.get("beta"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
            }
        except Exception as e:
            logger.error(f"Error getting fundamentals for {yahoo_ticker}: {e}")
            return {}

    @staticmethod
    def _calc_change(current: float, previous: float) -> float:
        if previous == 0:
            return 0.0
        return round(((current - previous) / previous) * 100, 2)
