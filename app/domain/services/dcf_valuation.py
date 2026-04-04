"""Servicio de Valoración DCF (Discounted Cash Flow).

Calcula el valor intrínseco de una acción usando:
1. Proyección de FCF a 5 años
2. Valor terminal (perpetuity growth model)
3. Descuento a valor presente con WACC
4. Ajuste por deuda neta → equity value
5. Valor por acción → comparación con precio de mercado

Cuando no hay Cash Flow Statement disponible, usa EBITDA como
proxy de FCF operativo (EBITDA * conversion_factor).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Sequence

from app.domain.entities.financial import FinancialStatement

logger = logging.getLogger(__name__)


@dataclass
class DCFParameters:
    """Parámetros configurables del modelo DCF."""

    projection_years: int = 5
    wacc: float = 0.10               # Costo promedio ponderado de capital
    terminal_growth_rate: float = 0.03  # Crecimiento perpetuo del terminal value
    margin_of_safety_pct: float = 0.25  # Margen de seguridad requerido para BUY
    ebitda_to_fcf_ratio: float = 0.55   # Conversión EBITDA → FCF (proxy sin CF)
    default_growth_rate: float = 0.05   # Growth rate si no hay historial
    max_growth_rate: float = 0.25       # Cap de growth rate para evitar proyecciones irreales
    min_growth_rate: float = -0.10      # Floor de growth rate


@dataclass
class DCFResult:
    """Resultado de la valoración DCF."""

    ticker: str
    intrinsic_value_per_share: float
    market_price: float
    margin_of_safety: float          # % positivo = subvalorada
    signal: str                      # BUY | HOLD | SELL
    projected_fcf: list[float]       # FCF proyectado por año
    terminal_value: float            # Valor terminal descontado
    enterprise_value: float          # EV total (FCF descontados + TV)
    equity_value: float              # EV - deuda neta
    wacc_used: float
    growth_rate_used: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "intrinsic_value_per_share": round(self.intrinsic_value_per_share, 2),
            "market_price": round(self.market_price, 2),
            "margin_of_safety": round(self.margin_of_safety, 2),
            "signal": self.signal,
            "projected_fcf": [round(f, 2) for f in self.projected_fcf],
            "terminal_value": round(self.terminal_value, 2),
            "enterprise_value": round(self.enterprise_value, 2),
            "equity_value": round(self.equity_value, 2),
            "wacc_used": round(self.wacc_used, 4),
            "growth_rate_used": round(self.growth_rate_used, 4),
            "reasons": self.reasons,
        }


class DCFValuationService:
    """Servicio de dominio para valoración DCF.

    Principio: sin IO, sin side effects. Cálculo puro.
    """

    def calculate(
        self,
        latest: FinancialStatement,
        historical: Sequence[FinancialStatement],
        shares_outstanding: int,
        market_price: float,
        params: DCFParameters | None = None,
    ) -> DCFResult:
        """Calcula valor intrínseco usando DCF.

        Args:
            latest: Último estado financiero (anualizado o Q4)
            historical: Historial para estimar growth rate
            shares_outstanding: Acciones en circulación
            market_price: Precio actual de mercado (por acción)
            params: Parámetros del modelo (usa defaults si None)

        Returns:
            DCFResult con valor intrínseco, señal y detalles

        Raises:
            ValueError: Si shares_outstanding <= 0
        """
        if shares_outstanding <= 0:
            raise ValueError(
                "shares_outstanding debe ser > 0 para calcular valor por acción"
            )

        p = params or DCFParameters()
        reasons: list[str] = []

        # 1. Encontrar mejor statement para FCF base (preferir FY)
        base_stmt = self._select_base_statement(latest, historical)
        is_quarterly = "Q" in base_stmt.period and "FY" not in base_stmt.period
        annualization_factor = 4 if is_quarterly else 1

        # 2. Estimar FCF base (anualizado)
        fcf_base = self._estimate_base_fcf(base_stmt, reasons) * annualization_factor
        if is_quarterly:
            reasons.append(f"FCF anualizado: ×4 (período trimestral {base_stmt.period})")

        # 3. Estimar growth rate desde historial
        growth_rate = self._estimate_growth_rate(
            historical, p, reasons
        )

        # 4. Proyectar FCF a N años
        projected_fcf = self._project_fcf(fcf_base, growth_rate, p)

        # 4. Calcular valor presente de FCF proyectados
        pv_fcf = sum(
            fcf / (1 + p.wacc) ** (i + 1)
            for i, fcf in enumerate(projected_fcf)
        )

        # 5. Calcular terminal value (Gordon Growth Model)
        if p.wacc <= p.terminal_growth_rate:
            # Evitar división por cero o negativa
            terminal_value_future = projected_fcf[-1] * 15  # Fallback: 15x último FCF
            reasons.append("WACC ≤ terminal growth: usando múltiplo 15x como TV")
        else:
            terminal_value_future = (
                projected_fcf[-1] * (1 + p.terminal_growth_rate)
                / (p.wacc - p.terminal_growth_rate)
            )

        # Descontar terminal value a valor presente
        terminal_value_pv = terminal_value_future / (1 + p.wacc) ** p.projection_years

        # 6. Enterprise Value = PV(FCF) + PV(TV)
        enterprise_value = pv_fcf + terminal_value_pv

        # 7. Equity Value = EV - Deuda Neta
        net_debt = latest.total_debt - latest.cash_and_equivalents
        equity_value = enterprise_value - net_debt

        # 8. Valor por acción
        intrinsic_per_share = equity_value / shares_outstanding
        # Convertir de USD millions a valor por acción
        # Los estados financieros están en millones USD,
        # necesitamos multiplicar por 1M y luego dividir por shares
        intrinsic_per_share = (equity_value * 1_000_000) / shares_outstanding

        # 9. Margin of Safety
        if intrinsic_per_share > 0:
            margin = ((intrinsic_per_share - market_price) / intrinsic_per_share) * 100
        else:
            margin = -100.0

        # 10. Signal
        signal = self._determine_signal(margin, p, reasons)

        return DCFResult(
            ticker=latest.ticker,
            intrinsic_value_per_share=max(intrinsic_per_share, 0),
            market_price=market_price,
            margin_of_safety=margin,
            signal=signal,
            projected_fcf=projected_fcf,
            terminal_value=terminal_value_pv,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            wacc_used=p.wacc,
            growth_rate_used=growth_rate,
            reasons=reasons,
        )

    def _select_base_statement(
        self,
        latest: FinancialStatement,
        historical: Sequence[FinancialStatement],
    ) -> FinancialStatement:
        """Selecciona el mejor statement para FCF base.

        Prefiere FY (anual) sobre trimestral para evitar estacionalidad.
        """
        # Buscar el FY más reciente en historial
        fy_stmts = [
            s for s in historical
            if "FY" in s.period and (s.ebitda > 0 or s.free_cash_flow != 0 or s.net_income > 0)
        ]
        if fy_stmts:
            return sorted(fy_stmts, key=lambda s: s.period)[-1]

        return latest

    def _estimate_base_fcf(
        self, stmt: FinancialStatement, reasons: list[str]
    ) -> float:
        """Estima FCF base anualizado.

        Prioridad:
        1. Free Cash Flow directo (si disponible)
        2. Operating Cash Flow - CapEx
        3. EBITDA * ratio de conversión (proxy)
        4. Net Income * 1.2 (último recurso)
        """
        # Intentar FCF directo
        if stmt.free_cash_flow != 0:
            reasons.append(f"FCF base: Free Cash Flow directo = {stmt.free_cash_flow:.1f}M")
            return abs(stmt.free_cash_flow)

        # Intentar OCF - CapEx
        if stmt.operating_cash_flow != 0:
            fcf = stmt.operating_cash_flow + stmt.capital_expenditure  # capex es negativo
            reasons.append(
                f"FCF base: OCF ({stmt.operating_cash_flow:.1f}) "
                f"- CapEx ({stmt.capital_expenditure:.1f}) = {fcf:.1f}M"
            )
            return abs(fcf) if fcf > 0 else abs(stmt.operating_cash_flow) * 0.6

        # Proxy: EBITDA * conversión
        if stmt.ebitda > 0:
            fcf = stmt.ebitda * DCFParameters().ebitda_to_fcf_ratio
            reasons.append(
                f"FCF base: EBITDA ({stmt.ebitda:.1f}M) × 0.55 = {fcf:.1f}M (proxy sin Cash Flow)"
            )
            return fcf

        # Último recurso: Net Income
        if stmt.net_income > 0:
            fcf = stmt.net_income * 1.2
            reasons.append(
                f"FCF base: Net Income ({stmt.net_income:.1f}M) × 1.2 = {fcf:.1f}M (proxy mínimo)"
            )
            return fcf

        # Empresa en pérdidas
        reasons.append("FCF base: empresa sin flujo positivo, usando 0")
        return 0.0

    def _estimate_growth_rate(
        self,
        historical: Sequence[FinancialStatement],
        params: DCFParameters,
        reasons: list[str],
    ) -> float:
        """Estima tasa de crecimiento desde historial.

        Usa CAGR de revenue si hay suficientes datos, sino default.
        """
        if len(historical) < 2:
            reasons.append(
                f"Growth rate: sin historial suficiente, usando default {params.default_growth_rate:.0%}"
            )
            return params.default_growth_rate

        # Filtrar períodos FY para CAGR más preciso
        fy_stmts = [s for s in historical if "FY" in s.period and s.revenue > 0]
        if len(fy_stmts) >= 2:
            stmts = sorted(fy_stmts, key=lambda s: s.period)
        else:
            stmts = sorted(
                [s for s in historical if s.revenue > 0],
                key=lambda s: s.period,
            )

        if len(stmts) < 2:
            reasons.append(
                f"Growth rate: revenue insuficiente, usando default {params.default_growth_rate:.0%}"
            )
            return params.default_growth_rate

        first_rev = stmts[0].revenue
        last_rev = stmts[-1].revenue
        years = max(len(stmts) - 1, 1)

        if first_rev <= 0 or last_rev <= 0:
            reasons.append(
                f"Growth rate: revenue negativo en historial, usando default"
            )
            return params.default_growth_rate

        cagr = (last_rev / first_rev) ** (1 / years) - 1

        # Cap growth rate
        capped = max(min(cagr, params.max_growth_rate), params.min_growth_rate)
        if capped != cagr:
            reasons.append(
                f"Growth rate: CAGR {cagr:.1%} ajustado a {capped:.1%} (cap)"
            )
        else:
            reasons.append(
                f"Growth rate: CAGR revenue = {cagr:.1%} ({years} períodos)"
            )

        return capped

    def _project_fcf(
        self, base: float, growth: float, params: DCFParameters
    ) -> list[float]:
        """Proyecta FCF para N años con growth rate decreciente."""
        projected = []
        # Growth rate decrece gradualmente hacia terminal growth
        for year in range(1, params.projection_years + 1):
            # Blend: growth rate se acerca a terminal en los últimos años
            blend = year / params.projection_years
            rate = growth * (1 - blend * 0.5) + params.terminal_growth_rate * (blend * 0.5)
            fcf = base * (1 + rate) ** year
            projected.append(max(fcf, 0))
        return projected

    def _determine_signal(
        self, margin: float, params: DCFParameters, reasons: list[str]
    ) -> str:
        """Determina señal BUY/HOLD/SELL basado en margin of safety."""
        mos_threshold = params.margin_of_safety_pct * 100  # 25%

        if margin >= mos_threshold:
            reasons.append(
                f"SEÑAL BUY: margen de seguridad {margin:.1f}% ≥ {mos_threshold:.0f}% requerido"
            )
            return "BUY"
        elif margin >= 0:
            reasons.append(
                f"SEÑAL HOLD: subvalorada {margin:.1f}% pero < {mos_threshold:.0f}% de margen requerido"
            )
            return "HOLD"
        else:
            reasons.append(
                f"SEÑAL SELL: sobrevalorada por {abs(margin):.1f}%"
            )
            return "SELL"
