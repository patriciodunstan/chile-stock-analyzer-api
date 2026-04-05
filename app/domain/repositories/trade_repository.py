"""Puerto de salida — repositorio de trades de swing trading."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.trade import Trade


class TradeRepository(ABC):

    @abstractmethod
    async def save(self, trade: Trade) -> Trade:
        pass

    @abstractmethod
    async def get_by_id(self, trade_id: str) -> Trade | None:
        pass

    @abstractmethod
    async def get_open_trades(self, is_paper: bool = True) -> list[Trade]:
        pass

    @abstractmethod
    async def get_closed_trades(self, is_paper: bool = True, limit: int = 50) -> list[Trade]:
        pass

    @abstractmethod
    async def update(self, trade: Trade) -> Trade:
        pass
