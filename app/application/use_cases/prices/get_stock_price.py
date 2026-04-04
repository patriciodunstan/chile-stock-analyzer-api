"""Use Case: Obtener precio actual de una acción.

Flujo:
1. Consulta la API de la Bolsa de Santiago
2. Persiste el precio en la DB
3. Retorna el DTO con el precio
"""

from dataclasses import dataclass

from app.application.dtos.stock_dto import StockPriceDTO
from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.repositories.stock_repository import StockRepository


@dataclass
class GetStockPriceUseCase:
    market_provider: MarketDataProvider
    stock_repository: StockRepository

    async def execute(self, ticker: str) -> StockPriceDTO:
        # 1. Obtener precio desde la Bolsa de Santiago
        price = await self.market_provider.get_price(ticker)

        # 2. Persistir en DB para historial
        await self.stock_repository.save_price(price)

        # 3. Retornar DTO
        return StockPriceDTO.from_entity(price)
