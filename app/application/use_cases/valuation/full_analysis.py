"""Use Case: Análisis completo de una acción.

Orquesta: Financial Data → Metrics → DCF → Scoring → Resultado.
Endpoint target: GET /api/v1/analysis/{ticker}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.domain.entities.company import (
    get_company,
    get_all_active_companies,
)
from app.domain.entities.financial import FundamentalMetrics
from app.domain.repositories.financial_repository import FinancialRepository
from app.domain.repositories.stock_repository import StockRepository
from app.domain.services.dcf_valuation import (
    DCFValuationService,
    DCFResult,
)
from app.domain.services.metrics_calculator import MetricsCalculatorService
from app.domain.services.opportunity_scoring import (
    OpportunityScoringService,
    ScoringResult,
)
from app.application.interfaces.market_data_provider import MarketDataProvider

logger = logging.getLogger(__name__)

# Tipo de cambio USD/CLP (se debería obtener de API, hardcoded por ahora)
# TODO: obtener de Banco Central o Yahoo Finance dinámicamente
_USD_CLP_RATE = 920.0  # Aproximado marzo 2026


@dataclass
class AnalysisResult:
    """Resultado completo del análisis de una acción."""

    ticker: str
    signal: str                  # BUY | HOLD | SELL
    score: int                   # 0-100
    market_price: float | None
    intrinsic_value: float | None
    margin_of_safety: float | None

    # Sub-resultados
    metrics: dict[str, Any] | None
    dcf: dict[str, Any] | None
    scoring: dict[str, Any] | None
    latest_statement: dict[str, Any] | None

    reasons: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "signal": self.signal,
            "score": self.score,
            "market_price": self.market_price,
            "intrinsic_value": self.intrinsic_value,
            "margin_of_safety": self.margin_of_safety,
            "metrics": self.metrics,
            "dcf": self.dcf,
            "scoring": self.scoring,
            "latest_statement": self.latest_statement,
            "reasons": self.reasons,
            "warnings": self.warnings,
        }


@dataclass
class FullAnalysisUseCase:
    """Orquesta el análisis completo de una acción."""

    financial_repository: FinancialRepository
    stock_repository: StockRepository
    market_provider: MarketDataProvider
    metrics_calculator: MetricsCalculatorService
    dcf_service: DCFValuationService
    scoring_service: OpportunityScoringService

    async def execute(self, ticker: str) -> AnalysisResult:
        """Ejecuta análisis completo para un ticker.

        Flujo resiliente: si algún paso falla, continúa con lo que hay.
        """
        ticker = ticker.upper()
        reasons: list[str] = []
        warnings: list[str] = []

        # 0. Obtener configuración de la empresa del Company Registry
        company = get_company(ticker)
        if company is None:
            return AnalysisResult(
                ticker=ticker, signal="N/A", score=0,
                market_price=None, intrinsic_value=None,
                margin_of_safety=None, metrics=None, dcf=None,
                scoring=None, latest_statement=None,
                reasons=[f"Empresa '{ticker}' no registrada. Empresas disponibles: "
                         f"{', '.join(c.ticker for c in get_all_active_companies())}"],
                warnings=[],
            )

        # 1. Obtener datos financieros
        statement = await self.financial_repository.get_latest_statement(ticker)
        if statement is None:
            return AnalysisResult(
                ticker=ticker, signal="N/A", score=0,
                market_price=None, intrinsic_value=None,
                margin_of_safety=None, metrics=None, dcf=None,
                scoring=None, latest_statement=None,
                reasons=[f"Sin datos financieros para {company.name}. Ejecute ingesta primero."],
                warnings=[],
            )

        historical = await self.financial_repository.get_statements(ticker, limit=12)

        # 2. Obtener precio de mercado
        market_price: float | None = None
        try:
            price_data = await self.market_provider.get_price(ticker)
            market_price = price_data.price
        except Exception as e:
            warnings.append(f"No se pudo obtener precio de mercado: {e}")
            # Intentar desde DB
            price_data = await self.stock_repository.get_latest_price(ticker)
            if price_data:
                market_price = price_data.price

        # 3. Normalizar moneda (EEFF USD vs market CLP) usando Company Registry
        eeff_currency = company.eeff_currency.value
        price_currency = getattr(price_data, "currency", "CLP") if price_data else "CLP"

        fx_rate = 1.0
        market_price_normalized = market_price
        market_cap_normalized = getattr(price_data, "market_cap", 0) if price_data else 0

        if eeff_currency == "USD" and price_currency == "CLP" and market_price:
            fx_rate = _USD_CLP_RATE
            market_price_normalized = market_price / fx_rate
            market_cap_normalized = market_cap_normalized / fx_rate
            reasons.append(
                f"Conversión: precio {market_price:,.0f} CLP → "
                f"{market_price_normalized:,.2f} USD (TC={fx_rate:,.0f})"
            )

        # market_cap en misma unidad que EEFF (millones)
        market_cap_millions = market_cap_normalized / 1_000_000 if market_cap_normalized else 0

        # 3b. Calcular métricas fundamentales
        metrics_result: FundamentalMetrics | None = None
        if market_price_normalized and market_price_normalized > 0:
            try:
                from app.domain.entities.stock import StockPrice
                price_obj = StockPrice(
                    ticker=ticker,
                    price=market_price_normalized,
                    market_cap=market_cap_millions,
                    currency=eeff_currency,
                )
                metrics_result = self.metrics_calculator.calculate(
                    statement=statement,
                    price=price_obj,
                    historical_statements=historical if len(historical) >= 4 else None,
                )
            except Exception as e:
                warnings.append(f"Error calculando métricas: {e}")
        else:
            warnings.append("Sin precio de mercado → métricas de valorización no disponibles")

        # 4. DCF Valuation — shares desde Company Registry
        dcf_result: DCFResult | None = None
        shares = company.shares_outstanding

        if shares > 0 and market_price_normalized and market_price_normalized > 0:
            try:
                dcf_result = self.dcf_service.calculate(
                    latest=statement,
                    historical=historical,
                    shares_outstanding=shares,
                    market_price=market_price_normalized,
                )
                reasons.extend(dcf_result.reasons)
            except Exception as e:
                warnings.append(f"Error en DCF: {e}")
        else:
            if shares == 0:
                warnings.append(f"Shares outstanding no configuradas para {ticker}")
            if not market_price:
                warnings.append("Sin precio de mercado para DCF")

        # 5. Scoring
        scoring_result: ScoringResult | None = None
        if metrics_result:
            try:
                scoring_result = self.scoring_service.score(
                    metrics=metrics_result,
                    dcf=dcf_result,
                )
                reasons.extend(scoring_result.reasons)
            except Exception as e:
                warnings.append(f"Error en scoring: {e}")

        # 6. Construir resultado
        signal = "N/A"
        score = 0
        intrinsic = None
        mos = None

        if scoring_result:
            signal = scoring_result.signal
            score = scoring_result.score

        if dcf_result:
            # Convertir intrinsic value de vuelta a moneda de mercado (CLP)
            intrinsic = dcf_result.intrinsic_value_per_share * fx_rate
            mos = dcf_result.margin_of_safety

        # Statement summary
        stmt_dict = {
            "period": statement.period,
            "revenue": statement.revenue,
            "ebitda": statement.ebitda,
            "net_income": statement.net_income,
            "total_assets": statement.total_assets,
            "total_equity": statement.total_equity,
            "total_debt": statement.total_debt,
            "cash": statement.cash_and_equivalents,
        } if statement else None

        return AnalysisResult(
            ticker=ticker,
            signal=signal,
            score=score,
            market_price=market_price,
            intrinsic_value=round(intrinsic, 2) if intrinsic else None,
            margin_of_safety=round(mos, 2) if mos else None,
            metrics=self._metrics_to_dict(metrics_result) if metrics_result else None,
            dcf=dcf_result.to_dict() if dcf_result else None,
            scoring=scoring_result.to_dict() if scoring_result else None,
            latest_statement=stmt_dict,
            reasons=reasons,
            warnings=warnings,
        )

    @staticmethod
    def _metrics_to_dict(m: FundamentalMetrics) -> dict:
        return {
            "pe_ratio": m.pe_ratio,
            "pb_ratio": m.pb_ratio,
            "ps_ratio": m.ps_ratio,
            "ev_ebitda": m.ev_ebitda,
            "ev_ebit": m.ev_ebit,
            "roe": m.roe,
            "roa": m.roa,
            "roic": m.roic,
            "net_margin": m.net_margin,
            "ebitda_margin": m.ebitda_margin,
            "gross_margin": m.gross_margin,
            "debt_to_equity": m.debt_to_equity,
            "debt_to_ebitda": m.debt_to_ebitda,
            "interest_coverage": m.interest_coverage,
            "current_ratio": m.current_ratio,
            "dividend_yield": m.dividend_yield,
            "revenue_cagr_3y": m.revenue_cagr_3y,
        }
