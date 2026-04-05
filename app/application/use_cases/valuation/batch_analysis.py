"""Use Case: Análisis batch de múltiples empresas + ranking comparativo.

Orquesta FullAnalysisUseCase para todas las empresas activas del Company Registry,
luego genera un ranking ordenado por score para responder: "¿cuál comprar?"

Endpoint target: GET /api/v1/analysis/batch
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.domain.entities.company import get_all_active_companies, Company
from app.application.use_cases.valuation.full_analysis import (
    FullAnalysisUseCase,
    AnalysisResult,
)

logger = logging.getLogger(__name__)


@dataclass
class RankedCompany:
    """Resultado resumido de una empresa en el ranking."""

    rank: int
    ticker: str
    name: str
    sector: str
    signal: str              # BUY | HOLD | SELL
    score: int               # 0-100
    market_price: float | None
    intrinsic_value: float | None
    margin_of_safety: float | None
    pe_ratio: float | None
    ev_ebitda: float | None
    roe: float | None
    debt_to_equity: float | None
    top_reasons: list[str]   # Top 3 razones

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "signal": self.signal,
            "score": self.score,
            "market_price": self.market_price,
            "intrinsic_value": self.intrinsic_value,
            "margin_of_safety": self.margin_of_safety,
            "pe_ratio": self.pe_ratio,
            "ev_ebitda": self.ev_ebitda,
            "roe": self.roe,
            "debt_to_equity": self.debt_to_equity,
            "top_reasons": self.top_reasons,
        }


@dataclass
class BatchAnalysisResult:
    """Resultado del análisis batch con ranking."""

    total_companies: int
    analyzed: int
    buy_count: int
    hold_count: int
    sell_count: int
    ranking: list[RankedCompany]
    errors: list[dict[str, str]]

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_companies": self.total_companies,
                "analyzed": self.analyzed,
                "buy_count": self.buy_count,
                "hold_count": self.hold_count,
                "sell_count": self.sell_count,
            },
            "ranking": [r.to_dict() for r in self.ranking],
            "errors": self.errors,
        }


@dataclass
class BatchAnalysisUseCase:
    """Analiza todas las empresas activas y genera ranking comparativo."""

    full_analysis: FullAnalysisUseCase

    async def execute(
        self,
        tickers: list[str] | None = None,
        sector: str | None = None,
    ) -> BatchAnalysisResult:
        """Ejecuta análisis batch.

        Args:
            tickers: Lista específica de tickers (None = todas las activas)
            sector: Filtrar por sector (None = todos)

        Returns:
            BatchAnalysisResult con ranking ordenado por score descendente.
        """
        # Determinar empresas a analizar
        companies = get_all_active_companies()

        if tickers:
            tickers_upper = [t.upper() for t in tickers]
            companies = [c for c in companies if c.ticker in tickers_upper]

        if sector:
            companies = [c for c in companies if c.sector.value.lower() == sector.lower()]

        if not companies:
            return BatchAnalysisResult(
                total_companies=0, analyzed=0,
                buy_count=0, hold_count=0, sell_count=0,
                ranking=[], errors=[],
            )

        # Ejecutar análisis en paralelo con semáforo para limitar concurrencia
        sem = asyncio.Semaphore(5)

        async def analyze_one(
            company: Company,
        ) -> tuple[Company, AnalysisResult | None, str | None]:
            async with sem:
                try:
                    result = await self.full_analysis.execute(company.ticker)
                    return (company, result, None)
                except Exception as e:
                    logger.error(f"Error analizando {company.ticker}: {e}")
                    return (company, None, str(e))

        results: list[tuple[Company, AnalysisResult | None, str | None]] = list(
            await asyncio.gather(*[analyze_one(c) for c in companies])
        )

        # Construir ranking
        ranked: list[RankedCompany] = []
        errors: list[dict[str, str]] = []

        for company, result, error in results:
            if error or result is None:
                errors.append({
                    "ticker": company.ticker,
                    "error": error or "Resultado vacío",
                })
                continue

            if result.signal == "N/A":
                errors.append({
                    "ticker": company.ticker,
                    "error": result.reasons[0] if result.reasons else "Sin datos",
                })
                continue

            metrics = result.metrics or {}
            ranked.append(RankedCompany(
                rank=0,  # Se asigna después de ordenar
                ticker=company.ticker,
                name=company.name,
                sector=company.sector.value,
                signal=result.signal,
                score=result.score,
                market_price=result.market_price,
                intrinsic_value=result.intrinsic_value,
                margin_of_safety=result.margin_of_safety,
                pe_ratio=_round(metrics.get("pe_ratio")),
                ev_ebitda=_round(metrics.get("ev_ebitda")),
                roe=_round(metrics.get("roe"), 4),
                debt_to_equity=_round(metrics.get("debt_to_equity")),
                top_reasons=result.reasons[:3],
            ))

        # Ordenar por score descendente (mejor primero)
        ranked.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(ranked, 1):
            r.rank = i

        buy_count = sum(1 for r in ranked if r.signal == "BUY")
        hold_count = sum(1 for r in ranked if r.signal == "HOLD")
        sell_count = sum(1 for r in ranked if r.signal == "SELL")

        logger.info(
            f"Batch analysis completado: {len(ranked)} empresas analizadas, "
            f"BUY={buy_count}, HOLD={hold_count}, SELL={sell_count}"
        )

        return BatchAnalysisResult(
            total_companies=len(companies),
            analyzed=len(ranked),
            buy_count=buy_count,
            hold_count=hold_count,
            sell_count=sell_count,
            ranking=ranked,
            errors=errors,
        )


def _round(value: float | None, decimals: int = 2) -> float | None:
    """Round helper que maneja None."""
    return round(value, decimals) if value is not None else None
