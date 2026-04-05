"""Endpoints de análisis y señales de inversión.

- GET /{ticker} → análisis individual
- GET /batch → análisis de todas las empresas + ranking
- GET /companies → lista de empresas disponibles
"""
import time as _time
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Any

from app.dependencies import FullAnalysisUC, BatchAnalysisUC
from app.domain.entities.company import (
    get_all_active_companies,
)

# Cache en memoria para el batch (evita recomputar en cada request)
_BATCH_CACHE_TTL = 300  # 5 minutos
_batch_cache: dict | None = None
_batch_cache_ts: float = 0.0

router = APIRouter(prefix="/analysis", tags=["analysis"])


# ============================================================
# Schemas
# ============================================================

class CompanyInfo(BaseModel):
    ticker: str
    name: str
    sector: str
    eeff_currency: str
    shares_outstanding: int
    has_data: bool = False


class CompaniesResponse(BaseModel):
    total: int
    companies: list[CompanyInfo]


class AnalysisResponse(BaseModel):
    ticker: str
    signal: str
    score: int
    market_price: float | None
    intrinsic_value: float | None
    margin_of_safety: float | None
    metrics: dict[str, Any] | None
    dcf: dict[str, Any] | None
    scoring: dict[str, Any] | None
    latest_statement: dict[str, Any] | None
    reasons: list[str]
    warnings: list[str]


class BatchSummary(BaseModel):
    total_companies: int
    analyzed: int
    buy_count: int
    hold_count: int
    sell_count: int


class RankedCompanyResponse(BaseModel):
    rank: int
    ticker: str
    name: str
    sector: str
    signal: str
    score: int
    market_price: float | None
    intrinsic_value: float | None
    margin_of_safety: float | None
    pe_ratio: float | None
    ev_ebitda: float | None
    roe: float | None
    debt_to_equity: float | None
    top_reasons: list[str]


class BatchAnalysisResponse(BaseModel):
    summary: BatchSummary
    ranking: list[RankedCompanyResponse]
    errors: list[dict[str, str]]


# ============================================================
# Endpoints
# ============================================================

@router.get(
    "/companies",
    response_model=CompaniesResponse,
    summary="Lista de empresas disponibles para análisis",
)
async def list_companies() -> CompaniesResponse:
    """Retorna todas las empresas registradas en el sistema con su metadata."""
    companies = get_all_active_companies()
    return CompaniesResponse(
        total=len(companies),
        companies=[
            CompanyInfo(
                ticker=c.ticker,
                name=c.name,
                sector=c.sector.value,
                eeff_currency=c.eeff_currency.value,
                shares_outstanding=c.shares_outstanding,
            )
            for c in companies
        ],
    )


@router.get(
    "/batch",
    response_model=BatchAnalysisResponse,
    summary="Análisis batch + ranking de todas las empresas",
    description="Analiza todas las empresas con datos financieros ingestados "
    "y retorna un ranking ordenado por score. Ideal para decidir qué comprar.",
)
async def batch_analysis(
    use_case: BatchAnalysisUC,
    sector: str | None = Query(None, description="Filtrar por sector"),
) -> BatchAnalysisResponse:
    global _batch_cache, _batch_cache_ts

    # Solo cachear cuando no hay filtro de sector (el caso más frecuente)
    use_cache = sector is None
    now = _time.monotonic()

    if use_cache and _batch_cache is not None and (now - _batch_cache_ts) < _BATCH_CACHE_TTL:
        return BatchAnalysisResponse(**_batch_cache)

    result = await use_case.execute(sector=sector)
    data = result.to_dict()

    if use_cache:
        _batch_cache = data
        _batch_cache_ts = now

    return BatchAnalysisResponse(**data)


@router.get(
    "/{ticker}",
    response_model=AnalysisResponse,
    summary="Análisis completo de una acción",
    description="Retorna señal BUY/HOLD/SELL con score 0-100, "
    "métricas fundamentales, valoración DCF, y razones detalladas. "
    "Requiere datos financieros ingestados previamente.",
)
async def full_analysis(
    ticker: str,
    use_case: FullAnalysisUC,
) -> AnalysisResponse:
    result = await use_case.execute(ticker)
    return AnalysisResponse(**result.to_dict())
