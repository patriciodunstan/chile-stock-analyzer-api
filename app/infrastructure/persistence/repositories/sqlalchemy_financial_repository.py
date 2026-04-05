"""Implementación SQLAlchemy del FinancialRepository."""
from __future__ import annotations

import logging

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.financial import FinancialStatement, FundamentalMetrics
from app.domain.repositories.financial_repository import FinancialRepository
from app.infrastructure.persistence.models.financial_model import (
    FinancialStatementModel,
    FundamentalMetricsModel,
)

logger = logging.getLogger(__name__)


def _dialect_insert(model: type, values: dict, conflict_cols: list[str]):
    """Construye un INSERT ... ON CONFLICT DO UPDATE compatible con PostgreSQL y SQLite."""
    from app.config import get_settings
    db_url = get_settings().database_url
    if "postgresql" in db_url:
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(model).values(**values)
    return stmt.on_conflict_do_update(
        index_elements=conflict_cols,
        set_={k: v for k, v in values.items() if k not in conflict_cols},
    )


class SQLAlchemyFinancialRepository(FinancialRepository):
    """Repositorio de datos financieros con SQLAlchemy async."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save_statement(self, statement: FinancialStatement) -> None:
        """Upsert: inserta o actualiza si ticker+period ya existe."""
        values = {
            "ticker": statement.ticker,
            "period": statement.period,
            "period_date": statement.period_date,
            "revenue": statement.revenue,
            "cost_of_revenue": statement.cost_of_revenue,
            "gross_profit": statement.gross_profit,
            "operating_income": statement.operating_income,
            "ebitda": statement.ebitda,
            "ebit": statement.ebit,
            "net_income": statement.net_income,
            "interest_expense": statement.interest_expense,
            "total_assets": statement.total_assets,
            "total_liabilities": statement.total_liabilities,
            "total_equity": statement.total_equity,
            "total_debt": statement.total_debt,
            "cash_and_equivalents": statement.cash_and_equivalents,
            "current_assets": statement.current_assets,
            "current_liabilities": statement.current_liabilities,
            "operating_cash_flow": statement.operating_cash_flow,
            "capital_expenditure": statement.capital_expenditure,
            "free_cash_flow": statement.free_cash_flow,
            "dividends_paid": statement.dividends_paid,
            "shares_outstanding": statement.shares_outstanding,
        }

        stmt = _dialect_insert(FinancialStatementModel, values, ["ticker", "period"])
        await self._session.execute(stmt)
        logger.info(f"Saved financial statement: {statement.ticker} {statement.period}")

    async def get_statements(
        self, ticker: str, limit: int = 20
    ) -> list[FinancialStatement]:
        query = (
            select(FinancialStatementModel)
            .where(FinancialStatementModel.ticker == ticker)
            .order_by(FinancialStatementModel.period.asc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        rows = result.scalars().all()
        return [self._model_to_entity(row) for row in rows]

    async def get_latest_statement(
        self, ticker: str
    ) -> FinancialStatement | None:
        query = (
            select(FinancialStatementModel)
            .where(FinancialStatementModel.ticker == ticker)
            .order_by(desc(FinancialStatementModel.period))
            .limit(1)
        )
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        return self._model_to_entity(row) if row else None

    async def save_metrics(self, metrics: FundamentalMetrics) -> None:
        """Upsert de métricas fundamentales."""
        values = {
            "ticker": metrics.ticker,
            "period": metrics.period,
            "pe_ratio": metrics.pe_ratio,
            "pb_ratio": metrics.pb_ratio,
            "ps_ratio": metrics.ps_ratio,
            "ev_ebitda": metrics.ev_ebitda,
            "ev_ebit": metrics.ev_ebit,
            "roe": metrics.roe,
            "roa": metrics.roa,
            "roic": metrics.roic,
            "net_margin": metrics.net_margin,
            "ebitda_margin": metrics.ebitda_margin,
            "gross_margin": metrics.gross_margin,
            "debt_to_equity": metrics.debt_to_equity,
            "debt_to_ebitda": metrics.debt_to_ebitda,
            "interest_coverage": metrics.interest_coverage,
            "current_ratio": metrics.current_ratio,
            "dividend_yield": metrics.dividend_yield,
            "payout_ratio": metrics.payout_ratio,
            "revenue_cagr_3y": metrics.revenue_cagr_3y,
            "net_income_cagr_3y": metrics.net_income_cagr_3y,
            "intrinsic_value": metrics.intrinsic_value,
            "margin_of_safety": metrics.margin_of_safety,
            "opportunity_score": metrics.opportunity_score,
        }

        stmt = _dialect_insert(FundamentalMetricsModel, values, ["ticker", "period"])
        await self._session.execute(stmt)
        logger.info(f"Saved metrics: {metrics.ticker} {metrics.period}")

    async def get_latest_metrics(
        self, ticker: str
    ) -> FundamentalMetrics | None:
        query = (
            select(FundamentalMetricsModel)
            .where(FundamentalMetricsModel.ticker == ticker)
            .order_by(desc(FundamentalMetricsModel.period))
            .limit(1)
        )
        result = await self._session.execute(query)
        row = result.scalar_one_or_none()
        if not row:
            return None

        return FundamentalMetrics(
            ticker=row.ticker,
            period=row.period,
            pe_ratio=row.pe_ratio,
            pb_ratio=row.pb_ratio,
            ps_ratio=row.ps_ratio,
            ev_ebitda=row.ev_ebitda,
            ev_ebit=row.ev_ebit,
            roe=row.roe,
            roa=row.roa,
            roic=row.roic,
            net_margin=row.net_margin,
            ebitda_margin=row.ebitda_margin,
            gross_margin=row.gross_margin,
            debt_to_equity=row.debt_to_equity,
            debt_to_ebitda=row.debt_to_ebitda,
            interest_coverage=row.interest_coverage,
            current_ratio=row.current_ratio,
            dividend_yield=row.dividend_yield,
            payout_ratio=row.payout_ratio,
            revenue_cagr_3y=row.revenue_cagr_3y,
            net_income_cagr_3y=row.net_income_cagr_3y,
            intrinsic_value=row.intrinsic_value,
            margin_of_safety=row.margin_of_safety,
            opportunity_score=row.opportunity_score,
        )

    @staticmethod
    def _model_to_entity(row: FinancialStatementModel) -> FinancialStatement:
        return FinancialStatement(
            id=row.id,
            ticker=row.ticker,
            period=row.period,
            period_date=row.period_date,
            revenue=row.revenue or 0.0,
            cost_of_revenue=row.cost_of_revenue or 0.0,
            gross_profit=row.gross_profit or 0.0,
            operating_income=row.operating_income or 0.0,
            ebitda=row.ebitda or 0.0,
            ebit=row.ebit or 0.0,
            net_income=row.net_income or 0.0,
            interest_expense=row.interest_expense or 0.0,
            total_assets=row.total_assets or 0.0,
            total_liabilities=row.total_liabilities or 0.0,
            total_equity=row.total_equity or 0.0,
            total_debt=row.total_debt or 0.0,
            cash_and_equivalents=row.cash_and_equivalents or 0.0,
            current_assets=row.current_assets or 0.0,
            current_liabilities=row.current_liabilities or 0.0,
            operating_cash_flow=row.operating_cash_flow or 0.0,
            capital_expenditure=row.capital_expenditure or 0.0,
            free_cash_flow=row.free_cash_flow or 0.0,
            dividends_paid=row.dividends_paid or 0.0,
            shares_outstanding=row.shares_outstanding or 0,
        )
