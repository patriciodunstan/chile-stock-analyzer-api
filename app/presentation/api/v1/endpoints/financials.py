"""Endpoints de datos financieros y métricas — HU-004, HU-IR-006."""

from pathlib import Path

from fastapi import APIRouter, Query, UploadFile, File, Form
from pydantic import BaseModel
from typing import Annotated

from app.dependencies import (
    CalculateMetricsUC,
    FinancialRepo,
    MarketProvider,
    IngestFinancialsUC,
)
from app.presentation.schemas.financial import (
    FundamentalMetricsResponse,
    FinancialStatementResponse,
    FinancialStatementsListResponse,
)

router = APIRouter(prefix="/financials", tags=["financials"])


class IngestResponse(BaseModel):
    ticker: str
    source_file: str
    success: bool
    periods_processed: list[str]
    statements_saved: int
    fields_mapped: dict[str, int]
    warnings: list[str]
    errors: list[str]


class IngestFromPathRequest(BaseModel):
    file_path: str
    ticker: str


@router.get(
    "/{ticker}/metrics",
    response_model=FundamentalMetricsResponse,
    summary="Calcular métricas fundamentales",
    description="Calcula P/E, ROE, D/E, EV/EBITDA, márgenes y más "
    "a partir del último estado financiero y precio de mercado.",
)
async def get_metrics(
    ticker: str,
    use_case: CalculateMetricsUC,
) -> FundamentalMetricsResponse:
    dto = await use_case.execute(ticker.upper())
    return FundamentalMetricsResponse(**dto.to_dict())


@router.get(
    "/{ticker}/statements",
    response_model=FinancialStatementsListResponse,
    summary="Obtener estados financieros históricos",
    description="Retorna los estados financieros almacenados (Income Statement, "
    "Balance Sheet, Cash Flow) para un ticker.",
)
async def get_statements(
    ticker: str,
    repo: FinancialRepo,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> FinancialStatementsListResponse:
    statements = await repo.get_statements(ticker.upper(), limit=limit)
    return FinancialStatementsListResponse(
        ticker=ticker.upper(),
        statements=[
            FinancialStatementResponse(
                ticker=s.ticker,
                period=s.period,
                revenue=s.revenue,
                cost_of_revenue=s.cost_of_revenue,
                gross_profit=s.gross_profit,
                operating_income=s.operating_income,
                ebitda=s.ebitda,
                net_income=s.net_income,
                total_assets=s.total_assets,
                total_liabilities=s.total_liabilities,
                total_equity=s.total_equity,
                total_debt=s.total_debt,
                cash_and_equivalents=s.cash_and_equivalents,
                operating_cash_flow=s.operating_cash_flow,
                free_cash_flow=s.free_cash_flow,
                dividends_paid=s.dividends_paid,
            )
            for s in statements
        ],
        count=len(statements),
    )


@router.get(
    "/{ticker}/latest",
    response_model=FinancialStatementResponse,
    summary="Último estado financiero",
    description="Retorna el estado financiero más reciente para un ticker.",
)
async def get_latest_statement(
    ticker: str,
    repo: FinancialRepo,
) -> FinancialStatementResponse:
    from app.domain.exceptions import InsufficientDataError

    stmt = await repo.get_latest_statement(ticker.upper())
    if stmt is None:
        raise InsufficientDataError(
            f"No hay estados financieros para '{ticker}'."
        )
    return FinancialStatementResponse(
        ticker=stmt.ticker,
        period=stmt.period,
        revenue=stmt.revenue,
        cost_of_revenue=stmt.cost_of_revenue,
        gross_profit=stmt.gross_profit,
        operating_income=stmt.operating_income,
        ebitda=stmt.ebitda,
        net_income=stmt.net_income,
        total_assets=stmt.total_assets,
        total_liabilities=stmt.total_liabilities,
        total_equity=stmt.total_equity,
        total_debt=stmt.total_debt,
        cash_and_equivalents=stmt.cash_and_equivalents,
        operating_cash_flow=stmt.operating_cash_flow,
        free_cash_flow=stmt.free_cash_flow,
        dividends_paid=stmt.dividends_paid,
    )


# ============================================================
# Ingesta de datos
# ============================================================


@router.post(
    "/{ticker}/ingest",
    response_model=IngestResponse,
    summary="Ingestar datos desde XLSX (upload)",
    description="Sube un archivo XLSX de earnings release y extrae los "
    "estados financieros al sistema. Soporta formato Q4Web/Nasdaq IR.",
)
async def ingest_from_upload(
    ticker: str,
    use_case: IngestFinancialsUC,
    file: UploadFile = File(..., description="Archivo XLSX de earnings release"),
) -> IngestResponse:
    import tempfile

    # Guardar upload a archivo temporal
    suffix = Path(file.filename or "upload.xlsx").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        result = await use_case.execute_from_file(
            file_path=tmp_path, ticker=ticker.upper()
        )
        return IngestResponse(**result.to_dict())
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post(
    "/ingest-path",
    response_model=IngestResponse,
    summary="Ingestar datos desde path local",
    description="Procesa un archivo XLSX que ya existe en el servidor. "
    "Útil para scripts y automatización.",
)
async def ingest_from_path(
    request: IngestFromPathRequest,
    use_case: IngestFinancialsUC,
) -> IngestResponse:
    result = await use_case.execute_from_file(
        file_path=Path(request.file_path),
        ticker=request.ticker.upper(),
    )
    return IngestResponse(**result.to_dict())
