"""Servicio de dominio: cálculo de métricas fundamentales.

Calcula ratios financieros a partir de un FinancialStatement y precio de mercado.
Sigue el principio de Single Responsibility: solo calcula, no persiste ni obtiene datos.

Métricas calculadas:
- Valorización: P/E, P/B, P/S, EV/EBITDA, EV/EBIT
- Rentabilidad: ROE, ROA, ROIC, márgenes (gross, EBITDA, net)
- Solvencia: D/E, D/EBITDA, interest coverage, current ratio
- Dividendos: yield, payout ratio
- Crecimiento: CAGR 3 años (revenue, net income)
"""
from __future__ import annotations

import logging
from typing import Sequence

from app.domain.entities.financial import FinancialStatement, FundamentalMetrics
from app.domain.entities.stock import StockPrice

logger = logging.getLogger(__name__)


class MetricsCalculatorService:
    """Calcula FundamentalMetrics a partir de datos financieros y de mercado."""

    def calculate(
        self,
        statement: FinancialStatement,
        price: StockPrice,
        historical_statements: Sequence[FinancialStatement] | None = None,
    ) -> FundamentalMetrics:
        """Calcula todas las métricas fundamentales para un período.

        Args:
            statement: Estado financiero del período actual.
            price: Precio/market cap actual de la acción.
            historical_statements: Lista histórica ordenada por período (más antiguo primero)
                                   para cálculo de CAGR. Debe incluir el statement actual.

        Returns:
            FundamentalMetrics con todos los ratios calculados.

        Note:
            Si el statement es trimestral (period contiene "Q"), los flujos del
            income statement se anualizan (×4) para que los ratios de valorización
            (P/E, EV/EBITDA, etc.) sean comparables con market_cap anual.
            Las métricas del balance (point-in-time) NO se anualizan.
        """
        metrics = FundamentalMetrics(
            ticker=statement.ticker,
            period=statement.period,
        )

        market_cap = price.market_cap if price.market_cap > 0 else None
        ev = self._enterprise_value(statement, market_cap)

        # Determinar factor de anualización
        ann = self._annualization_factor(statement.period)

        # Flujos anualizados (income statement / cash flow son flujos de período)
        revenue_ann = statement.revenue * ann
        net_income_ann = statement.net_income * ann
        ebitda_ann = statement.ebitda * ann
        ebit_ann = statement.ebit * ann
        gross_profit_ann = statement.gross_profit * ann
        interest_expense_ann = statement.interest_expense * ann
        dividends_ann = statement.dividends_paid * ann

        if ann > 1:
            logger.info(
                f"Anualización ×{ann} aplicada para {statement.ticker} "
                f"{statement.period} (trimestral → anual estimado)"
            )

        # Valorización (market_cap es anual, flujos deben ser anuales)
        metrics.pe_ratio = self._safe_divide(market_cap, net_income_ann) \
            if net_income_ann > 0 else None
        metrics.pb_ratio = self._safe_divide(market_cap, statement.total_equity)
        metrics.ps_ratio = self._safe_divide(market_cap, revenue_ann)
        metrics.ev_ebitda = self._safe_divide(ev, ebitda_ann)
        metrics.ev_ebit = self._safe_divide(ev, ebit_ann)

        # Rentabilidad (margen = flujo/flujo, no necesita ajuste; ROE/ROA = flujo anual / stock)
        metrics.roe = self._safe_divide(net_income_ann, statement.total_equity)
        metrics.roa = self._safe_divide(net_income_ann, statement.total_assets)
        metrics.roic = self._calculate_roic(statement, ann)
        metrics.net_margin = self._safe_divide(statement.net_income, statement.revenue)
        metrics.ebitda_margin = self._safe_divide(statement.ebitda, statement.revenue)
        metrics.gross_margin = self._safe_divide(statement.gross_profit, statement.revenue)

        # Solvencia (deuda es stock, EBITDA es flujo → anualizar EBITDA)
        metrics.debt_to_equity = self._safe_divide(statement.total_debt, statement.total_equity)
        metrics.debt_to_ebitda = self._safe_divide(statement.total_debt, ebitda_ann)
        abs_interest_ann = abs(interest_expense_ann)
        metrics.interest_coverage = self._safe_divide(
            ebit_ann, abs_interest_ann
        ) if abs_interest_ann > 0 else None
        metrics.current_ratio = self._safe_divide(
            statement.current_assets, statement.current_liabilities
        )

        # Dividendos
        abs_dividends = abs(dividends_ann)
        metrics.dividend_yield = self._safe_divide(abs_dividends, market_cap) \
            if abs_dividends > 0 else None
        metrics.payout_ratio = self._safe_divide(abs_dividends, net_income_ann) \
            if abs_dividends > 0 and net_income_ann > 0 else None

        # Crecimiento
        if historical_statements and len(historical_statements) >= 4:
            metrics.revenue_cagr_3y = self._cagr(
                historical_statements, "revenue", years=3,
            )
            metrics.net_income_cagr_3y = self._cagr(
                historical_statements, "net_income", years=3,
            )

        logger.info(
            f"Métricas calculadas para {statement.ticker} {statement.period}: "
            f"P/E={metrics.pe_ratio}, ROE={metrics.roe}, D/E={metrics.debt_to_equity}"
        )

        return metrics

    # ----------------------------------------------------------
    # Helpers privados
    # ----------------------------------------------------------

    @staticmethod
    def _safe_divide(
        numerator: float | None,
        denominator: float | None,
    ) -> float | None:
        """División segura: retorna None si numerador o denominador son None/0."""
        if numerator is None or denominator is None:
            return None
        if denominator == 0:
            return None
        return numerator / denominator

    @staticmethod
    def _annualization_factor(period: str) -> int:
        """Retorna el factor de anualización según el tipo de período.

        - Trimestral (contiene 'Q'): ×4
        - Semestral (contiene 'H'): ×2
        - Anual (FY o sin indicador): ×1
        """
        period_upper = period.upper()
        if "Q" in period_upper:
            return 4
        if "H" in period_upper:
            return 2
        return 1

    @staticmethod
    def _enterprise_value(
        stmt: FinancialStatement,
        market_cap: float | None,
    ) -> float | None:
        """EV = Market Cap + Deuda Total - Cash."""
        if market_cap is None:
            return None
        return market_cap + stmt.total_debt - stmt.cash_and_equivalents

    @staticmethod
    def _calculate_roic(stmt: FinancialStatement, ann: int = 1) -> float | None:
        """ROIC = NOPAT / Invested Capital.

        NOPAT = EBIT_anualizado * (1 - tax_rate_implícita)
        Invested Capital = Total Equity + Total Debt - Cash
        Tax Rate implícita = 1 - (Net Income / EBT) ≈ 1 - (Net Income / EBIT)
        """
        if stmt.ebit == 0 or stmt.total_equity == 0:
            return None

        invested_capital = stmt.total_equity + stmt.total_debt - stmt.cash_and_equivalents
        if invested_capital <= 0:
            return None

        # Tasa impositiva implícita (ratio entre flujos, no necesita anualizar)
        if stmt.ebit > 0 and stmt.net_income > 0:
            tax_rate = 1.0 - (stmt.net_income / stmt.ebit)
            tax_rate = max(0.0, min(tax_rate, 0.5))  # Clamp entre 0% y 50%
        else:
            tax_rate = 0.27  # Tasa corporativa Chile como fallback

        nopat = stmt.ebit * ann * (1.0 - tax_rate)
        return nopat / invested_capital

    @staticmethod
    def _cagr(
        statements: Sequence[FinancialStatement],
        field: str,
        years: int = 3,
    ) -> float | None:
        """Calcula CAGR para un campo dado.

        Necesita al menos years+1 períodos. Toma el primer y último valor
        de la serie.

        CAGR = (end_value / start_value) ^ (1/years) - 1
        """
        if len(statements) < years + 1:
            return None

        start_value = getattr(statements[0], field, 0)
        end_value = getattr(statements[-1], field, 0)

        if start_value <= 0 or end_value <= 0:
            return None

        return (end_value / start_value) ** (1.0 / years) - 1.0
