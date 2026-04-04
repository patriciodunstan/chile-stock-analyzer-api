"""Puerto de salida — proveedor de datos de mercado."""

from abc import ABC, abstractmethod
from app.domain.entities.stock import Stock, StockPrice


class MarketDataProvider(ABC):
    """Interfaz para obtener datos de mercado en tiempo real."""

    @abstractmethod
    async def get_price(self, ticker: str) -> StockPrice:
        """Obtiene precio actual de una acción."""
        pass

    @abstractmethod
    async def get_constituents(self, index: str = "IPSA") -> list[Stock]:
        """Obtiene listado de acciones de un índice."""
        pass

    @abstractmethod
    async def search(self, query: str) -> list[Stock]:
        """Busca acciones por nombre o ticker."""
        pass
