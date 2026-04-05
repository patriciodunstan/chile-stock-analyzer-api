"""Schemas Pydantic para endpoints financieros."""
from pydantic import BaseModel


class FinancialStatementResponse(BaseModel):
    """Respuesta con estado financiero."""

    ticker: str
    period: str

    # Income Statement
    revenue: float = 0.0
    cost_of_revenue: float = 0.0
    gross_profit: float = 0.0
    operating_income: float = 0.0
    ebitda: float = 0.0
    net_income: float = 0.0

    # Balance Sheet
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    total_debt: float = 0.0
    cash_and_equivalents: float = 0.0

    # Cash Flow
    operating_cash_flow: float = 0.0
    free_cash_flow: float = 0.0
    dividends_paid: float = 0.0


class FundamentalMetricsResponse(BaseModel):
    """Respuesta con métricas fundamentales calculadas."""

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


class FinancialStatementsListResponse(BaseModel):
    """Lista de estados financieros."""

    ticker: str
    statements: list[FinancialStatementResponse]
    count: int


class MetricsComparisonItem(BaseModel):
    """Métricas de un ticker para comparación."""

    ticker: str
    period: str
    pe_ratio: float | None = None
    roe: float | None = None
    debt_to_equity: float | None = None
    ev_ebitda: float | None = None
    net_margin: float | None = None
    dividend_yield: float | None = None
    opportunity_score: float | None = None


class MetricsComparisonResponse(BaseModel):
    """Respuesta de comparación multi-ticker."""

    tickers: list[MetricsComparisonItem]
    count: int
