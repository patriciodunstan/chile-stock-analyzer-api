from __future__ import annotations
"""Implementación SQLAlchemy del repositorio de acciones."""

from sqlalchemy import select, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.stock import Stock, StockPrice
from app.domain.repositories.stock_repository import StockRepository
from app.infrastructure.persistence.models.stock_model import (
    StockModel,
    StockPriceModel,
)


class SQLAlchemyStockRepository(StockRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        result = await self._session.execute(
            select(StockModel).where(StockModel.ticker == ticker.upper())
        )
        model = result.scalar_one_or_none()
        return self._to_stock_entity(model) if model else None

    async def list_active(self) -> list[Stock]:
        result = await self._session.execute(
            select(StockModel)
            .where(StockModel.is_active.is_(True))
            .order_by(StockModel.ticker)
        )
        return [self._to_stock_entity(m) for m in result.scalars().all()]

    async def upsert(self, stock: Stock) -> Stock:
        existing = await self.get_by_ticker(stock.ticker)
        if existing:
            result = await self._session.execute(
                select(StockModel).where(
                    StockModel.ticker == stock.ticker.upper()
                )
            )
            model = result.scalar_one()
            model.name = stock.name
            model.sector = stock.sector
            model.market = stock.market
            model.is_active = stock.is_active
        else:
            model = StockModel(
                ticker=stock.ticker.upper(),
                name=stock.name,
                sector=stock.sector,
                market=stock.market,
                is_active=stock.is_active,
            )
            self._session.add(model)

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_stock_entity(model)

    async def save_price(self, price: StockPrice) -> None:
        model = StockPriceModel(
            ticker=price.ticker.upper(),
            price=price.price,
            open_price=price.open_price,
            high=price.high,
            low=price.low,
            close_price=price.close_price,
            volume=price.volume,
            market_cap=price.market_cap,
            change_percent=price.change_percent,
            currency=price.currency,
            timestamp=price.timestamp,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_latest_price(self, ticker: str) -> StockPrice | None:
        result = await self._session.execute(
            select(StockPriceModel)
            .where(StockPriceModel.ticker == ticker.upper())
            .order_by(desc(StockPriceModel.timestamp))
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_price_entity(model) if model else None

    async def get_price_history(
        self, ticker: str, limit: int = 30
    ) -> list[StockPrice]:
        result = await self._session.execute(
            select(StockPriceModel)
            .where(StockPriceModel.ticker == ticker.upper())
            .order_by(desc(StockPriceModel.timestamp))
            .limit(limit)
        )
        return [self._to_price_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_stock_entity(model: StockModel) -> Stock:
        return Stock(
            id=model.id,
            ticker=model.ticker,
            name=model.name,
            sector=model.sector,
            market=model.market,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_price_entity(model: StockPriceModel) -> StockPrice:
        return StockPrice(
            ticker=model.ticker,
            price=model.price,
            open_price=model.open_price,
            high=model.high,
            low=model.low,
            close_price=model.close_price,
            volume=model.volume,
            market_cap=model.market_cap,
            change_percent=model.change_percent,
            timestamp=model.timestamp,
            currency=model.currency,
        )
