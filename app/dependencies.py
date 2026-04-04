"""Dependency Injection container para FastAPI."""

from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database import async_session_factory
from app.infrastructure.persistence.repositories.sqlalchemy_stock_repository import (
    SQLAlchemyStockRepository,
)
from app.infrastructure.persistence.repositories.sqlalchemy_financial_repository import (
    SQLAlchemyFinancialRepository,
)
from app.infrastructure.external.banco_central.client import BancoCentralClient
from app.infrastructure.external.composite_provider import (
    CompositeMarketProvider,
    build_composite_provider,
)
from app.domain.repositories.stock_repository import StockRepository
from app.domain.repositories.financial_repository import FinancialRepository
from app.domain.services.metrics_calculator import MetricsCalculatorService
from app.application.interfaces.market_data_provider import MarketDataProvider
from app.application.interfaces.macro_data_provider import MacroDataProvider
from app.application.use_cases.prices.get_stock_price import GetStockPriceUseCase
from app.application.use_cases.prices.list_stocks import ListStocksUseCase
from app.application.use_cases.prices.get_price_history import GetPriceHistoryUseCase
from app.application.use_cases.metrics.calculate_metrics import CalculateMetricsUseCase
from app.application.use_cases.reports.ingest_financials import IngestFinancialsUseCase
from app.application.use_cases.valuation.full_analysis import FullAnalysisUseCase
from app.application.use_cases.valuation.batch_analysis import BatchAnalysisUseCase
from app.domain.services.dcf_valuation import DCFValuationService
from app.domain.services.opportunity_scoring import OpportunityScoringService


# --- DB Session ---
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DBSession = Annotated[AsyncSession, Depends(get_db)]


# --- Repositories ---
def get_stock_repository(db: DBSession) -> StockRepository:
    return SQLAlchemyStockRepository(db)


StockRepo = Annotated[StockRepository, Depends(get_stock_repository)]


def get_financial_repository(db: DBSession) -> FinancialRepository:
    return SQLAlchemyFinancialRepository(db)


FinancialRepo = Annotated[FinancialRepository, Depends(get_financial_repository)]


# --- External Providers ---
# Singleton del composite provider (se crea una vez)
_composite_provider: CompositeMarketProvider | None = None


def get_market_provider() -> CompositeMarketProvider:
    global _composite_provider
    if _composite_provider is None:
        _composite_provider = build_composite_provider()
    return _composite_provider


def get_macro_provider() -> MacroDataProvider:
    return BancoCentralClient()


MarketProvider = Annotated[CompositeMarketProvider, Depends(get_market_provider)]
MacroProvider = Annotated[MacroDataProvider, Depends(get_macro_provider)]


# --- Use Cases ---
def get_stock_price_use_case(
    market: MarketProvider, repo: StockRepo
) -> GetStockPriceUseCase:
    return GetStockPriceUseCase(market_provider=market, stock_repository=repo)


def get_list_stocks_use_case(
    market: MarketProvider, repo: StockRepo
) -> ListStocksUseCase:
    return ListStocksUseCase(market_provider=market, stock_repository=repo)


def get_price_history_use_case(repo: StockRepo) -> GetPriceHistoryUseCase:
    return GetPriceHistoryUseCase(stock_repository=repo)


def get_calculate_metrics_use_case(
    fin_repo: FinancialRepo,
    stock_repo: StockRepo,
    market: MarketProvider,
) -> CalculateMetricsUseCase:
    return CalculateMetricsUseCase(
        financial_repository=fin_repo,
        stock_repository=stock_repo,
        market_provider=market,
        calculator=MetricsCalculatorService(),
    )


def get_ingest_financials_use_case(
    fin_repo: FinancialRepo,
) -> IngestFinancialsUseCase:
    return IngestFinancialsUseCase(financial_repository=fin_repo)


GetStockPriceUC = Annotated[GetStockPriceUseCase, Depends(get_stock_price_use_case)]
ListStocksUC = Annotated[ListStocksUseCase, Depends(get_list_stocks_use_case)]
GetPriceHistoryUC = Annotated[GetPriceHistoryUseCase, Depends(get_price_history_use_case)]
CalculateMetricsUC = Annotated[CalculateMetricsUseCase, Depends(get_calculate_metrics_use_case)]
def get_full_analysis_use_case(
    fin_repo: FinancialRepo,
    stock_repo: StockRepo,
    market: MarketProvider,
) -> FullAnalysisUseCase:
    return FullAnalysisUseCase(
        financial_repository=fin_repo,
        stock_repository=stock_repo,
        market_provider=market,
        metrics_calculator=MetricsCalculatorService(),
        dcf_service=DCFValuationService(),
        scoring_service=OpportunityScoringService(),
    )


def get_batch_analysis_use_case(
    full_analysis: FullAnalysisUseCase = Depends(get_full_analysis_use_case),
) -> BatchAnalysisUseCase:
    return BatchAnalysisUseCase(full_analysis=full_analysis)


IngestFinancialsUC = Annotated[IngestFinancialsUseCase, Depends(get_ingest_financials_use_case)]
FullAnalysisUC = Annotated[FullAnalysisUseCase, Depends(get_full_analysis_use_case)]
BatchAnalysisUC = Annotated[BatchAnalysisUseCase, Depends(get_batch_analysis_use_case)]
