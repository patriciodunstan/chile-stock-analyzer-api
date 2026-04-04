from __future__ import annotations
"""Interfaz del repositorio de datos financieros."""

from abc import ABC, abstractmethod
from app.domain.entities.financial import FinancialStatement, FundamentalMetrics


class FinancialRepository(ABC):
    """Contrato para persistencia de datos financieros."""

    @abstractmethod
    async def save_statement(self, statement: FinancialStatement) -> None:
        pass

    @abstractmethod
    async def get_statements(
        self, ticker: str, limit: int = 20
    ) -> list[FinancialStatement]:
        pass

    @abstractmethod
    async def get_latest_statement(
        self, ticker: str
    ) -> FinancialStatement | None:
        pass

    @abstractmethod
    async def save_metrics(self, metrics: FundamentalMetrics) -> None:
        pass

    @abstractmethod
    async def get_latest_metrics(
        self, ticker: str
    ) -> FundamentalMetrics | None:
        pass
