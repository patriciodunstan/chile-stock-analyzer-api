"""Use Case: Paper Trade — abre/cierra trades simulados y calcula performance.

El paper trading simula operaciones reales con capital virtual de 200.000 CLP.
Las comisiones (0.5%) se descuentan del P&L para reflejar el costo real.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.trade import Trade, TradeStatus, TradeStrategy
from app.domain.repositories.trade_repository import TradeRepository

logger = logging.getLogger(__name__)

_INITIAL_CAPITAL = 200_000.0
_MAX_POSITION_PCT = 0.50       # máximo 50% del capital por posición
_COMMISSION_RATE = 0.005       # 0.5%


@dataclass
class PortfolioStatus:
    """Estado actual del portfolio paper."""
    capital_initial: float
    capital_available: float
    capital_in_positions: float
    open_trades: list[dict]
    unrealized_pnl: float
    unrealized_pnl_pct: float

    def to_dict(self) -> dict:
        return {
            "capital_initial": self.capital_initial,
            "capital_available": round(self.capital_available, 2),
            "capital_in_positions": round(self.capital_in_positions, 2),
            "open_trades": self.open_trades,
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "unrealized_pnl_pct": round(self.unrealized_pnl_pct, 2),
        }


@dataclass
class PerformanceMetrics:
    """Métricas de performance del paper trading."""
    total_trades: int
    open_trades: int
    closed_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float           # %
    total_pnl: float          # CLP
    total_pnl_pct: float      # %
    avg_win: float            # CLP promedio en trades ganadores
    avg_loss: float           # CLP promedio en trades perdedores
    profit_factor: float      # total_wins / total_losses
    max_drawdown: float       # % máxima caída desde peak
    best_trade: dict | None
    worst_trade: dict | None

    def to_dict(self) -> dict:
        return {
            "total_trades": self.total_trades,
            "open_trades": self.open_trades,
            "closed_trades": self.closed_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 1),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "best_trade": self.best_trade,
            "worst_trade": self.worst_trade,
        }


@dataclass
class PaperTradeUseCase:
    trade_repository: TradeRepository

    async def open_trade(
        self,
        ticker: str,
        strategy: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        capital: float | None = None,
    ) -> Trade:
        """Abre un nuevo trade simulado.

        Valida que haya capital disponible y no haya otra posición abierta
        en el mismo ticker.
        """
        # Verificar posiciones abiertas
        open_trades = await self.trade_repository.get_open_trades(is_paper=True)
        if len(open_trades) >= 1:
            raise ValueError(
                f"Ya hay {len(open_trades)} posición(es) abierta(s). "
                "Máximo 1 posición simultánea con 200.000 CLP."
            )

        capital_used = capital or min(
            _INITIAL_CAPITAL * _MAX_POSITION_PCT,
            100_000.0,
        )
        commission = capital_used * _COMMISSION_RATE
        quantity = max(1, int((capital_used - commission) / entry_price))

        trade = Trade(
            ticker=ticker.upper(),
            strategy=TradeStrategy(strategy),
            entry_price=entry_price,
            quantity=quantity,
            entry_date=datetime.utcnow(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            capital_used=capital_used,
            commission_entry=commission,
            is_paper=True,
        )

        saved = await self.trade_repository.save(trade)
        logger.info(
            "Paper trade abierto: %s %s — entrada %.0f, SL %.0f, TP %.0f",
            ticker, strategy, entry_price, stop_loss, take_profit,
        )
        return saved

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float,
    ) -> Trade:
        """Cierra un trade simulado al precio indicado."""
        trade = await self.trade_repository.get_by_id(trade_id)
        if trade is None:
            raise ValueError(f"Trade {trade_id} no encontrado")
        if not trade.is_open:
            raise ValueError(f"Trade {trade_id} ya está cerrado ({trade.status.value})")

        trade.close(exit_price, datetime.utcnow(), _COMMISSION_RATE)
        updated = await self.trade_repository.update(trade)

        logger.info(
            "Paper trade cerrado: %s — salida %.0f, P&L %.0f CLP (%.1f%%)",
            trade.ticker, exit_price,
            trade.pnl or 0, trade.pnl_pct or 0,
        )
        return updated

    async def get_portfolio(self, current_prices: dict[str, float] | None = None) -> PortfolioStatus:
        """Retorna estado actual del portfolio con P&L no realizado."""
        open_trades = await self.trade_repository.get_open_trades(is_paper=True)
        closed_trades = await self.trade_repository.get_closed_trades(is_paper=True)

        realized_pnl = sum(t.pnl or 0 for t in closed_trades)
        capital_in_positions = sum(t.capital_used for t in open_trades)
        capital_available = _INITIAL_CAPITAL + realized_pnl - capital_in_positions

        unrealized_pnl = 0.0
        open_dicts = []
        for trade in open_trades:
            current = (current_prices or {}).get(trade.ticker, trade.entry_price)
            unreal = (current - trade.entry_price) * trade.quantity
            unrealized_pnl += unreal
            d = trade.to_dict()
            d["current_price"] = current
            d["unrealized_pnl"] = round(unreal, 2)
            d["unrealized_pnl_pct"] = round(unreal / trade.capital_used * 100, 2)
            open_dicts.append(d)

        unreal_pct = (unrealized_pnl / _INITIAL_CAPITAL * 100) if _INITIAL_CAPITAL else 0

        return PortfolioStatus(
            capital_initial=_INITIAL_CAPITAL,
            capital_available=capital_available,
            capital_in_positions=capital_in_positions,
            open_trades=open_dicts,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unreal_pct,
        )

    async def get_performance(self) -> PerformanceMetrics:
        """Calcula métricas completas de performance sobre todos los trades cerrados."""
        closed = await self.trade_repository.get_closed_trades(is_paper=True, limit=200)
        open_trades = await self.trade_repository.get_open_trades(is_paper=True)

        wins = [t for t in closed if t.status == TradeStatus.CLOSED_PROFIT]
        losses = [t for t in closed if t.status in (
            TradeStatus.CLOSED_LOSS, TradeStatus.CLOSED_MANUAL
        ) and (t.pnl or 0) < 0]

        total_pnl = sum(t.pnl or 0 for t in closed)
        win_rate = len(wins) / len(closed) * 100 if closed else 0.0

        total_wins = sum(t.pnl or 0 for t in wins)
        total_losses = abs(sum(t.pnl or 0 for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else (99.0 if total_wins > 0 else 0.0)

        avg_win = total_wins / len(wins) if wins else 0.0
        avg_loss = total_losses / len(losses) if losses else 0.0

        # Max drawdown (simplificado: mayor pérdida acumulada desde peak)
        max_drawdown = _calculate_max_drawdown(closed, _INITIAL_CAPITAL)

        best = max(closed, key=lambda t: t.pnl or 0, default=None)
        worst = min(closed, key=lambda t: t.pnl or 0, default=None)

        return PerformanceMetrics(
            total_trades=len(closed) + len(open_trades),
            open_trades=len(open_trades),
            closed_trades=len(closed),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=win_rate,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl / _INITIAL_CAPITAL * 100 if _INITIAL_CAPITAL else 0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            best_trade=best.to_dict() if best else None,
            worst_trade=worst.to_dict() if worst else None,
        )


def _calculate_max_drawdown(trades: list[Trade], initial: float) -> float:
    """Calcula el max drawdown como % desde el peak del portfolio."""
    if not trades:
        return 0.0
    equity = initial
    peak = initial
    max_dd = 0.0
    for t in sorted(trades, key=lambda x: x.exit_date or datetime.min):
        equity += t.pnl or 0
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, dd)
    return max_dd
