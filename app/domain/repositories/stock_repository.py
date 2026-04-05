"""Interfaz del repositorio de acciones."""
from __future__ import annotations

from abc import ABC, abstractmethod
from app.domain.entities.stock import Stock, StockPrice


class StockRepository(ABC):
    """Contrato para persistencia de datos de acciones."""

    @abstractmethod
    async def get_by_ticker(self, ticker: str) -> Stock | None:
        pass

    @abstractmethod
    async def list_active(self) -> list[Stock]:
        pass

    @abstractmethod
    async def upsert(self, stock: Stock) -> Stock:
        pass

    @abstractmethod
    async def save_price(self, price: StockPrice) -> None:
        pass

    @abstractmethod
    async def get_latest_price(self, ticker: str) -> StockPrice | None:
        pass

    @abstractmethod
    async def get_price_history(
        self, ticker: str, limit: int = 30
    ) -> list[StockPrice]:
        pass
