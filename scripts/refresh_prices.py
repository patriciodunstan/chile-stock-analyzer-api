"""Actualización diaria de precios — ejecutado por Railway Cron Job.

Obtiene el precio del día de cada ticker desde yfinance y lo persiste en la DB.
Se ejecuta después del cierre del mercado chileno (18:30 CLT = 21:30 UTC).

Uso:
    DATABASE_URL=<url> python scripts/refresh_prices.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yfinance as yf

from app.domain.entities.company import COMPANY_REGISTRY
from app.domain.entities.stock import StockPrice
from app.infrastructure.persistence.database import async_session_factory, init_db
from app.infrastructure.persistence.repositories.sqlalchemy_stock_repository import (
    SQLAlchemyStockRepository,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def refresh() -> None:
    await init_db()
    companies = list(COMPANY_REGISTRY.values())
    ok = 0
    failed = 0

    async with async_session_factory() as session:
        repo = SQLAlchemyStockRepository(session)

        for company in companies:
            yf_ticker = company.yahoo_ticker or f"{company.ticker}.SN"
            try:
                ticker_obj = yf.Ticker(yf_ticker)
                info = ticker_obj.fast_info
                close = float(info.last_price or 0)

                if close <= 0:
                    # fallback: último día del historial
                    hist = ticker_obj.history(period="2d")
                    if not hist.empty:
                        close = float(hist["Close"].iloc[-1])

                if close <= 0:
                    logger.warning("%s: precio no disponible", company.ticker)
                    failed += 1
                    continue

                hist = ticker_obj.history(period="2d")
                row = hist.iloc[-1] if not hist.empty else None

                price = StockPrice(
                    ticker=company.ticker,
                    price=close,
                    open_price=float(row.get("Open") or 0) if row is not None else 0.0,
                    high=float(row.get("High") or 0) if row is not None else 0.0,
                    low=float(row.get("Low") or 0) if row is not None else 0.0,
                    close_price=close,
                    volume=int(row.get("Volume") or 0) if row is not None else 0,
                    timestamp=datetime.now(tz=timezone.utc),
                )
                await repo.save_price(price)
                logger.info("%s: $%.2f ✓", company.ticker, close)
                ok += 1

            except Exception as e:
                logger.error("%s: %s", company.ticker, e)
                failed += 1

        await session.commit()

    logger.info("Refresh completado — %d ok / %d fallidos", ok, failed)


if __name__ == "__main__":
    asyncio.run(refresh())
