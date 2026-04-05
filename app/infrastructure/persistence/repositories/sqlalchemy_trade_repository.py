"""Implementación SQLAlchemy del repositorio de trades."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.trade import Trade, TradeStatus, TradeStrategy
from app.domain.repositories.trade_repository import TradeRepository
from app.infrastructure.persistence.models.trade_model import TradeModel


class SQLAlchemyTradeRepository(TradeRepository):

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, trade: Trade) -> Trade:
        model = _to_model(trade)
        self._session.add(model)
        await self._session.flush()
        return trade

    async def get_by_id(self, trade_id: str) -> Trade | None:
        result = await self._session.execute(
            select(TradeModel).where(TradeModel.id == trade_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def get_open_trades(self, is_paper: bool = True) -> list[Trade]:
        result = await self._session.execute(
            select(TradeModel).where(
                TradeModel.status == "OPEN",
                TradeModel.is_paper == is_paper,
            )
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def get_closed_trades(self, is_paper: bool = True, limit: int = 50) -> list[Trade]:
        result = await self._session.execute(
            select(TradeModel)
            .where(
                TradeModel.status != "OPEN",
                TradeModel.is_paper == is_paper,
            )
            .order_by(TradeModel.exit_date.desc())
            .limit(limit)
        )
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(self, trade: Trade) -> Trade:
        result = await self._session.execute(
            select(TradeModel).where(TradeModel.id == trade.id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ValueError(f"Trade {trade.id} no encontrado para actualizar")
        _update_model(model, trade)
        await self._session.flush()
        return trade


# ── Mappers ──────────────────────────────────────────────────

def _to_model(trade: Trade) -> TradeModel:
    return TradeModel(
        id=trade.id,
        ticker=trade.ticker,
        strategy=trade.strategy.value,
        entry_price=trade.entry_price,
        quantity=trade.quantity,
        entry_date=trade.entry_date,
        stop_loss=trade.stop_loss,
        take_profit=trade.take_profit,
        capital_used=trade.capital_used,
        commission_entry=trade.commission_entry,
        status=trade.status.value,
        exit_price=trade.exit_price,
        exit_date=trade.exit_date,
        commission_exit=trade.commission_exit,
        pnl=trade.pnl,
        pnl_pct=trade.pnl_pct,
        is_paper=trade.is_paper,
        notes=trade.notes,
        created_at=datetime.utcnow(),
    )


def _to_entity(model: TradeModel) -> Trade:
    return Trade(
        id=model.id,
        ticker=model.ticker,
        strategy=TradeStrategy(model.strategy),
        entry_price=model.entry_price,
        quantity=model.quantity,
        entry_date=model.entry_date,
        stop_loss=model.stop_loss,
        take_profit=model.take_profit,
        capital_used=model.capital_used,
        commission_entry=model.commission_entry,
        status=TradeStatus(model.status),
        exit_price=model.exit_price,
        exit_date=model.exit_date,
        commission_exit=model.commission_exit,
        pnl=model.pnl,
        pnl_pct=model.pnl_pct,
        is_paper=model.is_paper,
        notes=model.notes,
    )


def _update_model(model: TradeModel, trade: Trade) -> None:
    model.status = trade.status.value
    model.exit_price = trade.exit_price
    model.exit_date = trade.exit_date
    model.commission_exit = trade.commission_exit
    model.pnl = trade.pnl
    model.pnl_pct = trade.pnl_pct
    model.notes = trade.notes
