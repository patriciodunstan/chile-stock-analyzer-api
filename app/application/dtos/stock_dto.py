from __future__ import annotations
"""DTOs para transferencia de datos de acciones."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class StockPriceDTO:
    """DTO de respuesta con precio de acción."""

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

    @classmethod
    def from_entity(cls, entity) -> "StockPriceDTO":
        from app.domain.entities.stock import StockPrice

        return cls(
            ticker=entity.ticker,
            price=entity.price,
            open_price=entity.open_price,
            high=entity.high,
            low=entity.low,
            close_price=entity.close_price,
            volume=entity.volume,
            market_cap=entity.market_cap,
            change_percent=entity.change_percent,
            timestamp=entity.timestamp.isoformat(),
            currency=entity.currency,
        )


@dataclass
class StockListItemDTO:
    """DTO resumido de una acción para listados."""

    ticker: str
    name: str
    sector: str
    market: str
    latest_price: float | None = None
    change_percent: float | None = None
