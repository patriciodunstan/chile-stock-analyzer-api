"""Tests unitarios para MetricsCalculatorService.

Cubre:
- Ratios de valorización (P/E, P/B, P/S, EV/EBITDA, EV/EBIT)
- Ratios de rentabilidad (ROE, ROA, ROIC, márgenes)
- Ratios de deuda/solvencia (D/E, D/EBITDA, interest coverage, current ratio)
- Ratios de dividendos (yield, payout)
- CAGR de crecimiento (revenue, net income)
- Edge cases (divisiones por cero, datos faltantes)
"""
import pytest

from app.domain.entities.financial import FinancialStatement, FundamentalMetrics
from app.domain.entities.stock import StockPrice
from app.domain.services.metrics_calculator import MetricsCalculatorService


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def calculator():
    return MetricsCalculatorService()


@pytest.fixture
def sample_statement() -> FinancialStatement:
    """SQM-like financials anuales para testing de ratios base."""
    return FinancialStatement(
        ticker="SQM-B",
        period="2025-FY",
        revenue=4576.0,
        cost_of_revenue=-2800.0,
        gross_profit=1776.0,
        operating_income=900.0,
        ebitda=1200.0,
        ebit=950.0,
        net_income=588.0,
        interest_expense=-150.0,
        total_assets=13000.0,
        total_liabilities=5800.0,
        total_equity=7200.0,
        total_debt=3500.0,
        cash_and_equivalents=1200.0,
        current_assets=5000.0,
        current_liabilities=3000.0,
        operating_cash_flow=1100.0,
        capital_expenditure=-400.0,
        free_cash_flow=700.0,
        dividends_paid=-200.0,
        shares_outstanding=286_000_000,
    )


@pytest.fixture
def sample_price() -> StockPrice:
    return StockPrice(
        ticker="SQM-B",
        price=45000.0,
        market_cap=45000.0 * 286_000_000,  # ~12.87T CLP
    )


# ============================================================
# Valuation Ratios
# ============================================================

class TestValuationRatios:
    def test_pe_ratio(self, calculator, sample_statement, sample_price):
        """P/E = price / EPS = price / (net_income / shares)."""
        metrics = calculator.calculate(sample_statement, sample_price)
        # EPS = 588 / 286M ≈ 0.002056
        # P/E = 45000 / 0.002056 ≈ 21,882 → pero en MUSD: 45000 / (588M/286M)
        # Realmente: market_cap / net_income
        # market_cap = 45000 * 286M = 12.87T
        # P/E = 12.87T / 588 ... depende de unidades.
        # Simplificamos: P/E = market_cap / (net_income * unit_multiplier)
        # Para el test, net_income está en MUSD y market_cap en CLP
        # Usamos price/EPS donde EPS = net_income/shares
        assert metrics.pe_ratio is not None
        assert metrics.pe_ratio > 0

    def test_pe_ratio_negative_earnings(self, calculator, sample_price):
        """P/E debe ser None si net_income <= 0."""
        stmt = FinancialStatement(ticker="TEST", period="2025-Q4", net_income=-100)
        metrics = calculator.calculate(stmt, sample_price)
        assert metrics.pe_ratio is None

    def test_pb_ratio(self, calculator, sample_statement, sample_price):
        """P/B = market_cap / total_equity."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.pb_ratio is not None
        assert metrics.pb_ratio > 0

    def test_ps_ratio(self, calculator, sample_statement, sample_price):
        """P/S = market_cap / revenue."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.ps_ratio is not None
        assert metrics.ps_ratio > 0

    def test_ev_ebitda(self, calculator, sample_statement, sample_price):
        """EV/EBITDA = enterprise_value / EBITDA."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.ev_ebitda is not None
        assert metrics.ev_ebitda > 0

    def test_ev_ebitda_zero_ebitda(self, calculator, sample_price):
        """EV/EBITDA debe ser None si EBITDA == 0."""
        stmt = FinancialStatement(ticker="TEST", period="2025-Q4", ebitda=0)
        metrics = calculator.calculate(stmt, sample_price)
        assert metrics.ev_ebitda is None

    def test_ev_ebit(self, calculator, sample_statement, sample_price):
        """EV/EBIT = enterprise_value / EBIT."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.ev_ebit is not None
        assert metrics.ev_ebit > 0


# ============================================================
# Profitability Ratios
# ============================================================

