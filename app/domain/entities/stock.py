"""Entidad Stock — representa una acción del mercado chileno."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from app.domain.entities.base import BaseEntity


@dataclass
class Stock(BaseEntity):
    """Acción listada en la Bolsa de Santiago."""

    ticker: str = ""
    name: str = ""
    sector: str = ""
    market: str = "IPSA"  # IPSA, IGPA, etc.
    is_active: bool = True


@dataclass
class StockPrice:
    """Snapshot de precio de una acción en un momento dado."""

    ticker: str
    price: float  # Precio en CLP
    open_price: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close_price: float = 0.0
    volume: int = 0
    market_cap: float = 0.0  # Capitalización bursátil en CLP
    change_percent: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    currency: str = "CLP"

    @property
    def is_valid(self) -> bool:
        return self.price > 0 and self.ticker != ""
