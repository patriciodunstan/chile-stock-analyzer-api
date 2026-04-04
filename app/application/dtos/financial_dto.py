"""DTOs para datos financieros y métricas fundamentales."""
from __future__ import annotations

from dataclasses import dataclass, asdict

from app.domain.entities.financial import FinancialStatement, FundamentalMetrics


@dataclass
class FinancialStatementDTO:
    """DTO para transferir datos de estado financiero."""

    ticker: str
    period: str

    # Income Statement
    revenue: float
    cost_of_revenue: float
    gross_profit: float
    operating_income: float
    ebitda: float
    net_income: float

    # Balance Sheet
    total_assets: float
    total_liabilities: float
    total_equity: float
    total_debt: float
    cash_and_equivalents: float

    # Cash Flow
    operating_cash_flow: float
    free_cash_flow: float
    dividends_paid: float

    @classmethod
    def from_entity(cls, entity: FinancialStatement) -> FinancialStatementDTO:
        return cls(
            ticker=entity.ticker,
            period=entity.period,
            revenue=entity.revenue,
            cost_of_revenue=entity.cost_of_revenue,
            gross_profit=entity.gross_profit,
            operating_income=entity.operating_income,
            ebitda=entity.ebitda,
            net_income=entity.net_income,
            total_assets=entity.total_assets,
            total_liabilities=entity.total_liabilities,
            total_equity=entity.total_equity,
            total_debt=entity.total_debt,
            cash_and_equivalents=entity.cash_and_equivalents,
            operating_cash_flow=entity.operating_cash_flow,
            free_cash_flow=entity.free_cash_flow,
            dividends_paid=entity.dividends_paid,
        )


@dataclass
class FundamentalMetricsDTO:
    """DTO para transferir métricas fundamentales calculadas."""

    ticker: str
    period: str

    # Valorización
    pe_ratio: float | None = None
    pb_ratio: float | None = None
    ps_ratio: float | None = None
    ev_ebitda: float | None = None
    ev_ebit: float | None = None

    # Rentabilidad
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    net_margin: float | None = None
    ebitda_margin: float | None = None
    gross_margin: float | None = None

    # Solvencia
    debt_to_equity: float | None = None
    debt_to_ebitda: float | None = None
    interest_coverage: float | None = None
    current_ratio: float | None = None

    # Dividendos
    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # Crecimiento
    revenue_cagr_3y: float | None = None
    net_income_cagr_3y: float | None = None

    # Valorización intrínseca
    intrinsic_value: float | None = None
    margin_of_safety: float | None = None
    opportunity_score: float | None = None

    @classmethod
    def from_entity(cls, entity: FundamentalMetrics) -> FundamentalMetricsDTO:
        return cls(
            ticker=entity.ticker,
            period=entity.period,
            pe_ratio=entity.pe_ratio,
            pb_ratio=entity.pb_ratio,
            ps_ratio=entity.ps_ratio,
            ev_ebitda=entity.ev_ebitda,
            ev_ebit=entity.ev_ebit,
            roe=entity.roe,
            roa=entity.roa,
            roic=entity.roic,
            net_margin=entity.net_margin,
            ebitda_margin=entity.ebitda_margin,
            gross_margin=entity.gross_margin,
            debt_to_equity=entity.debt_to_equity,
            debt_to_ebitda=entity.debt_to_ebitda,
            interest_coverage=entity.interest_coverage,
            current_ratio=entity.current_ratio,
            dividend_yield=entity.dividend_yield,
            payout_ratio=entity.payout_ratio,
            revenue_cagr_3y=entity.revenue_cagr_3y,
            net_income_cagr_3y=entity.net_income_cagr_3y,
            intrinsic_value=entity.intrinsic_value,
            margin_of_safety=entity.margin_of_safety,
            opportunity_score=entity.opportunity_score,
        )

    def to_dict(self) -> dict:
        return asdict(self)
