"""Use Case: Listar acciones disponibles con precios."""

from dataclasses import dataclass

from app.application.dtos.stock_dto import StockListItemDTO
from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.repositories.stock_repository import StockRepository


@dataclass
class ListStocksUseCase:
    market_provider: MarketDataProvider
    stock_repository: StockRepository

    async def execute(self, index: str = "IPSA") -> list[StockListItemDTO]:
        """Lista constituyentes de un índice con su último precio guardado."""
        # Obtener constituyentes del índice
        stocks = await self.market_provider.get_constituents(index)

        result: list[StockListItemDTO] = []
        for stock in stocks:
            # Guardar/actualizar stock en DB
            await self.stock_repository.upsert(stock)

            # Intentar obtener último precio guardado
            latest = await self.stock_repository.get_latest_price(stock.ticker)

            result.append(
                StockListItemDTO(
                    ticker=stock.ticker,
                    name=stock.name,
                    sector=stock.sector,
                    market=stock.market,
                    latest_price=latest.price if latest else None,
                    change_percent=latest.change_percent if latest else None,
                )
            )

        return result
