"""Use Case: Calcular métricas fundamentales de una acción.

Flujo:
1. Obtener último estado financiero del repositorio
2. Obtener precio actual del market provider
3. Obtener historial de estados financieros (para CAGR)
4. Delegar cálculo al servicio de dominio MetricsCalculatorService
5. Persistir métricas calculadas
6. Retornar DTO
"""
from __future__ import annotations

from dataclasses import dataclass

from app.application.dtos.financial_dto import FundamentalMetricsDTO
from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.exceptions import InsufficientDataError, TickerNotFoundError
from app.domain.repositories.financial_repository import FinancialRepository
from app.domain.repositories.stock_repository import StockRepository
from app.domain.services.metrics_calculator import MetricsCalculatorService


@dataclass
class CalculateMetricsUseCase:
    """Orquesta el cálculo de métricas fundamentales."""

    financial_repository: FinancialRepository
    stock_repository: StockRepository
    market_provider: MarketDataProvider
    calculator: MetricsCalculatorService

    async def execute(self, ticker: str) -> FundamentalMetricsDTO:
        """Calcula métricas para un ticker dado.

        Raises:
            TickerNotFoundError: Si no se encuentra el ticker.
            InsufficientDataError: Si no hay datos financieros suficientes.
        """
        # 1. Obtener último estado financiero
        statement = await self.financial_repository.get_latest_statement(ticker)
        if statement is None:
            raise InsufficientDataError(
                f"No hay estados financieros disponibles para '{ticker}'. "
                "Ejecute primero la extracción de reportes IR."
            )

        # 2. Obtener precio actual
        try:
            price = await self.market_provider.get_price(ticker)
        except Exception:
            # Fallback: intentar desde el repositorio
            price = await self.stock_repository.get_latest_price(ticker)
            if price is None:
                raise InsufficientDataError(
                    f"No hay datos de precio disponibles para '{ticker}'."
                )

        # 3. Obtener historial para CAGR (últimos 4+ períodos)
        historical = await self.financial_repository.get_statements(ticker, limit=12)

        # 4. Calcular métricas
        metrics = self.calculator.calculate(
            statement=statement,
            price=price,
            historical_statements=historical if len(historical) >= 4 else None,
        )

        # 5. Persistir
        await self.financial_repository.save_metrics(metrics)

        # 6. Retornar DTO
        return FundamentalMetricsDTO.from_entity(metrics)
