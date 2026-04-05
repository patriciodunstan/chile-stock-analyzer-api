"""Servicio de Opportunity Scoring — señal BUY/HOLD/SELL.

Combina múltiples factores en un score de 0-100:
- Valorización (DCF margin of safety, P/E, EV/EBITDA, P/B)  → 40%
- Calidad (ROE, márgenes, crecimiento)                       → 35%
- Riesgo (deuda, liquidez)                                   → 25%

Score ≥ 70 → BUY
Score 40-69 → HOLD
Score < 40  → SELL

Mejoras sobre versión original:
- Benchmarks diferenciados por sector (Minería, Retail, Banca, Energía, Forestal, Holding)
- data_completeness: % de criterios con datos reales (evita scores engañosos)
- critical_alerts: alertas de insolvencia que pueden forzar señal SELL
- Reasons contextuales: incluyen benchmark sectorial y drivers del score
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import NamedTuple

from app.domain.entities.company import Sector
from app.domain.entities.financial import FundamentalMetrics
from app.domain.services.dcf_valuation import DCFResult

logger = logging.getLogger(__name__)

# Pesos de cada categoría (suman 1.0)
_WEIGHT_VALUATION = 0.40
_WEIGHT_QUALITY = 0.35
_WEIGHT_RISK = 0.25


# ============================================================
# Benchmarks sectoriales
# ============================================================

class _SectorThresholds(NamedTuple):
    """Umbrales de valorización y calidad para un sector."""
    # P/E: excelente / bueno / razonable / caro
    pe_excellent: float
    pe_good: float
    pe_fair: float
    pe_expensive: float
    # EV/EBITDA: excelente / bueno / justo (None = no aplica)
    ev_excellent: float | None
    ev_good: float | None
    ev_fair: float | None
    # P/B: excelente / bueno / razonable
    pb_excellent: float
    pb_good: float
    pb_fair: float
    # ROE: excelente / bueno
    roe_excellent: float
    roe_good: float
    # D/E: bajo / moderado / alto
    de_low: float
    de_moderate: float
    de_high: float
    # Nombre visible del sector
    label: str
    # EV/EBITDA aplica para este sector
    ev_applies: bool = True


_SECTOR_THRESHOLDS: dict[Sector, _SectorThresholds] = {
    Sector.MINERIA: _SectorThresholds(
        pe_excellent=6, pe_good=10, pe_fair=15, pe_expensive=22,
        ev_excellent=4, ev_good=7, ev_fair=10,
        pb_excellent=0.8, pb_good=1.5, pb_fair=3.0,
        roe_excellent=0.18, roe_good=0.10,
        de_low=0.5, de_moderate=1.0, de_high=1.5,
        label="Minería",
    ),
    Sector.RETAIL: _SectorThresholds(
        pe_excellent=10, pe_good=15, pe_fair=22, pe_expensive=30,
        ev_excellent=6, ev_good=9, ev_fair=13,
        pb_excellent=1.0, pb_good=2.0, pb_fair=4.0,
        roe_excellent=0.15, roe_good=0.08,
        de_low=0.8, de_moderate=1.5, de_high=2.5,
        label="Retail",
    ),
    Sector.BANCA: _SectorThresholds(
        pe_excellent=7, pe_good=11, pe_fair=16, pe_expensive=22,
        ev_excellent=None, ev_good=None, ev_fair=None,
        pb_excellent=0.7, pb_good=1.2, pb_fair=2.0,
        roe_excellent=0.15, roe_good=0.10,
        de_low=5.0, de_moderate=10.0, de_high=15.0,  # bancos tienen leverage alto por estructura
        label="Banca",
        ev_applies=False,
    ),
    Sector.ENERGIA: _SectorThresholds(
        pe_excellent=10, pe_good=14, pe_fair=20, pe_expensive=28,
        ev_excellent=6, ev_good=9, ev_fair=13,
        pb_excellent=0.8, pb_good=1.5, pb_fair=3.0,
        roe_excellent=0.12, roe_good=0.07,
        de_low=1.0, de_moderate=2.0, de_high=3.5,
        label="Energía",
    ),
    Sector.FORESTAL: _SectorThresholds(
        pe_excellent=8, pe_good=12, pe_fair=18, pe_expensive=25,
        ev_excellent=5, ev_good=8, ev_fair=12,
        pb_excellent=0.8, pb_good=1.5, pb_fair=3.0,
        roe_excellent=0.14, roe_good=0.08,
        de_low=0.8, de_moderate=1.5, de_high=2.5,
        label="Forestal",
    ),
    Sector.HOLDING: _SectorThresholds(
        pe_excellent=10, pe_good=14, pe_fair=20, pe_expensive=28,
        ev_excellent=7, ev_good=10, ev_fair=14,
        pb_excellent=0.7, pb_good=1.2, pb_fair=2.5,
        roe_excellent=0.12, roe_good=0.07,
        de_low=0.5, de_moderate=1.2, de_high=2.0,
        label="Holding",
    ),
    Sector.INDUSTRIAL: _SectorThresholds(
        pe_excellent=9, pe_good=13, pe_fair=19, pe_expensive=26,
        ev_excellent=5, ev_good=8, ev_fair=12,
        pb_excellent=0.9, pb_good=1.8, pb_fair=3.5,
        roe_excellent=0.14, roe_good=0.08,
        de_low=0.6, de_moderate=1.2, de_high=2.0,
        label="Industrial",
    ),
    Sector.CONSUMO: _SectorThresholds(
        pe_excellent=10, pe_good=15, pe_fair=22, pe_expensive=30,
        ev_excellent=6, ev_good=9, ev_fair=13,
        pb_excellent=1.0, pb_good=2.0, pb_fair=4.0,
        roe_excellent=0.15, roe_good=0.08,
        de_low=0.8, de_moderate=1.5, de_high=2.5,
        label="Consumo",
    ),
}

# Benchmarks genéricos (fallback si sector es None)
_DEFAULT_THRESHOLDS = _SectorThresholds(
    pe_excellent=8, pe_good=12, pe_fair=18, pe_expensive=25,
    ev_excellent=6, ev_good=9, ev_fair=13,
    pb_excellent=1.0, pb_good=2.0, pb_fair=4.0,
    roe_excellent=0.20, roe_good=0.12,
    de_low=0.3, de_moderate=0.7, de_high=1.2,
    label="mercado general",
)


def _get_thresholds(sector: Sector | None) -> _SectorThresholds:
    if sector is None:
        return _DEFAULT_THRESHOLDS
    return _SECTOR_THRESHOLDS.get(sector, _DEFAULT_THRESHOLDS)


# ============================================================
# ScoringResult
# ============================================================

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

    # Completeness
    data_completeness: int = 100      # % de criterios con datos reales
    criteria_used: int = 0            # criterios con datos reales
    criteria_total: int = 0           # criterios totales evaluables para este sector

    # Alertas críticas
    critical_alerts: list[str] = field(default_factory=list)
    signal_override: bool = False     # True si la señal fue forzada por alerta crítica

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "score": self.score,
            "signal": self.signal,
            "valuation_score": self.valuation_score,
            "quality_score": self.quality_score,
            "risk_score": self.risk_score,
            "data_completeness": self.data_completeness,
            "criteria_used": self.criteria_used,
            "criteria_total": self.criteria_total,
            "critical_alerts": self.critical_alerts,
            "signal_override": self.signal_override,
            "reasons": self.reasons,
        }


# ============================================================
# OpportunityScoringService
# ============================================================

class OpportunityScoringService:
    """Servicio de dominio: calcula score de oportunidad.

    Puro, sin IO, sin side effects.
    """

    def score(
        self,
        metrics: FundamentalMetrics,
        dcf: DCFResult | None = None,
        sector: Sector | None = None,
    ) -> ScoringResult:
        """Calcula score compuesto y señal con benchmarks sectoriales.

        Args:
            metrics: Métricas fundamentales calculadas
            dcf: Resultado del DCF (opcional)
            sector: Sector de la empresa (para benchmarks ajustados)

        Returns:
            ScoringResult con score, señal, reasons y alertas críticas
        """
        t = _get_thresholds(sector)
        reasons: list[str] = []
        critical_alerts: list[str] = []

        # Verificar alertas críticas ANTES del scoring
        signal_override = self._check_critical_alerts(metrics, critical_alerts)

        val_score, val_used, val_total = self._score_valuation(metrics, dcf, reasons, t)
        qual_score, qual_used, qual_total = self._score_quality(metrics, reasons, t)
        risk_score, risk_used, risk_total = self._score_risk(metrics, reasons, t)

        total_used = val_used + qual_used + risk_used
        total_criteria = val_total + qual_total + risk_total
        data_completeness = int((total_used / max(total_criteria, 1)) * 100)

        total = int(
            val_score * _WEIGHT_VALUATION
            + qual_score * _WEIGHT_QUALITY
            + risk_score * _WEIGHT_RISK
        )
        total = max(0, min(100, total))

        # Determinar señal
        if signal_override:
            signal = "SELL"
        elif total >= 70:
            signal = "BUY"
        elif total >= 40:
            signal = "HOLD"
        else:
            signal = "SELL"

        # Agregar drivers del score a las razones
        self._add_score_drivers(val_score, qual_score, risk_score, reasons)

        # Aviso de completeness si hay datos faltantes
        if data_completeness < 70:
            reasons.append(
                f"Datos disponibles: {total_used}/{total_criteria} criterios "
                f"({data_completeness}%) — score puede ser menos preciso"
            )

        # Resumen al inicio
        summary = f"Score total: {total}/100 ({signal}) | {t.label}"
        if signal_override:
            summary += " — SEÑAL FORZADA POR ALERTA CRÍTICA"
        reasons.insert(0, summary)

        return ScoringResult(
            ticker=metrics.ticker,
            score=total,
            signal=signal,
            valuation_score=val_score,
            quality_score=qual_score,
            risk_score=risk_score,
            reasons=reasons,
            data_completeness=data_completeness,
            criteria_used=total_used,
            criteria_total=total_criteria,
            critical_alerts=critical_alerts,
            signal_override=signal_override,
        )

    # ----------------------------------------------------------
    # Alertas críticas
    # ----------------------------------------------------------

    def _check_critical_alerts(
        self, m: FundamentalMetrics, alerts: list[str]
    ) -> bool:
        """Verifica condiciones de insolvencia/riesgo extremo.

        Returns:
            True si debe forzarse señal SELL.
        """
        force_sell = False

        if m.interest_coverage is not None and m.interest_coverage < 1.0:
            alerts.append(
                f"ALERTA CRÍTICA: La empresa no puede cubrir sus intereses "
                f"(cobertura {m.interest_coverage:.1f}x < 1.0x)"
            )
            force_sell = True

        if m.current_ratio is not None and m.current_ratio < 0.8:
            alerts.append(
                f"ALERTA: Riesgo de liquidez crítico "
                f"(current ratio {m.current_ratio:.2f} < 0.8)"
            )

        if m.debt_to_ebitda is not None and m.debt_to_ebitda > 6.0:
            alerts.append(
                f"ALERTA: Apalancamiento excesivo "
                f"(D/EBITDA {m.debt_to_ebitda:.1f}x > 6.0x)"
            )

        if m.net_margin is not None and m.net_margin < -0.20:
            alerts.append(
                f"ALERTA: Pérdidas severas "
                f"(margen neto {m.net_margin * 100:.1f}%)"
            )

        return force_sell

    # ----------------------------------------------------------
    # Scoring de valorización
    # ----------------------------------------------------------

    def _score_valuation(
        self,
        m: FundamentalMetrics,
        dcf: DCFResult | None,
        reasons: list[str],
        t: _SectorThresholds,
    ) -> tuple[int, int, int]:
        """Retorna (score, criterios_usados, criterios_totales)."""
        points = 0
        used = 0
        total = 0

        # P/E ratio
        total += 1
        if m.pe_ratio is not None and m.pe_ratio > 0:
            used += 1
            if m.pe_ratio < t.pe_excellent:
                points += 100
                reasons.append(
                    f"P/E {m.pe_ratio:.1f}x — muy atractivo para {t.label} "
                    f"(benchmark: <{t.pe_excellent:.0f}x)"
                )
            elif m.pe_ratio < t.pe_good:
                points += 80
                reasons.append(
                    f"P/E {m.pe_ratio:.1f}x — atractivo para {t.label} "
                    f"(benchmark: <{t.pe_good:.0f}x)"
                )
            elif m.pe_ratio < t.pe_fair:
                points += 50
                reasons.append(
                    f"P/E {m.pe_ratio:.1f}x — razonable para {t.label} "
                    f"(benchmark: <{t.pe_fair:.0f}x)"
                )
            elif m.pe_ratio < t.pe_expensive:
                points += 25
                reasons.append(
                    f"P/E {m.pe_ratio:.1f}x — caro para {t.label} "
                    f"(benchmark sector: <{t.pe_fair:.0f}x)"
                )
            else:
                points += 5
                reasons.append(
                    f"P/E {m.pe_ratio:.1f}x — muy caro para {t.label} "
                    f"(benchmark: >{t.pe_expensive:.0f}x)"
                )

        # EV/EBITDA (solo si aplica para el sector)
        if t.ev_applies:
            total += 1
            if (
                m.ev_ebitda is not None
                and m.ev_ebitda > 0
                and t.ev_excellent is not None
            ):
                used += 1
                if m.ev_ebitda < t.ev_excellent:
                    points += 100
                    reasons.append(
                        f"EV/EBITDA {m.ev_ebitda:.1f}x — muy barato "
                        f"(benchmark {t.label}: <{t.ev_excellent:.0f}x)"
                    )
                elif m.ev_ebitda < t.ev_good:
                    points += 75
                    reasons.append(
                        f"EV/EBITDA {m.ev_ebitda:.1f}x — atractivo "
                        f"(benchmark {t.label}: <{t.ev_good:.0f}x)"
                    )
                elif m.ev_ebitda < t.ev_fair:
                    points += 45
                    reasons.append(
                        f"EV/EBITDA {m.ev_ebitda:.1f}x — justo "
                        f"(benchmark {t.label}: <{t.ev_fair:.0f}x)"
                    )
                else:
                    points += 10
                    reasons.append(
                        f"EV/EBITDA {m.ev_ebitda:.1f}x — caro para {t.label} "
                        f"(benchmark: <{t.ev_fair:.0f}x)"
                    )

        # P/B ratio
        total += 1
        if m.pb_ratio is not None and m.pb_ratio > 0:
            used += 1
            if m.pb_ratio < t.pb_excellent:
                points += 100
                reasons.append(
                    f"P/B {m.pb_ratio:.2f}x — deep value "
                    f"(benchmark {t.label}: <{t.pb_excellent:.1f}x)"
                )
            elif m.pb_ratio < t.pb_good:
                points += 70
                reasons.append(
                    f"P/B {m.pb_ratio:.2f}x — value "
                    f"(benchmark {t.label}: <{t.pb_good:.1f}x)"
                )
            elif m.pb_ratio < t.pb_fair:
                points += 40
            else:
                points += 10

        # DCF margin of safety
        total += 1
        if dcf is not None:
            used += 1
            mos = dcf.margin_of_safety
            if mos >= 40:
                points += 100
                reasons.append(f"DCF: margen de seguridad {mos:.0f}% — excelente")
            elif mos >= 25:
                points += 80
                reasons.append(f"DCF: margen de seguridad {mos:.0f}% — bueno")
            elif mos >= 10:
                points += 50
                reasons.append(f"DCF: margen de seguridad {mos:.0f}% — moderado")
            elif mos >= 0:
                points += 30
            else:
                points += 5
                reasons.append(f"DCF: acción sobrevalorada {abs(mos):.0f}% sobre valor intrínseco")

        return int(points / max(used, 1)), used, total

    # ----------------------------------------------------------
    # Scoring de calidad
    # ----------------------------------------------------------

    def _score_quality(
        self,
        m: FundamentalMetrics,
        reasons: list[str],
        t: _SectorThresholds,
    ) -> tuple[int, int, int]:
        """Retorna (score, criterios_usados, criterios_totales)."""
        points = 0
        used = 0
        total = 5  # ROE, net margin, EBITDA margin, revenue CAGR, gross margin

        # ROE
        if m.roe is not None:
            used += 1
            roe_pct = m.roe * 100
            if m.roe > t.roe_excellent:
                points += 100
                reasons.append(
                    f"ROE {roe_pct:.1f}% — excelente para {t.label} "
                    f"(benchmark: >{t.roe_excellent * 100:.0f}%)"
                )
            elif m.roe > t.roe_good:
                points += 75
                reasons.append(
                    f"ROE {roe_pct:.1f}% — bueno para {t.label} "
                    f"(benchmark: >{t.roe_good * 100:.0f}%)"
                )
            elif m.roe > 0.05:
                points += 40
                reasons.append(f"ROE {roe_pct:.1f}% — mediocre")
            elif m.roe > 0:
                points += 15
            else:
                points += 0
                reasons.append(f"ROE {roe_pct:.1f}% — negativo (pérdidas)")

        # Net Margin
        if m.net_margin is not None:
            used += 1
            nm_pct = m.net_margin * 100
            if nm_pct > 20:
                points += 100
                reasons.append(f"Margen neto {nm_pct:.1f}% — excelente")
            elif nm_pct > 12:
                points += 75
                reasons.append(f"Margen neto {nm_pct:.1f}% — saludable")
            elif nm_pct > 5:
                points += 45
            elif nm_pct > 0:
                points += 20
            else:
                points += 0
                reasons.append(f"Margen neto {nm_pct:.1f}% — en pérdidas")

        # EBITDA Margin
        if m.ebitda_margin is not None:
            used += 1
            em_pct = m.ebitda_margin * 100
            if em_pct > 30:
                points += 100
                reasons.append(f"Margen EBITDA {em_pct:.1f}% — muy alto")
            elif em_pct > 20:
                points += 75
            elif em_pct > 12:
                points += 50
            else:
                points += 20

        # Revenue CAGR 3y
        if m.revenue_cagr_3y is not None:
            used += 1
            cagr_pct = m.revenue_cagr_3y * 100
            if cagr_pct > 15:
                points += 100
                reasons.append(f"Crecimiento ventas 3Y: {cagr_pct:.1f}% — alto")
            elif cagr_pct > 8:
                points += 70
                reasons.append(f"Crecimiento ventas 3Y: {cagr_pct:.1f}% — moderado")
            elif cagr_pct > 2:
                points += 40
            elif cagr_pct > -5:
                points += 20
            else:
                points += 0
                reasons.append(
                    f"Crecimiento ventas 3Y: {cagr_pct:.1f}% — decreciendo"
                )

        # Gross Margin
        if m.gross_margin is not None:
            used += 1
            gm_pct = m.gross_margin * 100
            if gm_pct > 50:
                points += 100
            elif gm_pct > 35:
                points += 70
            elif gm_pct > 20:
                points += 40
            else:
                points += 15

        return int(points / max(used, 1)), used, total

    # ----------------------------------------------------------
    # Scoring de riesgo
    # ----------------------------------------------------------

    def _score_risk(
        self,
        m: FundamentalMetrics,
        reasons: list[str],
        t: _SectorThresholds,
    ) -> tuple[int, int, int]:
        """Score de riesgo (0-100). 100 = bajo riesgo.

        Retorna (score, criterios_usados, criterios_totales).
        """
        points = 0
        used = 0
        total = 4  # D/E, interest coverage, current ratio, D/EBITDA

        # Debt/Equity
        if m.debt_to_equity is not None:
            used += 1
            de = m.debt_to_equity
            if de < t.de_low:
                points += 100
                reasons.append(f"D/E {de:.2f}x — deuda baja para {t.label}")
            elif de < t.de_moderate:
                points += 80
            elif de < t.de_high:
                points += 55
                reasons.append(f"D/E {de:.2f}x — deuda moderada")
            elif de < t.de_high * 1.5:
                points += 25
                reasons.append(f"D/E {de:.2f}x — deuda alta para {t.label}")
            else:
                points += 5
                reasons.append(f"D/E {de:.2f}x — deuda muy alta para {t.label}")

        # Interest Coverage
        if m.interest_coverage is not None:
            used += 1
            ic = m.interest_coverage
            if ic > 10:
                points += 100
            elif ic > 5:
                points += 80
                reasons.append(f"Cobertura intereses {ic:.1f}x — buena")
            elif ic > 3:
                points += 50
            elif ic > 1.5:
                points += 25
                reasons.append(f"Cobertura intereses {ic:.1f}x — ajustada")
            else:
                points += 0
                reasons.append(f"Cobertura intereses {ic:.1f}x — en zona de riesgo")

        # Current Ratio
        if m.current_ratio is not None:
            used += 1
            cr = m.current_ratio
            if cr > 2.5:
                points += 100
            elif cr > 1.5:
                points += 75
            elif cr > 1.0:
                points += 40
            else:
                points += 5
                reasons.append(f"Current ratio {cr:.2f} — riesgo de liquidez (<1.0)")

        # Debt/EBITDA
        if m.debt_to_ebitda is not None:
            used += 1
            de = m.debt_to_ebitda
            if de < 1.5:
                points += 100
            elif de < 3.0:
                points += 65
            elif de < 4.5:
                points += 30
            else:
                points += 5
                reasons.append(f"D/EBITDA {de:.1f}x — apalancamiento alto")

        return int(points / max(used, 1)), used, total

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    @staticmethod
    def _add_score_drivers(
        val_score: int,
        qual_score: int,
        risk_score: int,
        reasons: list[str],
    ) -> None:
        """Agrega una línea resumen indicando qué dimensiones impulsan o limitan el score."""
        scores = {
            "Valorización": val_score,
            "Calidad": qual_score,
            "Riesgo": risk_score,
        }
        best = max(scores, key=lambda k: scores[k])
        worst = min(scores, key=lambda k: scores[k])

        if scores[best] >= 70:
            reasons.append(
                f"Impulsado por: {best} ({scores[best]}/100)"
            )
        if scores[worst] <= 40:
            reasons.append(
                f"Limitado por: {worst} ({scores[worst]}/100)"
            )
