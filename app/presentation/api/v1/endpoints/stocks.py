"""Endpoints de acciones y precios — HU-001."""

from fastapi import APIRouter, Query
from typing import Annotated

from app.dependencies import GetStockPriceUC, ListStocksUC, GetPriceHistoryUC, MarketProvider
from app.presentation.schemas.stock import (
    StockPriceResponse,
    StockListResponse,
    StockListItem,
    PriceHistoryResponse,
    DataSourcesResponse,
)

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get(
    "/data-sources",
    response_model=DataSourcesResponse,
    summary="Ver proveedores de datos configurados",
    description="Muestra qué fuentes de datos están habilitadas y cuál se usó en la última consulta.",
)
async def get_data_sources(
    market: MarketProvider,
) -> DataSourcesResponse:
    return DataSourcesResponse(
        providers=[name for name, _ in market._providers],
        last_source=market.last_source,
        description="Proveedores en orden de prioridad. El sistema intenta cada uno en cascada hasta obtener respuesta.",
    )


@router.get(
    "/{ticker}/price",
    response_model=StockPriceResponse,
    summary="Obtener precio actual de una acción",
    description="Consulta precios usando múltiples fuentes en cascada "
    "(Bolsa de Santiago → Yahoo Finance → EODHD → Mock) "
    "y persiste en la base de datos.",
)
async def get_stock_price(
    ticker: str,
    use_case: GetStockPriceUC,
    market: MarketProvider,
) -> StockPriceResponse:
    dto = await use_case.execute(ticker)
    return StockPriceResponse(
        ticker=dto.ticker,
        price=dto.price,
        open_price=dto.open_price,
        high=dto.high,
        low=dto.low,
        close_price=dto.close_price,
        volume=dto.volume,
        market_cap=dto.market_cap,
        change_percent=dto.change_percent,
        timestamp=dto.timestamp,
        currency=dto.currency,
        data_source=market.last_source,
    )


@router.get(
    "/",
    response_model=StockListResponse,
    summary="Listar acciones de un índice",
    description="Retorna las acciones constituyentes de un índice (IPSA por defecto) "
    "con su último precio registrado.",
)
async def list_stocks(
    use_case: ListStocksUC,
    index: Annotated[str, Query(description="Índice bursátil")] = "IPSA",
) -> StockListResponse:
    items = await use_case.execute(index)
    return StockListResponse(
        items=[
            StockListItem(
                ticker=i.ticker,
                name=i.name,
                sector=i.sector,
                market=i.market,
                latest_price=i.latest_price,
                change_percent=i.change_percent,
            )
            for i in items
        ],
        total=len(items),
        index=index,
    )


@router.get(
    "/{ticker}/history",
    response_model=PriceHistoryResponse,
    summary="Historial de precios de una acción",
    description="Retorna los últimos N precios registrados en la base de datos.",
)
async def get_price_history(
    ticker: str,
    use_case: GetPriceHistoryUC,
    limit: Annotated[int, Query(ge=1, le=365)] = 30,
) -> PriceHistoryResponse:
    dtos = await use_case.execute(ticker, limit)
    return PriceHistoryResponse(
        ticker=ticker,
        prices=[
            StockPriceResponse(
                ticker=d.ticker,
                price=d.price,
                open_price=d.open_price,
                high=d.high,
                low=d.low,
                close_price=d.close_price,
                volume=d.volume,
                market_cap=d.market_cap,
                change_percent=d.change_percent,
                timestamp=d.timestamp,
                currency=d.currency,
            )
            for d in dtos
        ],
        count=len(dtos),
    )
