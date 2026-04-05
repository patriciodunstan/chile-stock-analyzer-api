"""Use Case: Friday Review — revisa posiciones abiertas el viernes y recomienda acción.

Analiza cada posición abierta en contexto del fin de semana:
- ¿Aguantar o cerrar antes del lunes?
- ¿Cuánto P&L hay en juego?
- ¿Los indicadores siguen siendo favorables?
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.entities.trade import Trade
from app.domain.repositories.trade_repository import TradeRepository
from app.domain.services.technical_indicators import TechnicalIndicatorsService
from app.domain.repositories.stock_repository import StockRepository

logger = logging.getLogger(__name__)

_INDICATORS = TechnicalIndicatorsService()


@dataclass
class PositionReview:
    """Revisión de una posición abierta el viernes."""
    trade: dict
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    recommendation: str        # "HOLD" | "CLOSE" | "CLOSE_URGENT"
    reasons: list[str]
    risk_weekend: str          # "LOW" | "MEDIUM" | "HIGH"


@dataclass
class FridayReviewResult:
    """Resultado completo del Friday Review."""
    open_positions: int
    reviews: list[PositionReview]
    portfolio_pnl: float
    portfolio_pnl_pct: float
    summary: str

    def to_dict(self) -> dict:
        return {
            "open_positions": self.open_positions,
            "portfolio_pnl": round(self.portfolio_pnl, 2),
            "portfolio_pnl_pct": round(self.portfolio_pnl_pct, 2),
            "summary": self.summary,
            "reviews": [
                {
                    "trade": r.trade,
                    "current_price": r.current_price,
                    "unrealized_pnl": round(r.unrealized_pnl, 2),
                    "unrealized_pnl_pct": round(r.unrealized_pnl_pct, 2),
                    "recommendation": r.recommendation,
                    "reasons": r.reasons,
                    "risk_weekend": r.risk_weekend,
                }
                for r in self.reviews
            ],
        }


@dataclass
class FridayReviewUseCase:
    trade_repository: TradeRepository
    stock_repository: StockRepository

    async def execute(self) -> FridayReviewResult:
        """Genera el reporte de revisión de posiciones para el viernes."""
        open_trades = await self.trade_repository.get_open_trades(is_paper=True)

        if not open_trades:
            return FridayReviewResult(
                open_positions=0,
                reviews=[],
                portfolio_pnl=0.0,
                portfolio_pnl_pct=0.0,
                summary="Sin posiciones abiertas. Libre para explorar entradas el lunes.",
            )

        reviews: list[PositionReview] = []
        total_pnl = 0.0
        total_capital = 0.0

        for trade in open_trades:
            review = await self._review_position(trade)
            reviews.append(review)
            total_pnl += review.unrealized_pnl
            total_capital += trade.capital_used

        pnl_pct = total_pnl / total_capital * 100 if total_capital else 0

        urgent = [r for r in reviews if r.recommendation == "CLOSE_URGENT"]
        close_recommended = [r for r in reviews if r.recommendation == "CLOSE"]
        hold = [r for r in reviews if r.recommendation == "HOLD"]

        if urgent:
            summary = f"⚠️ {len(urgent)} posición(es) requieren cierre URGENTE antes del fin de semana"
        elif close_recommended:
            summary = f"Se recomienda cerrar {len(close_recommended)} posición(es) antes del cierre del viernes"
        else:
            summary = f"{len(hold)} posición(es) pueden aguantar el fin de semana con stop loss activo"

        return FridayReviewResult(
            open_positions=len(open_trades),
            reviews=reviews,
            portfolio_pnl=total_pnl,
            portfolio_pnl_pct=pnl_pct,
            summary=summary,
        )

    async def _review_position(self, trade: Trade) -> PositionReview:
        """Analiza una posición y genera recomendación."""
        reasons: list[str] = []

        # Obtener precio actual desde historial
        prices = await self.stock_repository.get_price_history(trade.ticker, limit=10)
        current_price = prices[-1].price if prices else trade.entry_price

        unrealized_pnl = (current_price - trade.entry_price) * trade.quantity
        unrealized_pnl_pct = unrealized_pnl / trade.capital_used * 100

        recommendation = "HOLD"
        risk_weekend = "LOW"

        # Regla 1: Take profit alcanzado o muy cerca → CLOSE
        if current_price >= trade.take_profit:
            recommendation = "CLOSE"
            reasons.append(
                f"✅ Take profit alcanzado: {current_price:.0f} ≥ {trade.take_profit:.0f} "
                f"— asegurar ganancia de {unrealized_pnl_pct:.1f}%"
            )
        elif current_price >= trade.take_profit * 0.95:
            recommendation = "CLOSE"
            reasons.append(
                f"Muy cerca del take profit ({current_price:.0f} vs {trade.take_profit:.0f}) "
                f"— conveniente asegurar {unrealized_pnl_pct:.1f}%"
            )

        # Regla 2: Stop loss muy cerca → CLOSE_URGENT
        if current_price <= trade.stop_loss * 1.02:
            recommendation = "CLOSE_URGENT"
            risk_weekend = "HIGH"
            reasons.append(
                f"⚠️ Precio muy cerca del stop loss ({current_price:.0f} vs SL {trade.stop_loss:.0f}) "
                f"— riesgo alto de activarse el lunes con gap bajista"
            )

        # Regla 3: Pérdida > 3% → evaluar cierre
        if unrealized_pnl_pct <= -3 and recommendation == "HOLD":
            recommendation = "CLOSE"
            risk_weekend = "MEDIUM"
            reasons.append(
                f"Pérdida de {unrealized_pnl_pct:.1f}% — mejor cerrar que arriesgar más el fin de semana"
            )

        # Regla 4: Ganancia entre 5-9% → HOLD pero con nota
        if 5 <= unrealized_pnl_pct < 10 and recommendation == "HOLD":
            reasons.append(
                f"Ganancia de {unrealized_pnl_pct:.1f}% — stop loss sigue activo para proteger"
            )
            risk_weekend = "LOW"

        # Regla 5: Ganancia > 8% sin llegar al TP → considerar cierre
        if unrealized_pnl_pct >= 8 and recommendation == "HOLD":
            recommendation = "CLOSE"
            reasons.append(
                f"Ganancia de {unrealized_pnl_pct:.1f}% — se puede asegurar antes del fin de semana"
            )

        if not reasons:
            reasons.append(
                f"Posición neutral ({unrealized_pnl_pct:+.1f}%) — mantener con stop loss en {trade.stop_loss:.0f}"
            )

        return PositionReview(
            trade=trade.to_dict(),
            current_price=round(current_price, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            unrealized_pnl_pct=round(unrealized_pnl_pct, 2),
            recommendation=recommendation,
            reasons=reasons,
            risk_weekend=risk_weekend,
        )
