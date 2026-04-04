"""Tests unitarios para DCFValuationService.

TDD: Red → Green → Refactor.
"""
import pytest
from app.domain.services.dcf_valuation import (
    DCFValuationService,
    DCFResult,
    DCFParameters,
)
from app.domain.entities.financial import FinancialStatement


@pytest.fixture
def service():
    return DCFValuationService()


@pytest.fixture
def sqm_statement():
    """Statement basado en datos reales de SQM Q4 2025."""
    return FinancialStatement(
        ticker="SQM-B",
        period="2025-Q4",
        revenue=1323.9,
        cost_of_revenue=-875.3,
        gross_profit=448.5,
        ebitda=497.2,
        net_income=183.8,
        interest_expense=-46.0,
        total_assets=14504.8,
        total_liabilities=6451.0,
        total_equity=5691.3,
        total_debt=4691.4,
        cash_and_equivalents=1750.3,
        current_assets=5780.4,
        current_liabilities=1768.8,
    )


@pytest.fixture
def sqm_history():
    """4 períodos de historial para proyección."""
    return [
        FinancialStatement(
            ticker="SQM-B", period="2024-Q4",
            revenue=1073.8, ebitda=323.6, net_income=120.1,
            operating_cash_flow=0, capital_expenditure=0,
        ),
        FinancialStatement(
            ticker="SQM-B", period="2024-FY",
            revenue=4528.8, ebitda=1514.4, net_income=-404.4,
        ),
        FinancialStatement(
            ticker="SQM-B", period="2025-FY",
            revenue=4576.2, ebitda=1576.0, net_income=588.1,
        ),
        FinancialStatement(
            ticker="SQM-B", period="2025-Q4",
            revenue=1323.9, ebitda=497.2, net_income=183.8,
            total_debt=4691.4, total_equity=5691.3,
            cash_and_equivalents=1750.3,
        ),
    ]


class TestDCFParameters:
    def test_default_parameters(self):
        params = DCFParameters()
        assert params.projection_years == 5
        assert 0.08 <= params.wacc <= 0.15
        assert 0.02 <= params.terminal_growth_rate <= 0.04
        assert params.margin_of_safety_pct == 0.25

    def test_custom_parameters(self):
        params = DCFParameters(wacc=0.12, terminal_growth_rate=0.025)
        assert params.wacc == 0.12
        assert params.terminal_growth_rate == 0.025


class TestDCFResult:
    def test_result_fields(self):
        result = DCFResult(
            ticker="SQM-B",
            intrinsic_value_per_share=52000.0,
            market_price=41000.0,
            margin_of_safety=26.8,
            signal="BUY",
            projected_fcf=[100, 110, 121, 133, 146],
            terminal_value=2000.0,
            enterprise_value=3500.0,
            equity_value=2800.0,
            wacc_used=0.10,
            growth_rate_used=0.10,
        )
        assert result.signal == "BUY"
        assert result.margin_of_safety > 25.0


class TestDCFCalculation:
    def test_basic_dcf_returns_result(self, service, sqm_statement, sqm_history):
        """DCF con datos válidos retorna resultado completo."""
        result = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=41000.0,
        )
        assert isinstance(result, DCFResult)
        assert result.ticker == "SQM-B"
        assert result.intrinsic_value_per_share > 0
        assert result.enterprise_value > 0
        assert len(result.projected_fcf) == 5

    def test_dcf_projects_five_years(self, service, sqm_statement, sqm_history):
        """Proyección debe ser exactamente 5 años."""
        result = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=41000.0,
        )
        assert len(result.projected_fcf) == 5
        # Cada FCF proyectado debe ser positivo (asumiendo empresa rentable)
        assert all(fcf > 0 for fcf in result.projected_fcf)

    def test_dcf_terminal_value_positive(self, service, sqm_statement, sqm_history):
        result = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=41000.0,
        )
        assert result.terminal_value > 0

    def test_dcf_with_custom_params(self, service, sqm_statement, sqm_history):
        """WACC más alto → valor intrínseco más bajo."""
        params_low = DCFParameters(wacc=0.08)
        params_high = DCFParameters(wacc=0.15)

        result_low = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=41000.0,
            params=params_low,
        )
        result_high = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=41000.0,
            params=params_high,
        )
        assert result_low.intrinsic_value_per_share > result_high.intrinsic_value_per_share

    def test_buy_signal_when_undervalued(self, service, sqm_statement, sqm_history):
        """Si valor intrínseco >> precio, señal BUY.

        NOTA: EEFF en USD millones → intrinsic ~32 USD/share.
        Usamos precio en USD para consistencia de unidades.
        """
        result = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=5.0,  # USD, artificialmente bajo vs ~32 USD intrinsic
        )
        assert result.signal == "BUY"
        assert result.margin_of_safety > 50

    def test_sell_signal_when_overvalued(self, service, sqm_statement, sqm_history):
        """Si precio >> valor intrínseco, señal SELL."""
        result = service.calculate(
            latest=sqm_statement,
            historical=sqm_history,
            shares_outstanding=286_000_000,
            market_price=999.0,  # USD, muy por encima de ~32 USD intrinsic
        )
        assert result.signal == "SELL"
        assert result.margin_of_safety < 0


class TestDCFEdgeCases:
    def test_no_history_uses_defaults(self, service, sqm_statement):
        """Sin historial, usa growth rate por defecto."""
        result = service.calculate(
            latest=sqm_statement,
            historical=[],
            shares_outstanding=286_000_000,
            market_price=41000.0,
        )
        assert isinstance(result, DCFResult)
        assert result.intrinsic_value_per_share > 0

    def test_zero_shares_raises(self, service, sqm_statement):
        """shares_outstanding = 0 debe lanzar error."""
        with pytest.raises(ValueError, match="shares_outstanding"):
            service.calculate(
                latest=sqm_statement,
                historical=[],
                shares_outstanding=0,
                market_price=41000.0,
            )

    def test_negative_ebitda_handles_gracefully(self, service):
        """Empresa con EBITDA negativo (en pérdidas)."""
        loss_stmt = FinancialStatement(
            ticker="LOSS", period="2025-Q4",
            revenue=100.0, ebitda=-50.0, net_income=-80.0,
            total_debt=200.0, cash_and_equivalents=50.0,
            total_equity=100.0,
        )
        result = service.calculate(
            latest=loss_stmt,
            historical=[],
            shares_outstanding=1_000_000,
            market_price=100.0,
        )
        # Con EBITDA negativo, no puede proyectar FCF positivo
        # Debe retornar señal SELL o valor muy bajo
        assert result.signal in ("SELL", "HOLD")

    def test_uses_ebitda_as_fcf_proxy_when_no_cashflow(self, service, sqm_statement):
        """Cuando no hay Cash Flow, usa EBITDA como proxy de FCF."""
        # sqm_statement tiene operating_cash_flow = 0 (no disponible)
        result = service.calculate(
            latest=sqm_statement,
            historical=[],
            shares_outstanding=286_000_000,
            market_price=41000.0,
        )
        # El FCF base debe derivarse de EBITDA
        assert result.projected_fcf[0] > 0
