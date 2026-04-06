"""Carga inicial: 90 días de precios históricos desde yfinance para los 10 tickers.

Uso (una sola vez, desde la raíz del proyecto):
    DATABASE_URL=<url> python scripts/seed_price_history.py

En Railway: ejecutar desde la consola del servicio API como one-off command.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yfinance as yf

from app.domain.entities.company import COMPANY_REGISTRY
from app.domain.entities.stock import StockPrice
from app.infrastructure.persistence.database import async_session_factory, init_db
from app.infrastructure.persistence.repositories.sqlalchemy_stock_repository import (
    SQLAlchemyStockRepository,
)

DAYS = 90


async def seed() -> None:
    await init_db()
    companies = list(COMPANY_REGISTRY.values())
    total = 0

    async with async_session_factory() as session:
        repo = SQLAlchemyStockRepository(session)

        for company in companies:
            yf_ticker = company.yahoo_ticker or f"{company.ticker}.SN"
            print(f"  {company.ticker} ({yf_ticker})...", end=" ", flush=True)
            try:
                hist = yf.Ticker(yf_ticker).history(period=f"{DAYS}d")
                if hist.empty:
                    print("sin datos en yfinance")
                    continue

                count = 0
                for ts, row in hist.iterrows():
                    close = float(row["Close"])
                    if close <= 0:
                        continue

                    dt = ts.to_pydatetime()
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    price = StockPrice(
                        ticker=company.ticker,
                        price=close,
                        open_price=float(row.get("Open") or 0),
                        high=float(row.get("High") or 0),
                        low=float(row.get("Low") or 0),
                        close_price=close,
                        volume=int(row.get("Volume") or 0),
                        timestamp=dt,
                    )
                    await repo.save_price(price)
                    count += 1

                total += count
                print(f"{count} días cargados")

            except Exception as e:
                print(f"ERROR: {e}")

        await session.commit()

    print(f"\n✅ Seed completado: {total} registros insertados para {len(companies)} tickers")


if __name__ == "__main__":
    asyncio.run(seed())
