"""Motor de señales para swing trading — evalúa las 3 estrategias.

Las 3 estrategias están diseñadas para el ciclo lunes/viernes:
  1. Monday Bounce   — RSI oversold + BB inferior
  2. Weekly Momentum — EMA crossover + MACD positivo
  3. Friday Dip      — caída viernes sin noticia, cerca de soporte

Puro, sin IO, sin side effects.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.domain.entities.trade import TradeStrategy
from app.domain.services.technical_indicators import TechnicalSnapshot

logger = logging.getLogger(__name__)

# Comisión por defecto para calcular precios netos
_DEFAULT_COMMISSION = 0.005  # 0.5%


@dataclass
class SwingSignal:
    """Señal de swing trading para un ticker y estrategia."""

    ticker: str
    strategy: TradeStrategy
    action: str                 # "BUY" | "WAIT"
    strength: int               # 0-100 (confianza de la señal)
    entry_price: float          # precio sugerido de entrada
    stop_loss: float            # precio de stop loss
    take_profit: float          # precio de take profit
    risk_reward: float          # ratio riesgo/beneficio (ej: 2.0 = 1:2)
    capital_suggested: float    # CLP sugerido a invertir
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "strategy": self.strategy.value,
            "action": self.action,
            "strength": self.strength,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward": self.risk_reward,
            "capital_suggested": self.capital_suggested,
            "reasons": self.reasons,
            "warnings": self.warnings,
        }


@dataclass
class MondayScanResult:
    """Resultado del escaneo de oportunidades para el lunes."""

    ticker: str
    name: str
    sector: str
    best_signal: SwingSignal | None
    all_signals: list[SwingSignal]
    snapshot: dict              # indicadores técnicos actuales

    @property
    def has_opportunity(self) -> bool:
        return self.best_signal is not None and self.best_signal.action == "BUY"

    @property
    def strength(self) -> int:
        return self.best_signal.strength if self.best_signal else 0

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "has_opportunity": self.has_opportunity,
            "best_signal": self.best_signal.to_dict() if self.best_signal else None,
            "all_signals": [s.to_dict() for s in self.all_signals],
            "snapshot": self.snapshot,
        }


class SwingSignalService:
    """Evalúa las 3 estrategias de swing sobre un snapshot técnico.

    Puro, sin IO. Recibe TechnicalSnapshot y retorna señales.
    """

    def __init__(self, max_capital_per_trade: float = 100_000.0):
        self._max_capital = max_capital_per_trade

    def evaluate_all(
        self,
        snapshot: TechnicalSnapshot,
        week_change_pct: float = 0.0,   # % cambio semanal del precio
        day_change_pct: float = 0.0,    # % cambio en el día
    ) -> list[SwingSignal]:
        """Evalúa las 3 estrategias y retorna todas las señales."""
        signals = [
            self.monday_bounce(snapshot, week_change_pct),
            self.weekly_momentum(snapshot),
            self.friday_dip(snapshot, day_change_pct),
        ]
        return signals

    def best_signal(self, signals: list[SwingSignal]) -> SwingSignal | None:
        """Retorna la señal BUY con mayor strength, o None si no hay BUY."""
        buy_signals = [s for s in signals if s.action == "BUY"]
        if not buy_signals:
            return None
        return max(buy_signals, key=lambda s: s.strength)

    # ----------------------------------------------------------
    # Estrategia 1 — Monday Bounce
    # ----------------------------------------------------------

    def monday_bounce(
        self,
        snap: TechnicalSnapshot,
        week_change_pct: float = 0.0,
    ) -> SwingSignal:
        """RSI oversold + precio cerca de banda inferior Bollinger.

        Mejor entrada: lunes mañana después de caída del viernes.
        """
        reasons: list[str] = []
        warnings: list[str] = []
        strength = 0

        # Condición 1: RSI oversold
        rsi_ok = snap.rsi is not None and snap.rsi < 35
        if rsi_ok:
            strength += 35
            reasons.append(f"RSI {snap.rsi:.1f} — oversold (<35), rebote probable")
        elif snap.rsi is not None and snap.rsi < 45:
            strength += 15
            reasons.append(f"RSI {snap.rsi:.1f} — levemente bajo")
        else:
            warnings.append(f"RSI {snap.rsi:.1f} — no confirma oversold" if snap.rsi else "RSI no disponible")

        # Condición 2: precio cerca de banda inferior BB
        bb_ok = snap.bb_position == "LOWER"
        bb_pct_ok = snap.bb_pct is not None and snap.bb_pct < 0.20
        if bb_ok or bb_pct_ok:
            strength += 30
            pct_str = f"{snap.bb_pct * 100:.0f}%" if snap.bb_pct is not None else "?"
            reasons.append(f"Precio en zona baja de Bollinger Bands ({pct_str} desde lower)")
        else:
            warnings.append("Precio no está en zona baja de Bollinger Bands")

        # Condición 3: caída semanal (más oversold = mejor rebote)
        if week_change_pct <= -5:
            strength += 25
            reasons.append(f"Cayó {abs(week_change_pct):.1f}% la semana — oversold adicional")
        elif week_change_pct <= -3:
            strength += 15
            reasons.append(f"Cayó {abs(week_change_pct):.1f}% la semana")
        else:
            warnings.append("No hubo caída significativa la semana previa")

        # Condición 4: volumen bajo durante la caída (no hay pánico, es corrección)
        if snap.volume_ratio is not None and snap.volume_ratio < 0.8:
            strength += 10
            reasons.append("Volumen bajo durante caída — señal de corrección técnica, no pánico")

        action = "BUY" if strength >= 50 else "WAIT"

        entry = snap.last_price
        stop_loss = _stop_from_atr(entry, snap.atr, default_pct=0.05)
        take_profit = entry * 1.10
        risk = entry - stop_loss
        reward = take_profit - entry
        rr = round(reward / risk, 2) if risk > 0 else 0.0

        qty = int(self._max_capital / entry) if entry > 0 else 0
        capital = qty * entry

        return SwingSignal(
            ticker=snap.ticker,
            strategy=TradeStrategy.MONDAY_BOUNCE,
            action=action,
            strength=min(strength, 100),
            entry_price=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_reward=rr,
            capital_suggested=round(capital, 2),
            reasons=reasons,
            warnings=warnings,
        )

    # ----------------------------------------------------------
    # Estrategia 2 — Weekly Momentum
    # ----------------------------------------------------------

    def weekly_momentum(self, snap: TechnicalSnapshot) -> SwingSignal:
        """EMA9 > EMA21 + MACD histograma positivo y creciendo.

        Captura tendencias semanales alcistas confirmadas.
        """
        reasons: list[str] = []
        warnings: list[str] = []
        strength = 0

        # Condición 1: EMA cruce bullish
        ema_ok = snap.ema_cross == "BULLISH"
        if ema_ok:
            strength += 35
            if snap.ema9 and snap.ema21:
                diff_pct = (snap.ema9 - snap.ema21) / snap.ema21 * 100
                reasons.append(
                    f"EMA9 ({snap.ema9:.0f}) > EMA21 ({snap.ema21:.0f}) "
                    f"— tendencia alcista ({diff_pct:+.1f}%)"
                )
        else:
            warnings.append(
                f"EMA9 ({snap.ema9:.0f}) < EMA21 ({snap.ema21:.0f}) — sin tendencia alcista"
                if snap.ema9 and snap.ema21 else "EMAs no disponibles"
            )

        # Condición 2: MACD histograma positivo y creciendo
        macd_ok = snap.macd_trend == "BULLISH"
        if macd_ok:
            strength += 35
            reasons.append(
                f"MACD histograma positivo y creciendo ({snap.macd_histogram:+.4f}) — momentum alcista"
                if snap.macd_histogram else "MACD positivo"
            )
        elif snap.macd_histogram is not None and snap.macd_histogram > 0:
            strength += 15
            reasons.append("MACD histograma positivo (sin confirmación de crecimiento)")
        else:
            warnings.append("MACD no confirma momentum alcista")

        # Condición 3: volumen alto confirma el movimiento
        if snap.volume_ratio is not None and snap.volume_ratio > 1.3:
            strength += 20
            reasons.append(f"Volumen {snap.volume_ratio:.1f}x el promedio — fuerza confirmada")
        elif snap.volume_ratio is not None and snap.volume_ratio > 1.0:
            strength += 10
            reasons.append(f"Volumen sobre el promedio ({snap.volume_ratio:.1f}x)")
        else:
            warnings.append("Volumen no confirma el movimiento")

        # Condición 4: precio sobre EMA21 (tendencia establecida)
        if snap.ema21 and snap.last_price > snap.ema21:
            strength += 10
            reasons.append(f"Precio ({snap.last_price:.0f}) sobre EMA21 ({snap.ema21:.0f})")

        action = "BUY" if strength >= 55 else "WAIT"

        entry = snap.last_price
        stop_loss = _stop_from_atr(entry, snap.atr, default_pct=0.04)
        # Para momentum, stop más ajustado: puede ser EMA21
        if snap.ema21 and snap.ema21 < entry * 0.97:
            stop_loss = max(stop_loss, snap.ema21 * 0.99)  # justo bajo EMA21
        take_profit = entry * 1.10
        risk = entry - stop_loss
        reward = take_profit - entry
        rr = round(reward / risk, 2) if risk > 0 else 0.0

        qty = int(self._max_capital / entry) if entry > 0 else 0
        capital = qty * entry

        return SwingSignal(
            ticker=snap.ticker,
            strategy=TradeStrategy.WEEKLY_MOMENTUM,
            action=action,
            strength=min(strength, 100),
            entry_price=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_reward=rr,
            capital_suggested=round(capital, 2),
            reasons=reasons,
            warnings=warnings,
        )

    # ----------------------------------------------------------
    # Estrategia 3 — Friday Dip
    # ----------------------------------------------------------

    def friday_dip(
        self,
        snap: TechnicalSnapshot,
        day_change_pct: float = 0.0,
    ) -> SwingSignal:
        """Caída viernes cerca de soporte, sin noticia negativa.

        Objetivo: vender el lunes siguiente al open.
        Target más conservador: +6%.
        """
        reasons: list[str] = []
        warnings: list[str] = []
        strength = 0

        # Condición 1: caída del día > 2%
        if day_change_pct <= -3:
            strength += 35
            reasons.append(f"Cayó {abs(day_change_pct):.1f}% hoy — oversold intradía")
        elif day_change_pct <= -2:
            strength += 20
            reasons.append(f"Cayó {abs(day_change_pct):.1f}% hoy")
        else:
            warnings.append(f"Caída del día insuficiente ({day_change_pct:.1f}%, necesita <-2%)")

        # Condición 2: RSI bajo
        if snap.rsi is not None and snap.rsi < 40:
            strength += 30
            reasons.append(f"RSI {snap.rsi:.1f} — zona baja, rebote probable el lunes")
        elif snap.rsi is not None and snap.rsi < 50:
            strength += 15
            reasons.append(f"RSI {snap.rsi:.1f} — levemente bajo")
        else:
            warnings.append(f"RSI {snap.rsi:.1f} — sin zona oversold" if snap.rsi else "RSI no disponible")

        # Condición 3: precio cerca de soporte (EMA21 o BB lower)
        near_support = (
            (snap.ema21 is not None and snap.last_price < snap.ema21 * 1.02)
            or snap.bb_position == "LOWER"
        )
        if near_support:
            strength += 25
            if snap.ema21 and snap.last_price < snap.ema21 * 1.02:
                reasons.append(f"Precio cerca de EMA21 ({snap.ema21:.0f}) — soporte dinámico")
            if snap.bb_position == "LOWER":
                reasons.append("Precio en banda inferior Bollinger — soporte estadístico")
        else:
            warnings.append("Precio no está cerca de soportes técnicos conocidos")

        # Condición 4: tendencia mayor no es bajista (no atrapar cuchillo)
        if snap.ema_cross != "BEARISH":
            strength += 10
            reasons.append("Tendencia semanal no es bajista — riesgo reducido")
        else:
            warnings.append("⚠️ Tendencia bajista — riesgo de continuar cayendo el lunes")
            strength -= 10  # penalizar si hay tendencia bajista

        action = "BUY" if strength >= 55 else "WAIT"

        entry = snap.last_price
        stop_loss = _stop_from_atr(entry, snap.atr, default_pct=0.04)
        take_profit = entry * 1.06   # target más conservador para el lunes
        risk = entry - stop_loss
        reward = take_profit - entry
        rr = round(reward / risk, 2) if risk > 0 else 0.0

        qty = int(self._max_capital / entry) if entry > 0 else 0
        capital = qty * entry

        return SwingSignal(
            ticker=snap.ticker,
            strategy=TradeStrategy.FRIDAY_DIP,
            action=action,
            strength=max(0, min(strength, 100)),
            entry_price=round(entry, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_reward=rr,
            capital_suggested=round(capital, 2),
            reasons=reasons,
            warnings=warnings,
        )


# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------

def _stop_from_atr(
    price: float,
    atr: float | None,
    default_pct: float = 0.05,
    multiplier: float = 1.5,
) -> float:
    """Calcula stop loss basado en ATR o porcentaje fijo como fallback."""
    if atr is not None and atr > 0:
        return price - multiplier * atr
    return price * (1 - default_pct)
