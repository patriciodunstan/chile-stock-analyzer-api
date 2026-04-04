"""Modelos SQLAlchemy para datos financieros y métricas."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.database import Base


class FinancialStatementModel(Base):
    __tablename__ = "financial_statements"
    __table_args__ = (
        Index("ix_fin_stmt_ticker_period", "ticker", "period", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Income Statement
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    cost_of_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    gross_profit: Mapped[float] = mapped_column(Float, default=0.0)
    operating_income: Mapped[float] = mapped_column(Float, default=0.0)
    ebitda: Mapped[float] = mapped_column(Float, default=0.0)
    ebit: Mapped[float] = mapped_column(Float, default=0.0)
    net_income: Mapped[float] = mapped_column(Float, default=0.0)
    interest_expense: Mapped[float] = mapped_column(Float, default=0.0)

    # Balance Sheet
    total_assets: Mapped[float] = mapped_column(Float, default=0.0)
    total_liabilities: Mapped[float] = mapped_column(Float, default=0.0)
    total_equity: Mapped[float] = mapped_column(Float, default=0.0)
    total_debt: Mapped[float] = mapped_column(Float, default=0.0)
    cash_and_equivalents: Mapped[float] = mapped_column(Float, default=0.0)
    current_assets: Mapped[float] = mapped_column(Float, default=0.0)
    current_liabilities: Mapped[float] = mapped_column(Float, default=0.0)

    # Cash Flow
    operating_cash_flow: Mapped[float] = mapped_column(Float, default=0.0)
    capital_expenditure: Mapped[float] = mapped_column(Float, default=0.0)
    free_cash_flow: Mapped[float] = mapped_column(Float, default=0.0)
    dividends_paid: Mapped[float] = mapped_column(Float, default=0.0)

    shares_outstanding: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FundamentalMetricsModel(Base):
    __tablename__ = "fundamental_metrics"
    __table_args__ = (
        Index("ix_metrics_ticker_period", "ticker", "period", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(20), nullable=False)

    # Valuation
    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ps_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebit: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Profitability
    roe: Mapped[float | None] = mapped_column(Float, nullable=True)
    roa: Mapped[float | None] = mapped_column(Float, nullable=True)
    roic: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    ebitda_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Leverage
    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Dividends
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    payout_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Growth
    revenue_cagr_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income_cagr_3y: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Intrinsic value
    intrinsic_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    margin_of_safety: Mapped[float | None] = mapped_column(Float, nullable=True)
    opportunity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
