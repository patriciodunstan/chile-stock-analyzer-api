"""Entidad Trade — representa un trade de swing trading (real o simulado).

Un Trade tiene ciclo de vida: OPEN → CLOSED (por take profit, stop loss o manual).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED_PROFIT = "CLOSED_PROFIT"    # cerrado por take profit
    CLOSED_LOSS = "CLOSED_LOSS"        # cerrado por stop loss
    CLOSED_MANUAL = "CLOSED_MANUAL"    # cerrado manualmente (viernes review)


class TradeStrategy(str, Enum):
    MONDAY_BOUNCE = "monday_bounce"      # RSI oversold + BB inferior
    WEEKLY_MOMENTUM = "weekly_momentum"  # EMA crossover + MACD positivo
    FRIDAY_DIP = "friday_dip"            # caída viernes sin noticia


@dataclass
class Trade:
    """Trade de swing trading — paper o real.

    Attributes:
        id: UUID único del trade
        ticker: Código de la acción (ej: "COPEC")
        strategy: Estrategia que generó la señal
        entry_price: Precio de entrada en CLP
        quantity: Número de acciones
        entry_date: Fecha/hora de entrada
        stop_loss: Precio de stop loss en CLP
        take_profit: Precio de take profit en CLP
        capital_used: CLP invertidos (entry_price × quantity)
        commission_entry: Comisión pagada al entrar (CLP)
        status: Estado actual del trade
        exit_price: Precio de salida en CLP (None si aún abierto)
        exit_date: Fecha/hora de cierre (None si aún abierto)
        commission_exit: Comisión pagada al salir (CLP)
        pnl: Ganancia/pérdida neta en CLP (después de comisiones)
        pnl_pct: Ganancia/pérdida en porcentaje
        is_paper: True = simulado, False = real
        notes: Notas adicionales del trader
    """
    ticker: str
    strategy: TradeStrategy
    entry_price: float
    quantity: int
    entry_date: datetime
    stop_loss: float
    take_profit: float
    capital_used: float
    commission_entry: float = 0.0
    status: TradeStatus = TradeStatus.OPEN
    exit_price: float | None = None
    exit_date: datetime | None = None
    commission_exit: float = 0.0
    pnl: float | None = None
    pnl_pct: float | None = None
    is_paper: bool = True
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    @property
    def duration_days(self) -> int | None:
        """Días que estuvo abierto el trade."""
        if self.exit_date is None:
            return None
        return (self.exit_date - self.entry_date).days

    def close(
        self,
        exit_price: float,
        exit_date: datetime,
        commission_rate: float = 0.005,
    ) -> None:
        """Cierra el trade calculando P&L neto.

        Args:
            exit_price: Precio de salida en CLP
            exit_date: Fecha/hora de cierre
            commission_rate: Tasa de comisión (default 0.5%)
        """
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.commission_exit = self.capital_used * commission_rate

        gross_pnl = (exit_price - self.entry_price) * self.quantity
        self.pnl = gross_pnl - self.commission_entry - self.commission_exit
        self.pnl_pct = self.pnl / self.capital_used * 100

        if exit_price >= self.take_profit:
            self.status = TradeStatus.CLOSED_PROFIT
        elif exit_price <= self.stop_loss:
            self.status = TradeStatus.CLOSED_LOSS
        else:
            self.status = TradeStatus.CLOSED_MANUAL

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "strategy": self.strategy.value,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "entry_date": self.entry_date.isoformat(),
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "capital_used": self.capital_used,
            "commission_entry": self.commission_entry,
            "status": self.status.value,
            "exit_price": self.exit_price,
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "commission_exit": self.commission_exit,
            "pnl": round(self.pnl, 2) if self.pnl is not None else None,
            "pnl_pct": round(self.pnl_pct, 2) if self.pnl_pct is not None else None,
            "duration_days": self.duration_days,
            "is_paper": self.is_paper,
            "notes": self.notes,
        }
