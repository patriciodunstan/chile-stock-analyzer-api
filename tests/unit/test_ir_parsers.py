"""Tests unitarios para el sistema de IR scraping y parsing.

Cubre:
- ReportMetadata (value object)
- XLSXFinancialParser (parsing de números, headers, sheets)
- PDFFinancialParser (clasificación de tablas, parsing PDF)
- Normalizer (mapeo de labels, normalización de períodos, merge)
- Registry (factory pattern)
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.infrastructure.external.ir_reports.base_scraper import (
    ReportMetadata, ReportType, ReportFormat, ReportPeriod, DownloadResult,
)
from app.infrastructure.external.ir_reports.sqm_scraper import SQMScraper
from app.infrastructure.external.ir_reports.registry import (
    get_scraper, list_available_scrapers,
)
from app.infrastructure.parsers.xlsx_financial_parser import (
    XLSXFinancialParser, ParsedFinancialData,
)
from app.infrastructure.parsers.pdf_financial_parser import PDFFinancialParser
from app.infrastructure.parsers.normalizer import (
    normalize_all_periods,
    normalize_to_financial_statement,
    _normalize_period_key,
    _match_label_to_field,
)


# ============================================================
# ReportMetadata
# ============================================================

class TestReportMetadata:
    def test_filename_generation(self):
        report = ReportMetadata(
            ticker="SQM-B", company_name="SQM",
            report_type=ReportType.EARNINGS_TABLES,
            report_format=ReportFormat.XLSX,
            period=ReportPeriod.Q4, year=2025,
            url="https://example.com/test.xlsx",
        )
        assert report.filename == "SQM-B_Q4_2025_earnings_tables.xlsx"

    def test_is_tabular_xlsx(self):
        report = ReportMetadata(
            ticker="SQM-B", company_name="SQM",
            report_type=ReportType.EARNINGS_TABLES,
            report_format=ReportFormat.XLSX,
            period=ReportPeriod.Q4, year=2025,
            url="https://example.com/test.xlsx",
        )
        assert report.is_tabular is True

    def test_is_tabular_pdf(self):
        report = ReportMetadata(
            ticker="SQM-B", company_name="SQM",
            report_type=ReportType.FINANCIAL_STATEMENT,
            report_format=ReportFormat.PDF,
            period=ReportPeriod.Q4, year=2025,
            url="https://example.com/test.pdf",
        )
        assert report.is_tabular is False

    def test_frozen_dataclass(self):
        """ReportMetadata es inmutable (frozen)."""
        report = ReportMetadata(
            ticker="SQM-B", company_name="SQM",
            report_type=ReportType.EARNINGS_TABLES,
            report_format=ReportFormat.XLSX,
            period=ReportPeriod.Q4, year=2025,
            url="https://example.com/test.xlsx",
        )
        with pytest.raises(AttributeError):
            report.ticker = "OTHER"


# ============================================================
# ParsedFinancialData
# ============================================================

class TestParsedFinancialData:
    def test_completeness_all_three(self):
        data = ParsedFinancialData(
            source_file="test.xlsx", ticker="SQM-B",
            income_statement={"Q4": {"Revenue": 100}},
            balance_sheet={"Q4": {"Assets": 200}},
            cash_flow={"Q4": {"OCF": 50}},
        )
        assert data.completeness_score == 1.0

    def test_completeness_two_of_three(self):
        data = ParsedFinancialData(
            source_file="test.xlsx", ticker="SQM-B",
            income_statement={"Q4": {"Revenue": 100}},
            balance_sheet={"Q4": {"Assets": 200}},
        )
        assert abs(data.completeness_score - 2/3) < 0.001

    def test_completeness_empty(self):
        data = ParsedFinancialData(source_file="test.xlsx", ticker="SQM-B")
        assert data.completeness_score == 0.0


# ============================================================
# XLSX Parser — Number Parsing
# ============================================================

class TestXLSXNumberParsing:
    def setup_method(self):
        self.parser = XLSXFinancialParser()

    def test_integer(self):
        assert self.parser._parse_number(1234) == 1234.0

    def test_float(self):
        assert self.parser._parse_number(1234.5) == 1234.5

    def test_string_with_commas(self):
        assert self.parser._parse_number("1,234.56") == 1234.56

    def test_negative_parentheses(self):
        assert self.parser._parse_number("(123.4)") == -123.4

    def test_dash_is_zero(self):
        assert self.parser._parse_number("-") == 0.0
        assert self.parser._parse_number("—") == 0.0

    def test_none_returns_none(self):
        assert self.parser._parse_number(None) is None

    def test_na_is_zero(self):
        assert self.parser._parse_number("n/a") == 0.0
        assert self.parser._parse_number("N/A") == 0.0

    def test_dollar_sign_removed(self):
        assert self.parser._parse_number("$1,234") == 1234.0


# ============================================================
# XLSX Parser — Period Key Building
# ============================================================

class TestXLSXPeriodKeyBuilding:
    def setup_method(self):
        self.parser = XLSXFinancialParser()

    def test_quarter_context(self):
        assert self.parser._build_period_key("for the 4th quarter", 2025) == "Q4 2025"

    def test_first_quarter(self):
        assert self.parser._build_period_key("for the 1st quarter", 2025) == "Q1 2025"

    def test_twelve_months(self):
        assert self.parser._build_period_key(
            "for the twelve months ended december 31", 2025
        ) == "FY 2025"

    def test_as_of_dec(self):
        assert self.parser._build_period_key("as of dec. 31", 2025) == "Dec 2025"

    def test_as_of_no_month(self):
        assert self.parser._build_period_key("as of", 2025) == "Dec 2025"

    def test_empty_context_fallback(self):
        assert self.parser._build_period_key("", 2025) == "2025"

    def test_detect_data_columns_sqm_format(self):
        """Simula la estructura real del Income Statement de SQM."""
        rows = [
            (None, None, None, None, None, None, None, None, None, None, None),
            (None, "Consolidated Statement of Income", None, None, None, None, None, None, None, None, None),
            (None, None, None, "For the 4th quarter", None, None, None, "For the twelve months ended December 31", None, None, None),
            (None, "(US$ Millions)", None, None, None, None, None, None, None, None, None),
            (None, None, None, 2025, None, 2024, None, 2025, None, 2024, None),
        ]
        columns = self.parser._detect_data_columns(rows)
        assert len(columns) == 4
        # Verificar period keys
        period_keys = [c.period_key for c in columns]
        assert "Q4 2025" in period_keys
        assert "Q4 2024" in period_keys
        assert "FY 2025" in period_keys
        assert "FY 2024" in period_keys


# ============================================================
# PDF Parser — Number Parsing
# ============================================================

class TestPDFNumberParsing:
    def setup_method(self):
        self.parser = PDFFinancialParser()

    def test_spanish_format(self):
        """1.234,56 → 1234.56 (formato europeo/español)."""
        assert self.parser._parse_pdf_number("1.234,56") == 1234.56

    def test_english_format(self):
        assert self.parser._parse_pdf_number("1,234.56") == 1234.56

    def test_negative_parentheses(self):
        assert self.parser._parse_pdf_number("(500)") == -500.0

    def test_none(self):
        assert self.parser._parse_pdf_number(None) is None


# ============================================================
# PDF Parser — Table Classification
# ============================================================

class TestTableClassification:
    def setup_method(self):
        self.parser = PDFFinancialParser()

    def test_classify_income_statement(self):
        table = [
            ["", "Q4 2025", "Q4 2024"],
            ["Revenue", "4576", "4529"],
            ["Net Income", "588", "-404"],
            ["EBITDA", "900", "850"],
        ]
        assert self.parser._classify_table(table) == "income_statement"

    def test_classify_balance_sheet(self):
        table = [
            ["", "Dec 2025", "Dec 2024"],
            ["Total assets", "13000", "12400"],
            ["Total liabilities", "5800", "5980"],
            ["Total equity", "7200", "6420"],
        ]
        assert self.parser._classify_table(table) == "balance_sheet"

    def test_classify_cash_flow(self):
        table = [
            ["", "FY 2025"],
            ["Cash flows from operating activities", ""],
            ["Cash flows from investing activities", ""],
            ["Cash flows from financing activities", ""],
        ]
        assert self.parser._classify_table(table) == "cash_flow"

    def test_unclassifiable_table(self):
        table = [
            ["Product", "Volume", "Price"],
            ["Lithium", "100", "25"],
        ]
        assert self.parser._classify_table(table) is None


# ============================================================
# Normalizer — Period Keys
# ============================================================

class TestPeriodNormalization:
    def test_q4_2025(self):
        assert _normalize_period_key("Q4 2025", "SQM") == "2025-Q4"

    def test_4q2025(self):
        assert _normalize_period_key("4Q2025", "SQM") == "2025-Q4"

    def test_fy_2025(self):
        assert _normalize_period_key("FY 2025", "SQM") == "2025-FY"

    def test_dec_2025(self):
        assert _normalize_period_key("Dec 2025", "SQM") == "2025-Q4"

    def test_mar_2025(self):
        assert _normalize_period_key("Mar 2025", "SQM") == "2025-Q1"

    def test_spanish_month(self):
        assert _normalize_period_key("Dic 2025", "SQM") == "2025-Q4"


# ============================================================
# Normalizer — Field Matching
# ============================================================

class TestFieldMatching:
    def test_exact_match(self):
        assert _match_label_to_field("Revenue") == "revenue"

    def test_variant_match(self):
        assert _match_label_to_field("Total Revenue") == "revenue"

    def test_spanish_match(self):
        assert _match_label_to_field("Ingresos netos") == "revenue"

    def test_balance_match(self):
        assert _match_label_to_field("Total assets") == "total_assets"

    def test_cashflow_match(self):
        assert _match_label_to_field("Free Cash Flow") == "free_cash_flow"

    def test_no_match(self):
        assert _match_label_to_field("Some random metric XYZ") is None


# ============================================================
# Normalizer — Full Integration
# ============================================================

class TestNormalizerIntegration:
    def test_normalize_merges_periods(self):
        """Q4 2025 del IS y Dec 2025 del BS deben mergearse en 2025-Q4."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="SQM-B",
            income_statement={"Q4 2025": {"Revenues": 4576.0, "Net income": 588.0}},
            balance_sheet={"Dec 2025": {"Total assets": 13000.0, "Total equity": 7200.0}},
            cash_flow={},
        )

        statements = normalize_all_periods(parsed)

        # Debe haber exactamente 1 período
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.period == "2025-Q4"
        assert stmt.revenue == 4576.0
        assert stmt.net_income == 588.0
        assert stmt.total_assets == 13000.0
        assert stmt.total_equity == 7200.0

    def test_derived_fields_calculated(self):
        """gross_profit y FCF se calculan si faltan."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="TEST",
            income_statement={"Q1 2025": {
                "Revenues": 1000.0,
                "Cost of sales": -600.0,
            }},
            cash_flow={"Q1 2025": {
                "Net cash from operating activities": 200.0,
                "Capital expenditures": -50.0,
            }},
        )

        statements = normalize_all_periods(parsed)
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.gross_profit == 400.0  # 1000 + (-600)
        assert stmt.free_cash_flow == 150.0  # 200 + (-50)

    def test_ebitda_data_included_in_normalization(self):
        """ebitda_data debe mergearse con los otros estados financieros."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="SQM-B",
            income_statement={"Q4 2025": {"Revenues": 1300.0, "Operating income": 300.0}},
            ebitda_data={"Q4 2025": {
                "EBITDA": 450.0,
                "Depreciation and amortization expenses": -150.0,
            }},
        )

        statements = normalize_all_periods(parsed)
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.revenue == 1300.0
        assert stmt.ebitda == 450.0  # Directo del ebitda_data

    def test_total_debt_from_components(self):
        """total_debt se calcula de short_term_debt + long_term_debt."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="SQM-B",
            balance_sheet={"Dec 2025": {
                "Total assets": 13000.0,
                "Short-term debt": 500.0,
                "Long-term debt": 2000.0,
            }},
        )

        statements = normalize_all_periods(parsed)
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.total_debt == 2500.0  # 500 + 2000

    def test_ebitda_derived_from_ebit_plus_da(self):
        """EBITDA = EBIT + D&A cuando no viene directo."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="TEST",
            income_statement={"Q1 2025": {
                "Revenues": 1000.0,
                "EBIT": 200.0,
            }},
            ebitda_data={"Q1 2025": {
                "Depreciation and amortization": 80.0,
            }},
        )

        statements = normalize_all_periods(parsed)
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.ebitda == 280.0  # 200 + 80

    def test_financial_expenses_maps_to_interest_expense(self):
        """'Financial expenses' de SQM se mapea a interest_expense."""
        assert _match_label_to_field("Financial expenses") == "interest_expense"

    def test_profit_for_the_period_maps_to_net_income(self):
        """'Profit for the period' de SQM se mapea a net_income."""
        assert _match_label_to_field("Profit for the period") == "net_income"

    def test_exclusion_total_liabilities_and_equity(self):
        """'Total Liabilities & Shareholders' Equity' NO debe mapear a total_liabilities."""
        assert _match_label_to_field("Total Liabilities & Shareholders' Equity") is None

    def test_exclusion_net_income_before_minority(self):
        """'Net Income before minority interest' NO debe mapear a net_income."""
        assert _match_label_to_field("Net Income before minority interest") is None

    def test_shareholders_equity_maps(self):
        """'Shareholders' Equity' mapea a total_equity."""
        assert _match_label_to_field("Shareholders' Equity") == "total_equity"

    def test_total_liabilities_direct_maps(self):
        """'Total liabilities' directo sí mapea correctamente."""
        assert _match_label_to_field("Total liabilities") == "total_liabilities"

    def test_source_priority_is_over_ebitda(self):
        """IS 'Net Income' (183.8) tiene prioridad sobre EBITDA 'Profit for the Period' (232.9)."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="SQM-B",
            income_statement={"Q4 2025": {
                "Net Income": 183.8,
                "Revenues": 1323.9,
            }},
            ebitda_data={"Q4 2025": {
                "Profit for the Period": 232.9,
                "EBITDA": 497.2,
            }},
        )

        statements = normalize_all_periods(parsed)
        assert len(statements) == 1
        stmt = statements[0]
        # IS tiene prioridad → net_income = 183.8, no 232.9
        assert stmt.net_income == 183.8
        # EBITDA sí se toma del ebitda_data
        assert stmt.ebitda == 497.2

    def test_total_liabilities_calculated_from_equity_equation(self):
        """total_liabilities = total_assets - total_equity si no hay dato directo."""
        parsed = ParsedFinancialData(
            source_file="test.xlsx",
            ticker="SQM-B",
            balance_sheet={"Dec 2025": {
                "Total assets": 14504.8,
                "Total Shareholders' Equity": 8053.9,
                "Total Current Liabilities": 1768.8,
                "Total Long-Term Liabilities": 4682.2,
            }},
        )

        statements = normalize_all_periods(parsed)
        assert len(statements) == 1
        stmt = statements[0]
        assert stmt.total_equity == 8053.9
        # total_liabilities = current + long-term
        assert abs(stmt.total_liabilities - 6451.0) < 0.1


# ============================================================
# Registry
# ============================================================

class TestRegistry:
    def test_get_sqm_scraper(self):
        scraper = get_scraper("SQM-B", data_dir=Path("/tmp/test"))
        assert isinstance(scraper, SQMScraper)
        assert scraper.ticker == "SQM-B"

    def test_alias_sqm(self):
        scraper = get_scraper("SQM", data_dir=Path("/tmp/test"))
        assert isinstance(scraper, SQMScraper)

    def test_invalid_ticker_raises(self):
        with pytest.raises(ValueError, match="No hay scraper"):
            get_scraper("INVALID")

    def test_list_available(self):
        available = list_available_scrapers()
        assert "SQM-B" in available
