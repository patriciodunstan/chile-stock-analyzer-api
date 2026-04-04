"""Servicio de Opportunity Scoring — señal BUY/HOLD/SELL.

Combina múltiples factores en un score de 0-100:
- Valorización (DCF margin of safety, P/E, EV/EBITDA)
- Calidad (ROE, márgenes, crecimiento)
- Riesgo (deuda, liquidez)

Score ≥ 70 → BUY
Score 40-69 → HOLD
Score < 40  → SELL
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.domain.entities.financial import FundamentalMetrics
from app.domain.services.dcf_valuation import DCFResult

logger = logging.getLogger(__name__)

# Pesos de cada categoría (suman 1.0)
_WEIGHT_VALUATION = 0.40
_WEIGHT_QUALITY = 0.35
_WEIGHT_RISK = 0.25


@dataclass
class ScoringResult:
    """Resultado del scoring de oportunidad."""

    ticker: str
    score: int                        # 0-100
    signal: str                       # BUY | HOLD | SELL
    valuation_score: int              # 0-100
    quality_score: int                # 0-100
    risk_score: int                   # 0-100
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "score": self.score,
            "signal": self.signal,
            "valuation_score": self.valuation_score,
            "quality_score": self.quality_score,
            "risk_score": self.risk_score,
            "reasons": self.reasons,
        }


class OpportunityScoringService:
    """Servicio de dominio: calcula score de oportunidad.

    Puro, sin IO, sin side effects.
    """

    def score(
        self,
        metrics: FundamentalMetrics,
        dcf: DCFResult | None = None,
    ) -> ScoringResult:
        """Calcula score compuesto y señal.

        Args:
            metrics: Métricas fundamentales calculadas
            dcf: Resultado del DCF (opcional, aporta valorización)

        Returns:
            ScoringResult con score, señal y razones
        """
        reasons: list[str] = []

        val_score = self._score_valuation(metrics, dcf, reasons)
        qual_score = self._score_quality(metrics, reasons)
        risk_score = self._score_risk(metrics, reasons)

        total = int(
            val_score * _WEIGHT_VALUATION
            + qual_score * _WEIGHT_QUALITY
            + risk_score * _WEIGHT_RISK
        )
        total = max(0, min(100, total))

        if total >= 70:
            signal = "BUY"
        elif total >= 40:
            signal = "HOLD"
        else:
            signal = "SELL"

        reasons.insert(0, f"Score total: {total}/100 ({signal})")

        return ScoringResult(
            ticker=metrics.ticker,
            score=total,
            signal=signal,
            valuation_score=val_score,
            quality_score=qual_score,
            risk_score=risk_score,
            reasons=reasons,
        )

    def _score_valuation(
        self,
        m: FundamentalMetrics,
        dcf: DCFResult | None,
        reasons: list[str],
    ) -> int:
        """Score de valorización (0-100). Más bajo el múltiplo, más alto el score."""
        points = 0
        factors = 0

        # P/E ratio (referencia: <10 excelente, 10-15 bueno, 15-25 neutro, >25 caro)
        if m.pe_ratio is not None and m.pe_ratio > 0:
            factors += 1
            if m.pe_ratio < 8:
                points += 100
                reasons.append(f"P/E {m.pe_ratio:.1f}: muy atractivo (<8)")
            elif m.pe_ratio < 12:
                points += 80
                reasons.append(f"P/E {m.pe_ratio:.1f}: atractivo (<12)")
            elif m.pe_ratio < 18:
                points += 50
                reasons.append(f"P/E {m.pe_ratio:.1f}: razonable")
            elif m.pe_ratio < 25:
                points += 25
                reasons.append(f"P/E {m.pe_ratio:.1f}: caro")
            else:
                points += 5
                reasons.append(f"P/E {m.pe_ratio:.1f}: muy caro (>25)")

        # EV/EBITDA (<8 barato, 8-12 justo, >12 caro)
        if m.ev_ebitda is not None and m.ev_ebitda > 0:
            factors += 1
            if m.ev_ebitda < 6:
                points += 100
                reasons.append(f"EV/EBITDA {m.ev_ebitda:.1f}: muy barato (<6)")
            elif m.ev_ebitda < 9:
                points += 75
                reasons.append(f"EV/EBITDA {m.ev_ebitda:.1f}: atractivo (<9)")
            elif m.ev_ebitda < 13:
                points += 45
                reasons.append(f"EV/EBITDA {m.ev_ebitda:.1f}: justo")
            else:
                points += 10
                reasons.append(f"EV/EBITDA {m.ev_ebitda:.1f}: caro (>13)")

        # P/B ratio (<1 deep value, 1-2 value, 2-4 growth, >4 caro)
        if m.pb_ratio is not None and m.pb_ratio > 0:
            factors += 1
            if m.pb_ratio < 1.0:
                points += 100
                reasons.append(f"P/B {m.pb_ratio:.2f}: deep value (<1)")
            elif m.pb_ratio < 2.0:
                points += 70
                reasons.append(f"P/B {m.pb_ratio:.2f}: value (<2)")
            elif m.pb_ratio < 4.0:
                points += 40
            else:
                points += 10

        # DCF margin of safety
        if dcf is not None:
            factors += 1
            mos = dcf.margin_of_safety
            if mos >= 40:
                points += 100
                reasons.append(f"DCF: margen de seguridad {mos:.0f}% (excelente)")
            elif mos >= 25:
                points += 80
                reasons.append(f"DCF: margen de seguridad {mos:.0f}% (bueno)")
            elif mos >= 10:
                points += 50
                reasons.append(f"DCF: margen de seguridad {mos:.0f}% (moderado)")
            elif mos >= 0:
                points += 30
            else:
                points += 5
                reasons.append(f"DCF: sobrevalorada por {abs(mos):.0f}%")

        return int(points / max(factors, 1))

    def _score_quality(
        self, m: FundamentalMetrics, reasons: list[str]
    ) -> int:
        """Score de calidad del negocio (0-100)."""
        points = 0
        factors = 0

        # ROE (>15% excelente, 10-15 bueno, <10 mediocre)
        if m.roe is not None:
            factors += 1
            roe_pct = m.roe * 100
            if roe_pct > 20:
                points += 100
                reasons.append(f"ROE {roe_pct:.1f}%: excelente (>20%)")
            elif roe_pct > 12:
                points += 75
                reasons.append(f"ROE {roe_pct:.1f}%: bueno (>12%)")
            elif roe_pct > 5:
                points += 40
                reasons.append(f"ROE {roe_pct:.1f}%: mediocre")
            elif roe_pct > 0:
                points += 15
            else:
                points += 0
                reasons.append(f"ROE {roe_pct:.1f}%: negativo")

        # Net Margin (>15% excelente, 10-15 bueno, 5-10 ok, <5 bajo)
        if m.net_margin is not None:
            factors += 1
            nm_pct = m.net_margin * 100
            if nm_pct > 20:
                points += 100
            elif nm_pct > 12:
                points += 75
                reasons.append(f"Margen neto {nm_pct:.1f}%: saludable")
            elif nm_pct > 5:
                points += 45
            elif nm_pct > 0:
                points += 20
            else:
                points += 0

        # EBITDA Margin (>25% excelente, 15-25 bueno)
        if m.ebitda_margin is not None:
            factors += 1
            em_pct = m.ebitda_margin * 100
            if em_pct > 30:
                points += 100
            elif em_pct > 20:
                points += 75
            elif em_pct > 12:
                points += 50
            else:
                points += 20

        # Revenue CAGR 3y (>10% alto crecimiento)
        if m.revenue_cagr_3y is not None:
            factors += 1
            cagr_pct = m.revenue_cagr_3y * 100
            if cagr_pct > 15:
                points += 100
                reasons.append(f"Crecimiento revenue 3Y: {cagr_pct:.1f}% (alto)")
            elif cagr_pct > 8:
                points += 70
            elif cagr_pct > 2:
                points += 40
            elif cagr_pct > -5:
                points += 20
            else:
                points += 0
                reasons.append(f"Crecimiento revenue 3Y: {cagr_pct:.1f}% (decreciendo)")

        # Gross Margin (>40% fuerte pricing power)
        if m.gross_margin is not None:
            factors += 1
            gm_pct = m.gross_margin * 100
            if gm_pct > 50:
                points += 100
            elif gm_pct > 35:
                points += 70
            elif gm_pct > 20:
                points += 40
            else:
                points += 15

        return int(points / max(factors, 1))

    def _score_risk(
        self, m: FundamentalMetrics, reasons: list[str]
    ) -> int:
        """Score de riesgo (0-100). Menor riesgo = mayor score.

        INVERTIDO: 100 = bajo riesgo (bueno), 0 = alto riesgo (malo).
        """
        points = 0
        factors = 0

        # Debt/Equity (<0.5 bajo, 0.5-1 moderado, 1-2 alto, >2 muy alto)
        if m.debt_to_equity is not None:
            factors += 1
            de = m.debt_to_equity
            if de < 0.3:
                points += 100
                reasons.append(f"D/E {de:.2f}: deuda muy baja")
            elif de < 0.7:
                points += 80
            elif de < 1.2:
                points += 55
                reasons.append(f"D/E {de:.2f}: deuda moderada")
            elif de < 2.0:
                points += 25
                reasons.append(f"D/E {de:.2f}: deuda alta")
            else:
                points += 5
                reasons.append(f"D/E {de:.2f}: deuda muy alta (>2)")

        # Interest Coverage (>5x seguro, 3-5 ok, <3 riesgo)
        if m.interest_coverage is not None:
            factors += 1
            ic = m.interest_coverage
            if ic > 10:
                points += 100
            elif ic > 5:
                points += 80
                reasons.append(f"Cobertura de intereses {ic:.1f}x: buena")
            elif ic > 3:
                points += 50
            elif ic > 1.5:
                points += 25
                reasons.append(f"Cobertura de intereses {ic:.1f}x: ajustada")
            else:
                points += 0
                reasons.append(f"Cobertura de intereses {ic:.1f}x: peligro")

        # Current Ratio (>2 holgado, 1.5-2 bueno, 1-1.5 ajustado, <1 riesgo)
        if m.current_ratio is not None:
            factors += 1
            cr = m.current_ratio
            if cr > 2.5:
                points += 100
            elif cr > 1.5:
                points += 75
            elif cr > 1.0:
                points += 40
            else:
                points += 5
                reasons.append(f"Current ratio {cr:.2f}: riesgo de liquidez (<1)")

        # Debt/EBITDA (<2 bajo, 2-3 moderado, >4 alto)
        if m.debt_to_ebitda is not None:
            factors += 1
            de = m.debt_to_ebitda
            if de < 1.5:
                points += 100
            elif de < 3.0:
                points += 65
            elif de < 4.5:
                points += 30
            else:
                points += 5
                reasons.append(f"Deuda/EBITDA {de:.1f}x: riesgo alto")

        return int(points / max(factors, 1))
