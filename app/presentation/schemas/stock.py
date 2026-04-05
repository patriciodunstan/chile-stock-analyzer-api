"""Pydantic v2 schemas para request/response de stocks."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StockPriceResponse(BaseModel):
    """Respuesta con precio actual de una acción."""

    model_config = ConfigDict(from_attributes=True)

    ticker: str
    price: float
    open_price: float
    high: float
    low: float
    close_price: float
    volume: int
    market_cap: float
    change_percent: float
    timestamp: str
    currency: str = "CLP"
    data_source: str | None = None


class StockListItem(BaseModel):
    """Item de listado de acciones."""

    ticker: str
    name: str
    sector: str
    market: str
    latest_price: float | None = None
    change_percent: float | None = None


class StockListResponse(BaseModel):
    """Respuesta de listado de acciones."""

    items: list[StockListItem]
    total: int
    index: str


class PriceHistoryResponse(BaseModel):
    """Respuesta con historial de precios."""

    ticker: str
    prices: list[StockPriceResponse]
    count: int


class DataSourcesResponse(BaseModel):
    """Respuesta con proveedores de datos configurados."""

    providers: list[str]
    last_source: str
    description: str


class HealthResponse(BaseModel):
    """Respuesta del health check."""

    status: str = "ok"
    version: str = "0.1.0"
    service: str = "chile-stock-analyzer"
