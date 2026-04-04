"""Use Case: Obtener historial de precios de una acción."""

from dataclasses import dataclass

from app.application.dtos.stock_dto import StockPriceDTO
from app.domain.repositories.stock_repository import StockRepository


@dataclass
class GetPriceHistoryUseCase:
    stock_repository: StockRepository

    async def execute(
        self, ticker: str, limit: int = 30
    ) -> list[StockPriceDTO]:
        """Retorna historial de precios desde la DB local."""
        prices = await self.stock_repository.get_price_history(ticker, limit)
        return [StockPriceDTO.from_entity(p) for p in prices]