class TestProfitabilityRatios:
    def test_roe(self, calculator, sample_statement, sample_price):
        """ROE = net_income / total_equity."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 588.0 / 7200.0
        assert metrics.roe == pytest.approx(expected, rel=1e-3)

    def test_roa(self, calculator, sample_statement, sample_price):
        """ROA = net_income / total_assets."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 588.0 / 13000.0
        assert metrics.roa == pytest.approx(expected, rel=1e-3)

    def test_roic(self, calculator, sample_statement, sample_price):
        """ROIC = EBIT * (1-tax_rate) / invested_capital."""
        metrics = calculator.calculate(sample_statement, sample_price)
        # invested_capital = total_equity + total_debt - cash
        # = 7200 + 3500 - 1200 = 9500
        # tax_rate implícita = 1 - (net_income/ebit) ≈ 1 - (588/950) ≈ 0.381
        # nopat = 950 * (1 - 0.381) = 587.9
        # ROIC = 587.9 / 9500 ≈ 0.0619
        assert metrics.roic is not None
        assert 0 < metrics.roic < 1

    def test_net_margin(self, calculator, sample_statement, sample_price):
        """Net Margin = net_income / revenue."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 588.0 / 4576.0
        assert metrics.net_margin == pytest.approx(expected, rel=1e-3)

    def test_ebitda_margin(self, calculator, sample_statement, sample_price):
        """EBITDA Margin = EBITDA / revenue."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 1200.0 / 4576.0
        assert metrics.ebitda_margin == pytest.approx(expected, rel=1e-3)

    def test_gross_margin(self, calculator, sample_statement, sample_price):
        """Gross Margin = gross_profit / revenue."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 1776.0 / 4576.0
        assert metrics.gross_margin == pytest.approx(expected, rel=1e-3)

    def test_roe_zero_equity(self, calculator, sample_price):
        """ROE debe ser None si equity == 0."""
        stmt = FinancialStatement(
            ticker="TEST", period="2025-Q4",
            net_income=100, total_equity=0,
        )
        metrics = calculator.calculate(stmt, sample_price)
        assert metrics.roe is None

    def test_margins_zero_revenue(self, calculator, sample_price):
        """Márgenes deben ser None si revenue == 0."""
        stmt = FinancialStatement(
            ticker="TEST", period="2025-Q4",
            revenue=0, net_income=100,
        )
        metrics = calculator.calculate(stmt, sample_price)
        assert metrics.net_margin is None
        assert metrics.gross_margin is None
        assert metrics.ebitda_margin is None


# ============================================================
# Leverage Ratios
# ============================================================

class TestLeverageRatios:
    def test_debt_to_equity(self, calculator, sample_statement, sample_price):
        """D/E = total_debt / total_equity."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 3500.0 / 7200.0
        assert metrics.debt_to_equity == pytest.approx(expected, rel=1e-3)

    def test_debt_to_ebitda(self, calculator, sample_statement, sample_price):
        """D/EBITDA = total_debt / EBITDA."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 3500.0 / 1200.0
        assert metrics.debt_to_ebitda == pytest.approx(expected, rel=1e-3)

    def test_interest_coverage(self, calculator, sample_statement, sample_price):
        """Interest coverage = EBIT / |interest_expense|."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 950.0 / 150.0
        assert metrics.interest_coverage == pytest.approx(expected, rel=1e-3)

    def test_current_ratio(self, calculator, sample_statement, sample_price):
        """Current ratio = current_assets / current_liabilities."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 5000.0 / 3000.0
        assert metrics.current_ratio == pytest.approx(expected, rel=1e-3)

    def test_interest_coverage_no_expense(self, calculator, sample_price):
        """Interest coverage debe ser None si interest_expense == 0."""
        stmt = FinancialStatement(
            ticker="TEST", period="2025-Q4",
            ebit=100, interest_expense=0,
        )
        metrics = calculator.calculate(stmt, sample_price)
        assert metrics.interest_coverage is None


# ============================================================
# Dividend Ratios
# ============================================================

class TestDividendRatios:
    def test_dividend_yield(self, calculator, sample_statement, sample_price):
        """Dividend Yield = |dividends_paid| / market_cap."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.dividend_yield is not None
        assert metrics.dividend_yield >= 0

    def test_payout_ratio(self, calculator, sample_statement, sample_price):
        """Payout Ratio = |dividends_paid| / net_income."""
        metrics = calculator.calculate(sample_statement, sample_price)
        expected = 200.0 / 588.0
        assert metrics.payout_ratio == pytest.approx(expected, rel=1e-3)

    def test_payout_ratio_no_dividends(self, calculator, sample_price):
        """Payout debe ser None si no hay dividendos."""
        stmt = FinancialStatement(
            ticker="TEST", period="2025-Q4",
            net_income=100, dividends_paid=0,
        )
        metrics = calculator.calculate(stmt, sample_price)
        assert metrics.payout_ratio is None


# ============================================================
# Growth (CAGR)
# ============================================================

