"""Tests unitarios para OpportunityScoringService.

Cubre:
- Señales BUY/HOLD/SELL según score
- Benchmarks sectoriales (Minería vs Banca vs default)
- Data completeness (criterios parciales)
- Alertas críticas de insolvencia (force SELL)
- Drivers del score (impulsado / limitado por)
- DCF margin of safety integrado en scoring
- Integración completa con sector real
"""
import pytest
from unittest.mock import MagicMock

from app.domain.entities.company import Sector
from app.domain.entities.financial import FundamentalMetrics
from app.domain.services.dcf_valuation import DCFResult
from app.domain.services.opportunity_scoring import (
    OpportunityScoringService,
    ScoringResult,
    _get_thresholds,
    _DEFAULT_THRESHOLDS,
    _SECTOR_THRESHOLDS,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def scorer():
    return OpportunityScoringService()


def make_metrics(
    ticker: str = "TEST",
    period: str = "2025-FY",
    pe_ratio: float | None = 10.0,
    ev_ebitda: float | None = 7.0,
    pb_ratio: float | None = 1.5,
    roe: float | None = 0.18,
    net_margin: float | None = 0.15,
    ebitda_margin: float | None = 0.25,
    revenue_cagr_3y: float | None = 0.10,
    gross_margin: float | None = 0.40,
    debt_to_equity: float | None = 0.5,
    interest_coverage: float | None = 8.0,
    current_ratio: float | None = 2.0,
    debt_to_ebitda: float | None = 2.0,
) -> FundamentalMetrics:
    m = MagicMock(spec=FundamentalMetrics)
    m.ticker = ticker
    m.period = period
    m.pe_ratio = pe_ratio
    m.ev_ebitda = ev_ebitda
    m.pb_ratio = pb_ratio
    m.roe = roe
    m.net_margin = net_margin
    m.ebitda_margin = ebitda_margin
    m.revenue_cagr_3y = revenue_cagr_3y
    m.gross_margin = gross_margin
    m.debt_to_equity = debt_to_equity
    m.interest_coverage = interest_coverage
    m.current_ratio = current_ratio
    m.debt_to_ebitda = debt_to_ebitda
    return m


def make_dcf(margin_of_safety: float = 30.0, intrinsic: float = 1000.0) -> DCFResult:
    dcf = MagicMock(spec=DCFResult)
    dcf.margin_of_safety = margin_of_safety
    dcf.intrinsic_value_per_share = intrinsic
    return dcf


# ============================================================
# Señales BUY / HOLD / SELL
# ============================================================

class TestSignals:
    def test_buy_signal_high_score(self, scorer):
        """Score ≥ 70 debe generar señal BUY."""
        m = make_metrics(
            pe_ratio=6.0, ev_ebitda=4.0, pb_ratio=0.8,
            roe=0.25, net_margin=0.22, ebitda_margin=0.35, revenue_cagr_3y=0.18,
            debt_to_equity=0.2, interest_coverage=15.0, current_ratio=3.0, debt_to_ebitda=1.0,
        )
        result = scorer.score(m)
        assert result.signal == "BUY"
        assert result.score >= 70

    def test_sell_signal_low_score(self, scorer):
        """Score < 40 debe generar señal SELL."""
        m = make_metrics(
            pe_ratio=40.0, ev_ebitda=20.0, pb_ratio=6.0,
            roe=-0.05, net_margin=-0.10, ebitda_margin=0.05, revenue_cagr_3y=-0.10,
            debt_to_equity=3.0, interest_coverage=1.2, current_ratio=0.5, debt_to_ebitda=7.0,
        )
        result = scorer.score(m)
        assert result.signal == "SELL"
        assert result.score < 40

    def test_hold_signal_mid_score(self, scorer):
        """Score 40-69 debe generar señal HOLD."""
        m = make_metrics(
            pe_ratio=16.0, ev_ebitda=10.0, pb_ratio=2.5,
            roe=0.10, net_margin=0.08, ebitda_margin=0.15, revenue_cagr_3y=0.04,
            debt_to_equity=1.0, interest_coverage=4.0, current_ratio=1.3, debt_to_ebitda=3.0,
        )
        result = scorer.score(m)
        assert result.signal == "HOLD"
        assert 40 <= result.score < 70

    def test_result_type(self, scorer):
        """El resultado debe ser una instancia de ScoringResult."""
        m = make_metrics()
        result = scorer.score(m)
        assert isinstance(result, ScoringResult)
        assert result.ticker == "TEST"

    def test_score_bounded_0_100(self, scorer):
        """El score siempre debe estar entre 0 y 100."""
        for pe in [1.0, 50.0, 100.0]:
            m = make_metrics(pe_ratio=pe)
            result = scorer.score(m)
            assert 0 <= result.score <= 100


# ============================================================
# Benchmarks sectoriales
# ============================================================

class TestSectorBenchmarks:
    def test_pe_12_scores_higher_for_retail_than_mineria(self, scorer):
        """P/E=12 es 'bueno' para Retail pero solo 'razonable' para Minería."""
        m = make_metrics(
            pe_ratio=12.0, ev_ebitda=None, pb_ratio=None,
            roe=None, net_margin=None, ebitda_margin=None, revenue_cagr_3y=None,
            gross_margin=None, debt_to_equity=None, interest_coverage=None,
            current_ratio=None, debt_to_ebitda=None,
        )
        result_retail = scorer.score(m, sector=Sector.RETAIL)
        result_mineria = scorer.score(m, sector=Sector.MINERIA)
        # Para Retail, P/E=12 es bueno (80pts); para Minería, P/E=12 es razonable (50pts)
        assert result_retail.valuation_score > result_mineria.valuation_score

    def test_ev_ebitda_skipped_for_banca(self, scorer):
        """EV/EBITDA no debe contar en criterios para sector Banca."""
        m = make_metrics(
            pe_ratio=10.0, ev_ebitda=5.0, pb_ratio=1.0,
            roe=0.15, net_margin=0.12, ebitda_margin=0.20, revenue_cagr_3y=0.05,
            debt_to_equity=8.0, interest_coverage=None, current_ratio=None, debt_to_ebitda=None,
        )
        result_banca = scorer.score(m, sector=Sector.BANCA)
        result_default = scorer.score(m)
        # Banca no evalúa EV/EBITDA, por lo que criteria_total debe ser menor
        assert result_banca.criteria_total < result_default.criteria_total

    def test_high_de_acceptable_for_banca(self, scorer):
        """D/E=8 es aceptable para Banca (threshold de_low=5) pero no para Minería."""
        m = make_metrics(
            pe_ratio=None, ev_ebitda=None, pb_ratio=None,
            roe=None, net_margin=None, ebitda_margin=None, revenue_cagr_3y=None,
            gross_margin=None, debt_to_equity=8.0, interest_coverage=None,
            current_ratio=None, debt_to_ebitda=None,
        )
        result_banca = scorer.score(m, sector=Sector.BANCA)
        result_mineria = scorer.score(m, sector=Sector.MINERIA)
        # Para Banca, D/E=8 está por encima del umbral moderado pero dentro del rango;
        # para Minería, D/E=8 es extremadamente alto → risk score de banca debe ser mayor
        assert result_banca.risk_score > result_mineria.risk_score

    def test_sector_label_in_reasons(self, scorer):
        """Las reasons deben incluir el label del sector."""
        m = make_metrics(pe_ratio=8.0)
        result = scorer.score(m, sector=Sector.ENERGIA)
        reason_text = " ".join(result.reasons)
        assert "Energía" in reason_text

    def test_default_thresholds_when_sector_none(self, scorer):
        """Sin sector, usa benchmarks genéricos."""
        m = make_metrics()
        result = scorer.score(m, sector=None)
        assert "mercado general" in result.reasons[0]

    def test_all_sectors_produce_valid_result(self, scorer):
        """Todos los sectores deben producir un ScoringResult válido."""
        m = make_metrics()
        for sector in Sector:
            result = scorer.score(m, sector=sector)
            assert isinstance(result, ScoringResult)
            assert 0 <= result.score <= 100
            assert result.signal in ("BUY", "HOLD", "SELL")


# ============================================================
# Data Completeness
# ============================================================

class TestDataCompleteness:
    def test_full_data_100_percent(self, scorer):
        """Con todos los datos disponibles, completeness debe ser 100%."""
        m = make_metrics()  # todos los campos tienen valor
        dcf = make_dcf()
        result = scorer.score(m, dcf=dcf)
        assert result.data_completeness == 100
        assert result.criteria_used == result.criteria_total

    def test_no_market_data_lower_completeness(self, scorer):
        """Sin precio de mercado (P/E, EV/EBITDA, P/B, DCF = None), completeness < 80%."""
        m = make_metrics(
            pe_ratio=None, ev_ebitda=None, pb_ratio=None,
        )
        result = scorer.score(m, dcf=None)
        # 4 criterios de valorización faltantes de 13 totales → 69% (~9/13)
        assert result.data_completeness < 80
        assert result.criteria_used < result.criteria_total

    def test_criteria_used_leq_total(self, scorer):
        """criteria_used siempre <= criteria_total."""
        m = make_metrics(pe_ratio=None, roe=None, debt_to_equity=None)
        result = scorer.score(m)
        assert result.criteria_used <= result.criteria_total

    def test_completeness_warning_in_reasons(self, scorer):
        """Si completeness < 70%, debe haber una advertencia en reasons."""
        m = make_metrics(
            pe_ratio=None, ev_ebitda=None, pb_ratio=None,
            roe=None, net_margin=None, ebitda_margin=None,
        )
        result = scorer.score(m, dcf=None)
        reason_text = " ".join(result.reasons)
        assert "criterios" in reason_text.lower() or "datos" in reason_text.lower()

    def test_partial_data_score_still_valid(self, scorer):
        """Score con datos parciales debe ser válido y no crashear."""
        m = make_metrics(pe_ratio=10.0, ev_ebitda=None, pb_ratio=None, roe=0.15)
        result = scorer.score(m)
        assert isinstance(result.score, int)
        assert result.criteria_used >= 2  # al menos P/E y ROE


# ============================================================
# Alertas críticas
# ============================================================

class TestCriticalAlerts:
    def test_interest_coverage_below_1_forces_sell(self, scorer):
        """IC < 1.0 debe forzar señal SELL aunque el resto sea excelente."""
        m = make_metrics(
            pe_ratio=6.0, ev_ebitda=4.0, roe=0.25,
            interest_coverage=0.8,  # crítico
        )
        result = scorer.score(m)
        assert result.signal == "SELL"
        assert result.signal_override is True
        assert len(result.critical_alerts) >= 1
        assert any("intereses" in a.lower() for a in result.critical_alerts)

    def test_current_ratio_below_08_generates_alert(self, scorer):
        """CR < 0.8 debe generar alerta pero no forzar SELL."""
        m = make_metrics(current_ratio=0.7, interest_coverage=5.0)
        result = scorer.score(m)
        assert any("liquidez" in a.lower() for a in result.critical_alerts)
        # No necesariamente SELL si IC está bien
        assert result.signal_override is False

    def test_high_debt_ebitda_generates_alert(self, scorer):
        """D/EBITDA > 6 debe generar alerta."""
        m = make_metrics(debt_to_ebitda=7.0)
        result = scorer.score(m)
        assert any("apalancamiento" in a.lower() for a in result.critical_alerts)

    def test_severe_losses_generate_alert(self, scorer):
        """Margen neto < -20% debe generar alerta."""
        m = make_metrics(net_margin=-0.25)
        result = scorer.score(m)
        assert any("pérdidas" in a.lower() for a in result.critical_alerts)

    def test_no_alerts_normal_company(self, scorer):
        """Una empresa normal no debe tener alertas críticas."""
        m = make_metrics()
        result = scorer.score(m)
        assert len(result.critical_alerts) == 0
        assert result.signal_override is False

    def test_force_sell_reflected_in_summary(self, scorer):
        """Si hay override, el resumen en reasons[0] debe mencionarlo."""
        m = make_metrics(interest_coverage=0.5)
        result = scorer.score(m)
        assert "SEÑAL FORZADA" in result.reasons[0] or "ALERTA" in result.reasons[0]

    def test_critical_alerts_propagated_to_result(self, scorer):
        """critical_alerts debe estar en to_dict()."""
        m = make_metrics(interest_coverage=0.5)
        result = scorer.score(m)
        d = result.to_dict()
        assert "critical_alerts" in d
        assert len(d["critical_alerts"]) >= 1
        assert d["signal_override"] is True


# ============================================================
# DCF integración
# ============================================================

class TestDCFIntegration:
    def test_excellent_dcf_increases_score(self, scorer):
        """DCF con margen ≥40% debe aumentar el score vs sin DCF."""
        m = make_metrics()
        result_no_dcf = scorer.score(m, dcf=None)
        result_with_dcf = scorer.score(m, dcf=make_dcf(margin_of_safety=45.0))
        assert result_with_dcf.score >= result_no_dcf.score

    def test_negative_dcf_decreases_score(self, scorer):
        """DCF negativo (sobrevalorada) debe bajar el score."""
        m = make_metrics()
        result_good = scorer.score(m, dcf=make_dcf(margin_of_safety=35.0))
        result_bad = scorer.score(m, dcf=make_dcf(margin_of_safety=-30.0))
        assert result_good.score > result_bad.score

    def test_dcf_reason_in_output(self, scorer):
        """DCF debe generar una razón visible."""
        m = make_metrics()
        result = scorer.score(m, dcf=make_dcf(margin_of_safety=30.0))
        reason_text = " ".join(result.reasons)
        assert "DCF" in reason_text or "seguridad" in reason_text

    def test_dcf_overvalued_reason_in_output(self, scorer):
        """DCF sobrevalorado debe mencionar la sobrevaloración."""
        m = make_metrics()
        result = scorer.score(m, dcf=make_dcf(margin_of_safety=-25.0))
        reason_text = " ".join(result.reasons)
        assert "sobrevalorada" in reason_text or "25" in reason_text


# ============================================================
# Score drivers
# ============================================================

class TestScoreDrivers:
    def test_driver_message_when_valuation_high(self, scorer):
        """Debe mencionar 'Impulsado por: Valorización' si val_score ≥ 70."""
        m = make_metrics(
            pe_ratio=5.0, ev_ebitda=3.0, pb_ratio=0.5,
            roe=None, net_margin=None, ebitda_margin=None, revenue_cagr_3y=None,
            gross_margin=None, debt_to_equity=None, interest_coverage=None,
            current_ratio=None, debt_to_ebitda=None,
        )
        result = scorer.score(m, dcf=make_dcf(margin_of_safety=50.0))
        reason_text = " ".join(result.reasons)
        assert "Impulsado por" in reason_text or "Valorización" in reason_text

    def test_driver_message_when_risk_low(self, scorer):
        """Debe mencionar 'Limitado por: Riesgo' si risk_score ≤ 40."""
        m = make_metrics(
            pe_ratio=None, ev_ebitda=None, pb_ratio=None,
            roe=None, net_margin=None, ebitda_margin=None, revenue_cagr_3y=None,
            gross_margin=None,
            debt_to_equity=3.0, interest_coverage=1.2, current_ratio=0.5, debt_to_ebitda=6.0,
        )
        result = scorer.score(m)
        reason_text = " ".join(result.reasons)
        assert "Limitado por" in reason_text or "Riesgo" in reason_text


# ============================================================
# to_dict()
# ============================================================

class TestToDict:
    def test_to_dict_contains_all_fields(self, scorer):
        """to_dict() debe tener todos los campos necesarios."""
        m = make_metrics()
        result = scorer.score(m)
        d = result.to_dict()
        expected_keys = {
            "ticker", "score", "signal", "valuation_score", "quality_score",
            "risk_score", "data_completeness", "criteria_used", "criteria_total",
            "critical_alerts", "signal_override", "reasons",
        }
        assert expected_keys.issubset(d.keys())

    def test_to_dict_signal_in_valid_values(self, scorer):
        """La señal en to_dict() debe ser BUY, HOLD o SELL."""
        m = make_metrics()
        d = scorer.score(m).to_dict()
        assert d["signal"] in ("BUY", "HOLD", "SELL")


# ============================================================
# Thresholds helpers
# ============================================================

class TestThresholds:
    def test_get_thresholds_none_returns_default(self):
        assert _get_thresholds(None) == _DEFAULT_THRESHOLDS

    def test_get_thresholds_all_sectors_defined(self):
        """Todos los sectores del Enum deben tener thresholds o usar el default."""
        for sector in Sector:
            t = _get_thresholds(sector)
            assert t is not None
            assert t.pe_excellent > 0

    def test_banca_ev_does_not_apply(self):
        """Banca debe tener ev_applies=False."""
        t = _get_thresholds(Sector.BANCA)
        assert t.ev_applies is False

    def test_all_other_sectors_ev_applies(self):
        """Todos los sectores excepto Banca deben tener ev_applies=True."""
        for sector in Sector:
            if sector != Sector.BANCA:
                t = _get_thresholds(sector)
                assert t.ev_applies is True, f"{sector} debería tener ev_applies=True"
