"""Entidades financieras — estados financieros y métricas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from app.domain.entities.base import BaseEntity


@dataclass
class FinancialStatement(BaseEntity):
    """Estado financiero trimestral/anual de una empresa."""

    ticker: str = ""
    period: str = ""  # "2024-Q4", "2024-FY"
    period_date: date | None = None

    # Estado de Resultados
    revenue: float = 0.0
    cost_of_revenue: float = 0.0
    gross_profit: float = 0.0
    operating_income: float = 0.0
    ebitda: float = 0.0
    ebit: float = 0.0
    net_income: float = 0.0
    interest_expense: float = 0.0

    # Balance General
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    total_debt: float = 0.0
    cash_and_equivalents: float = 0.0
    current_assets: float = 0.0
    current_liabilities: float = 0.0

    # Flujo de Caja
    operating_cash_flow: float = 0.0
    capital_expenditure: float = 0.0
    free_cash_flow: float = 0.0
    dividends_paid: float = 0.0

    # Shares
    shares_outstanding: int = 0

    @property
    def enterprise_value(self) -> float:
        """EV = Market Cap + Deuda - Cash (market_cap se agrega externamente)."""
        return self.total_debt - self.cash_and_equivalents


@dataclass
class FundamentalMetrics:
    """Métricas fundamentales calculadas para una empresa."""

    ticker: str = ""
    period: str = ""

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

    # Deuda
    debt_to_equity: float | None = None
    debt_to_ebitda: float | None = None
    interest_coverage: float | None = None
    current_ratio: float | None = None

    # Dividendos
    dividend_yield: float | None = None
    payout_ratio: float | None = None

    # Crecimiento (CAGR)
    revenue_cagr_3y: float | None = None
    net_income_cagr_3y: float | None = None

    # Valorización intrínseca
    intrinsic_value: float | None = None
    margin_of_safety: float | None = None
    opportunity_score: float | None = None