class TestGrowthRatios:
    def test_cagr_with_history(self, calculator, sample_price):
        """CAGR se calcula con lista histórica de statements."""
        statements = [
            FinancialStatement(ticker="TEST", period="2022-Q4", revenue=1000, net_income=100),
            FinancialStatement(ticker="TEST", period="2023-Q4", revenue=1100, net_income=120),
            FinancialStatement(ticker="TEST", period="2024-Q4", revenue=1210, net_income=140),
            FinancialStatement(ticker="TEST", period="2025-Q4", revenue=1331, net_income=160),
        ]
        metrics = calculator.calculate(
            statements[-1], sample_price, historical_statements=statements
        )
        # Revenue CAGR 3y = (1331/1000)^(1/3) - 1 ≈ 0.1 (10%)
        assert metrics.revenue_cagr_3y is not None
        assert metrics.revenue_cagr_3y == pytest.approx(0.1, rel=0.02)

    def test_cagr_insufficient_history(self, calculator, sample_statement, sample_price):
        """CAGR None si no hay suficiente historial."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.revenue_cagr_3y is None
        assert metrics.net_income_cagr_3y is None

    def test_cagr_with_negative_base(self, calculator, sample_price):
        """CAGR None si el valor base es negativo (no se puede calcular)."""
        statements = [
            FinancialStatement(ticker="TEST", period="2022-Q4", revenue=-100, net_income=-50),
            FinancialStatement(ticker="TEST", period="2023-Q4", revenue=200, net_income=20),
            FinancialStatement(ticker="TEST", period="2024-Q4", revenue=300, net_income=40),
            FinancialStatement(ticker="TEST", period="2025-Q4", revenue=400, net_income=60),
        ]
        metrics = calculator.calculate(
            statements[-1], sample_price, historical_statements=statements
        )
        assert metrics.revenue_cagr_3y is None


# ============================================================
# Edge Cases
# ============================================================

class TestEdgeCases:
    def test_empty_statement(self, calculator, sample_price):
        """Statement con todos los campos en 0 no debe crashear."""
        stmt = FinancialStatement(ticker="TEST", period="2025-Q4")
        metrics = calculator.calculate(stmt, sample_price)
        assert isinstance(metrics, FundamentalMetrics)
        assert metrics.ticker == "TEST"
        assert metrics.period == "2025-Q4"

    def test_no_price_data(self, calculator, sample_statement):
        """Sin price data, ratios de market deben ser None."""
        price = StockPrice(ticker="SQM-B", price=0, market_cap=0)
        metrics = calculator.calculate(sample_statement, price)
        assert metrics.pe_ratio is None
        assert metrics.pb_ratio is None
        assert metrics.ps_ratio is None

    def test_ticker_and_period_propagated(self, calculator, sample_statement, sample_price):
        """Ticker y period deben propagarse al resultado."""
        metrics = calculator.calculate(sample_statement, sample_price)
        assert metrics.ticker == "SQM-B"
        assert metrics.period == "2025-FY"


# ============================================================
# Annualization (Quarterly → Annual)
# ============================================================

class TestAnnualization:
    """Verifica que datos trimestrales se anualizan (×4) para ratios stock/flujo."""

    @pytest.fixture
    def quarterly_statement(self) -> FinancialStatement:
        """Statement trimestral con flujos de 1 quarter."""
        return FinancialStatement(
            ticker="TEST",
            period="2025-Q4",
            revenue=1000.0,
            gross_profit=400.0,
            operating_income=200.0,
            ebitda=300.0,
            ebit=250.0,
            net_income=150.0,
            interest_expense=-50.0,
            total_assets=10000.0,
            total_equity=6000.0,
            total_debt=2000.0,
            cash_and_equivalents=500.0,
            current_assets=4000.0,
            current_liabilities=2500.0,
            dividends_paid=-60.0,
        )

    @pytest.fixture
    def fy_statement(self) -> FinancialStatement:
        """Mismo statement pero con period FY (flujos ya anuales)."""
        return FinancialStatement(
            ticker="TEST",
            period="2025-FY",
            revenue=1000.0,
            gross_profit=400.0,
            operating_income=200.0,
            ebitda=300.0,
            ebit=250.0,
            net_income=150.0,
            interest_expense=-50.0,
            total_assets=10000.0,
            total_equity=6000.0,
            total_debt=2000.0,
            cash_and_equivalents=500.0,
            current_assets=4000.0,
            current_liabilities=2500.0,
            dividends_paid=-60.0,
        )

    @pytest.fixture
    def price(self) -> StockPrice:
        return StockPrice(ticker="TEST", price=100.0, market_cap=12000.0)

    def test_annualization_factor_quarterly(self, calculator):
        assert calculator._annualization_factor("2025-Q4") == 4
        assert calculator._annualization_factor("2024-Q1") == 4

    def test_annualization_factor_semiannual(self, calculator):
        assert calculator._annualization_factor("2025-H1") == 2

    def test_annualization_factor_annual(self, calculator):
        assert calculator._annualization_factor("2025-FY") == 1
        assert calculator._annualization_factor("2025") == 1

    def test_pe_quarterly_annualized(self, calculator, quarterly_statement, price):
        """P/E trimestral usa net_income×4."""
        metrics = calculator.calculate(quarterly_statement, price)
        # P/E = market_cap / (net_income * 4) = 12000 / (150*4) = 12000/600 = 20
        assert metrics.pe_ratio == pytest.approx(20.0, rel=1e-3)

    def test_pe_fy_not_annualized(self, calculator, fy_statement, price):
        """P/E anual usa net_income sin multiplicar."""
        metrics = calculator.calculate(fy_statement, price)
        # P/E = market_cap / net_income = 12000 / 150 = 80
        assert metrics.pe_ratio == pytest.approx(80.0, rel=1e-3)

    def test_ev_ebitda_quarterly_annualized(self, calculator, quarterly_statement, price):
        """EV/EBITDA trimestral usa EBITDA×4."""
        metrics = calculator.calculate(quarterly_statement, price)
        # EV = 12000 + 2000 - 500 = 13500
        # EV/EBITDA = 13500 / (300*4) = 13500/1200 = 11.25
        assert metrics.ev_ebitda == pytest.approx(11.25, rel=1e-3)

    def test_debt_to_ebitda_quarterly_annualized(self, calculator, quarterly_statement, price):
        """Debt/EBITDA trimestral usa EBITDA×4 (deuda es stock, no se anualiza)."""
        metrics = calculator.calculate(quarterly_statement, price)
        # D/EBITDA = 2000 / (300*4) = 2000/1200 = 1.667
        assert metrics.debt_to_ebitda == pytest.approx(1.667, rel=1e-2)

    def test_interest_coverage_quarterly(self, calculator, quarterly_statement, price):
        """Interest coverage: ratio EBIT/interest se mantiene igual (ambos ×4)."""
        metrics = calculator.calculate(quarterly_statement, price)
        # (250*4) / abs(-50*4) = 1000/200 = 5.0
        assert metrics.interest_coverage == pytest.approx(5.0, rel=1e-3)

    def test_interest_coverage_negative_expense(self, calculator, price):
        """Interest coverage funciona con interest_expense negativo."""
        stmt = FinancialStatement(
            ticker="TEST", period="2025-FY",
            ebit=500.0, interest_expense=-100.0,
        )
        metrics = calculator.calculate(stmt, price)
        assert metrics.interest_coverage == pytest.approx(5.0, rel=1e-3)

    def test_roe_quarterly_annualized(self, calculator, quarterly_statement, price):
        """ROE trimestral = net_income_ann / equity (equity es stock)."""
        metrics = calculator.calculate(quarterly_statement, price)
        # ROE = (150*4) / 6000 = 600/6000 = 0.1
        assert metrics.roe == pytest.approx(0.1, rel=1e-3)

    def test_margins_not_annualized(self, calculator, quarterly_statement, fy_statement, price):
        """Márgenes (flujo/flujo) son iguales entre Q y FY con mismos valores."""
        q_metrics = calculator.calculate(quarterly_statement, price)
        fy_metrics = calculator.calculate(fy_statement, price)
        assert q_metrics.net_margin == pytest.approx(fy_metrics.net_margin, rel=1e-6)
        assert q_metrics.ebitda_margin == pytest.approx(fy_metrics.ebitda_margin, rel=1e-6)
        assert q_metrics.gross_margin == pytest.approx(fy_metrics.gross_margin, rel=1e-6)

    def test_balance_ratios_not_annualized(self, calculator, quarterly_statement, fy_statement, price):
        """Ratios stock/stock (D/E, current ratio) son iguales entre Q y FY."""
        q_metrics = calculator.calculate(quarterly_statement, price)
        fy_metrics = calculator.calculate(fy_statement, price)
        assert q_metrics.debt_to_equity == pytest.approx(fy_metrics.debt_to_equity, rel=1e-6)
        assert q_metrics.current_ratio == pytest.approx(fy_metrics.current_ratio, rel=1e-6)

    def test_pb_ratio_not_annualized(self, calculator, quarterly_statement, fy_statement, price):
        """P/B (market_cap/equity) es igual en Q y FY — equity es stock."""
        q_metrics = calculator.calculate(quarterly_statement, price)
        fy_metrics = calculator.calculate(fy_statement, price)
        assert q_metrics.pb_ratio == pytest.approx(fy_metrics.pb_ratio, rel=1e-6)
