"""Test end-to-end del IR Scraper + Parser.

Ejecutar en tu máquina local:
    cd chile-stock-analyzer
    pip install httpx beautifulsoup4 openpyxl pdfplumber
    python scripts/test_ir_scraper.py

Este script:
1. Conecta a ir.sqm.com y descubre reportes disponibles
2. Descarga el XLSX de Earnings Release Tables (Q4 2025)
3. Parsea el XLSX y extrae Income Statement, Balance Sheet, Cash Flow
4. Muestra los datos extraídos en consola
5. Valida la calidad de la extracción
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Agregar el directorio raíz al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.external.ir_reports.base_scraper import (
    ReportFormat,
    ReportPeriod,
)
from app.infrastructure.external.ir_reports.sqm_scraper import SQMScraper
from app.infrastructure.parsers.xlsx_financial_parser import XLSXFinancialParser
from app.infrastructure.parsers.pdf_financial_parser import PDFFinancialParser
from app.infrastructure.parsers.normalizer import normalize_all_periods

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def print_header(text: str):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def print_financial_data(title: str, data: dict[str, dict[str, float | None]]):
    """Imprime datos financieros extraídos de forma legible."""
    print(f"\n--- {title} ---")

    if not data:
        print("  (sin datos)")
        return

    periods = list(data.keys())
    print(f"  Períodos: {periods}")

    # Obtener todas las métricas (unión de todos los períodos)
    all_metrics = set()
    for period_data in data.values():
        all_metrics.update(period_data.keys())

    # Imprimir tabla
    metric_width = 45
    value_width = 18

    header = f"  {'Métrica':<{metric_width}}"
    for p in periods[:4]:  # Max 4 períodos
        header += f" {p:>{value_width}}"
    print(header)
    print(f"  {'-' * (metric_width + value_width * min(len(periods), 4) + 4)}")

    for metric in sorted(all_metrics):
        row = f"  {metric:<{metric_width}}"
        for p in periods[:4]:
            val = data[p].get(metric)
            if val is not None:
                if abs(val) >= 1000:
                    row += f" {val:>{value_width},.1f}"
                elif abs(val) >= 1:
                    row += f" {val:>{value_width},.2f}"
                else:
                    row += f" {val:>{value_width},.4f}"
            else:
                row += f" {'N/A':>{value_width}}"
        print(row)


async def test_sqm_scraper():
    """Test completo: discover → download → parse."""
    print_header("TEST IR SCRAPER + PARSER — SQM")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    data_dir = Path("data/reports")
    data_dir.mkdir(parents=True, exist_ok=True)

    scraper = SQMScraper(data_dir=data_dir)

    # ============================================================
    # Paso 1: Descubrir reportes
    # ============================================================
    print_header("PASO 1: Descubriendo reportes en ir.sqm.com")

    try:
        reports = await scraper.discover_reports()
    except Exception as e:
        print(f"  ERROR al descubrir reportes: {e}")
        await scraper.close()
        return

    if not reports:
        print("  No se encontraron reportes. Posible cambio en la estructura del sitio.")
        await scraper.close()
        return

    print(f"\n  Reportes descubiertos: {len(reports)}")
    for r in reports:
        print(f"    {r.period.value} {r.year} | {r.report_type.value:25s} | {r.report_format.value} | {r.url[:60]}...")

    # ============================================================
    # Paso 2: Filtrar y descargar XLSX (prioridad)
    # ============================================================
    print_header("PASO 2: Descargando reportes XLSX")

    xlsx_reports = [r for r in reports if r.report_format == ReportFormat.XLSX]
    pdf_reports = [r for r in reports if r.report_format == ReportFormat.PDF]

    if xlsx_reports:
        print(f"  XLSX disponibles: {len(xlsx_reports)}")
        # Descargar el más reciente
        target = xlsx_reports[0]
        print(f"  Descargando: {target.filename}...")

        result = await scraper.download_report(target)

        if result.success:
            print(f"  OK: {result.local_path} ({result.bytes_downloaded:,} bytes)")

            # ============================================================
            # Paso 3: Parsear XLSX
            # ============================================================
            print_header("PASO 3: Parseando XLSX")

            parser = XLSXFinancialParser()
            parsed = parser.parse(result.local_path, ticker="SQM-B")

            print(f"  Moneda: {parsed.currency}")
            print(f"  Unidad: {parsed.unit}")
            print(f"  Períodos: {parsed.periods_found}")
            print(f"  Completitud: {parsed.completeness_score:.0%}")

            print_financial_data("INCOME STATEMENT", parsed.income_statement)
            print_financial_data("BALANCE SHEET", parsed.balance_sheet)
            print_financial_data("CASH FLOW", parsed.cash_flow)

            if parsed.parsing_warnings:
                print(f"\n  WARNINGS: {parsed.parsing_warnings}")

        else:
            print(f"  FAIL: {result.error}")
    else:
        print("  No hay reportes XLSX disponibles.")

    # ============================================================
    # Paso 4: Probar también con PDF (si hay)
    # ============================================================
    if pdf_reports:
        print_header("PASO 4: Probando parser PDF (primer PDF disponible)")

        # Descargar primer PDF tipo earnings_release o financial_statement
        target_pdf = None
        for r in pdf_reports:
            if r.report_type.value in ("earnings_release", "financial_statement"):
                target_pdf = r
                break

        if target_pdf:
            print(f"  Descargando: {target_pdf.filename}...")
            result = await scraper.download_report(target_pdf)

            if result.success:
                print(f"  OK: {result.local_path} ({result.bytes_downloaded:,} bytes)")

                pdf_parser = PDFFinancialParser()
                parsed_pdf = pdf_parser.parse(result.local_path, ticker="SQM-B")

                print(f"  Completitud PDF: {parsed_pdf.completeness_score:.0%}")
                print(f"  Períodos: {parsed_pdf.periods_found}")

                if parsed_pdf.has_income_statement:
                    # Solo mostrar primeras 10 métricas para no saturar
                    first_period = list(parsed_pdf.income_statement.keys())[0] if parsed_pdf.income_statement else None
                    if first_period:
                        metrics = list(parsed_pdf.income_statement[first_period].keys())[:10]
                        print(f"  Primeras métricas IS: {metrics}")

                if parsed_pdf.parsing_warnings:
                    print(f"  WARNINGS: {parsed_pdf.parsing_warnings}")
            else:
                print(f"  FAIL: {result.error}")

    # ============================================================
    # Paso 5: Validación de calidad
    # ============================================================
    print_header("PASO 5: Validación de calidad")

    if xlsx_reports and 'parsed' in dir():
        checks_passed = 0
        checks_total = 0

        # Check 1: ¿Tiene income statement?
        checks_total += 1
        if parsed.has_income_statement:
            checks_passed += 1
            print("  [PASS] Income Statement extraído")
        else:
            print("  [FAIL] Income Statement NO extraído")

        # Check 2: ¿Tiene balance sheet?
        checks_total += 1
        if parsed.has_balance_sheet:
            checks_passed += 1
            print("  [PASS] Balance Sheet extraído")
        else:
            print("  [FAIL] Balance Sheet NO extraído")

        # Check 3: ¿Tiene cash flow?
        checks_total += 1
        if parsed.has_cash_flow:
            checks_passed += 1
            print("  [PASS] Cash Flow extraído")
        else:
            print("  [FAIL] Cash Flow NO extraído")

        # Check 4: ¿Tiene múltiples períodos?
        checks_total += 1
        if len(parsed.periods_found) >= 2:
            checks_passed += 1
            print(f"  [PASS] Múltiples períodos: {len(parsed.periods_found)}")
        else:
            print(f"  [FAIL] Solo {len(parsed.periods_found)} período(s)")

        # Check 5: ¿Revenue > 0 en algún período?
        checks_total += 1
        revenue_found = False
        if parsed.income_statement:
            for p, metrics in parsed.income_statement.items():
                for key, val in metrics.items():
                    if "revenue" in key.lower() and val and val > 0:
                        revenue_found = True
                        print(f"  [PASS] Revenue encontrado: {val:,.1f} ({parsed.unit}) en {p}")
                        break
                if revenue_found:
                    break
        if not revenue_found:
            print("  [FAIL] No se encontró Revenue > 0")
        else:
            checks_passed += 1

        print(f"\n  RESULTADO: {checks_passed}/{checks_total} checks pasados")
        print(f"  VEREDICTO: {'APROBADO' if checks_passed >= 4 else 'NECESITA AJUSTES'}")

    # ============================================================
    # Paso 6: Normalización a FinancialStatement
    # ============================================================
    if xlsx_reports and 'parsed' in dir():
        print_header("PASO 6: Normalización → FinancialStatement")

        try:
            statements = normalize_all_periods(parsed)
            print(f"  Períodos normalizados: {len(statements)}")

            for stmt in statements:
                print(f"\n  --- {stmt.period} ---")
                print(f"    Revenue:         {stmt.revenue:>12,.1f}")
                print(f"    Gross Profit:    {stmt.gross_profit:>12,.1f}")
                print(f"    Operating Inc:   {stmt.operating_income:>12,.1f}")
                print(f"    Net Income:      {stmt.net_income:>12,.1f}")
                print(f"    EBITDA:          {stmt.ebitda:>12,.1f}")
                print(f"    Total Assets:    {stmt.total_assets:>12,.1f}")
                print(f"    Total Equity:    {stmt.total_equity:>12,.1f}")
                print(f"    Total Debt:      {stmt.total_debt:>12,.1f}")
                print(f"    Op Cash Flow:    {stmt.operating_cash_flow:>12,.1f}")
                print(f"    Free Cash Flow:  {stmt.free_cash_flow:>12,.1f}")

                # Validar coherencia
                has_is = stmt.revenue != 0
                has_bs = stmt.total_assets != 0
                has_cf = stmt.operating_cash_flow != 0
                completeness = sum([has_is, has_bs, has_cf])
                status = "COMPLETO" if completeness == 3 else f"{completeness}/3 EEFF"
                print(f"    Status:          {status}")

            # Verificar que al menos un statement tenga los 3 EEFF
            full_statements = [
                s for s in statements
                if s.revenue != 0 and s.total_assets != 0 and s.operating_cash_flow != 0
            ]
            print(f"\n  Statements con 3/3 EEFF: {len(full_statements)}/{len(statements)}")
            if full_statements:
                print("  NORMALIZACIÓN: EXITOSA")
            else:
                print("  NORMALIZACIÓN: PARCIAL (algunos EEFF incompletos)")

        except Exception as e:
            print(f"  ERROR en normalización: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    await scraper.close()

    # ============================================================
    # Guardar resultados
    # ============================================================
    output_dir = Path("scripts/output")
    output_dir.mkdir(exist_ok=True)

    summary = {
        "test_date": datetime.now().isoformat(),
        "ticker": "SQM-B",
        "reports_discovered": len(reports) if 'reports' in dir() else 0,
        "xlsx_available": len(xlsx_reports) if 'xlsx_reports' in dir() else 0,
        "pdf_available": len(pdf_reports) if 'pdf_reports' in dir() else 0,
    }

    with open(output_dir / "ir_scraper_test_results.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  Resumen guardado en: scripts/output/ir_scraper_test_results.json")


async def main():
    await test_sqm_scraper()


if __name__ == "__main__":
    asyncio.run(main())
