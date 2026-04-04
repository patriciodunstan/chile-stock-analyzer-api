"""Test local del parser XLSX + normalizer con archivo ya descargado.

Ejecutar:
    python scripts/test_parser_local.py

Usa el XLSX descargado previamente para validar:
1. XLSX parsing → income_statement, balance_sheet, cash_flow, ebitda_data
2. Normalización → FinancialStatement con campos derivados
3. Calidad de datos → métricas clave presentes y coherentes
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.infrastructure.parsers.xlsx_financial_parser import XLSXFinancialParser
from app.infrastructure.parsers.normalizer import normalize_all_periods


def print_header(text: str):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def main():
    xlsx_path = Path("data/reports/sqm-b/2025/SQM-B_Q4_2025_earnings_tables.xlsx")
    if not xlsx_path.exists():
        print(f"ERROR: No se encontró {xlsx_path}")
        print("Ejecuta primero: python scripts/test_ir_scraper.py (con internet)")
        sys.exit(1)

    print_header("PARSING XLSX LOCAL")
    print(f"  Archivo: {xlsx_path}")
    print(f"  Tamaño: {xlsx_path.stat().st_size:,} bytes")

    # === Paso 1: Parse XLSX ===
    parser = XLSXFinancialParser()
    parsed = parser.parse(xlsx_path, ticker="SQM-B")

    print(f"\n  Moneda: {parsed.currency}")
    print(f"  Unidad: {parsed.unit}")
    print(f"  Períodos encontrados: {parsed.periods_found}")
    print(f"  Completitud: {parsed.completeness_score:.0%}")

    # Mostrar resumen por estado financiero
    for name, data in [
        ("Income Statement", parsed.income_statement),
        ("Balance Sheet", parsed.balance_sheet),
        ("Cash Flow", parsed.cash_flow),
        ("EBITDA Data", parsed.ebitda_data),
    ]:
        if data:
            periods = list(data.keys())
            metrics_count = max(len(v) for v in data.values()) if data else 0
            print(f"\n  {name}:")
            print(f"    Períodos: {periods}")
            print(f"    Métricas: {metrics_count}")
            # Mostrar primeras 8 métricas del primer período
            first_period = periods[0]
            for i, (k, v) in enumerate(data[first_period].items()):
                if i >= 8:
                    print(f"    ... y {len(data[first_period]) - 8} más")
                    break
                print(f"    {k:45s} = {v}")
        else:
            print(f"\n  {name}: (sin datos)")

    if parsed.parsing_warnings:
        print(f"\n  WARNINGS: {parsed.parsing_warnings}")

    # === Paso 2: Normalización ===
    print_header("NORMALIZACIÓN → FinancialStatement")

    statements = normalize_all_periods(parsed)
    print(f"  Períodos normalizados: {len(statements)}")

    for stmt in statements:
        print(f"\n  --- {stmt.period} ---")
        print(f"    Revenue:          {stmt.revenue:>12,.1f}")
        print(f"    Cost of Revenue:  {stmt.cost_of_revenue:>12,.1f}")
        print(f"    Gross Profit:     {stmt.gross_profit:>12,.1f}")
        print(f"    Operating Inc:    {stmt.operating_income:>12,.1f}")
        print(f"    EBITDA:           {stmt.ebitda:>12,.1f}")
        print(f"    EBIT:             {stmt.ebit:>12,.1f}")
        print(f"    Net Income:       {stmt.net_income:>12,.1f}")
        print(f"    Interest Exp:     {stmt.interest_expense:>12,.1f}")
        print(f"    Total Assets:     {stmt.total_assets:>12,.1f}")
        print(f"    Total Liabilities:{stmt.total_liabilities:>12,.1f}")
        print(f"    Total Equity:     {stmt.total_equity:>12,.1f}")
        print(f"    Total Debt:       {stmt.total_debt:>12,.1f}")
        print(f"    Cash:             {stmt.cash_and_equivalents:>12,.1f}")
        print(f"    Current Assets:   {stmt.current_assets:>12,.1f}")
        print(f"    Current Liab:     {stmt.current_liabilities:>12,.1f}")
        print(f"    Op Cash Flow:     {stmt.operating_cash_flow:>12,.1f}")
        print(f"    CapEx:            {stmt.capital_expenditure:>12,.1f}")
        print(f"    Free Cash Flow:   {stmt.free_cash_flow:>12,.1f}")
        print(f"    Dividends Paid:   {stmt.dividends_paid:>12,.1f}")

        # Coherencia
        has_is = stmt.revenue != 0
        has_bs = stmt.total_assets != 0
        has_cf = stmt.operating_cash_flow != 0
        completeness = sum([has_is, has_bs, has_cf])
        status = "COMPLETO (3/3 EEFF)" if completeness == 3 else f"PARCIAL ({completeness}/3 EEFF)"
        print(f"    Status:           {status}")

    # === Paso 3: Validación de calidad ===
    print_header("VALIDACIÓN DE CALIDAD")

    checks_passed = 0
    checks_total = 0

    def check(name: str, condition: bool):
        nonlocal checks_passed, checks_total
        checks_total += 1
        if condition:
            checks_passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")

    check("Income Statement extraído", parsed.has_income_statement)
    check("Balance Sheet extraído", parsed.has_balance_sheet)
    check("Cash Flow extraído", parsed.has_cash_flow)
    check("Múltiples períodos (>=2)", len(parsed.periods_found) >= 2)

    # Revenue > 0
    has_revenue = any(
        stmt.revenue > 0 for stmt in statements
    )
    check("Revenue > 0 en algún período", has_revenue)

    # EBITDA disponible
    has_ebitda = any(stmt.ebitda != 0 for stmt in statements)
    check("EBITDA disponible", has_ebitda)

    # Total Assets > 0
    has_assets = any(stmt.total_assets > 0 for stmt in statements)
    check("Total Assets > 0", has_assets)

    # Net Income no es cero en todos
    has_net_income = any(stmt.net_income != 0 for stmt in statements)
    check("Net Income disponible", has_net_income)

    # Operating Cash Flow disponible
    has_ocf = any(stmt.operating_cash_flow != 0 for stmt in statements)
    check("Operating Cash Flow disponible", has_ocf)

    # Al menos un statement completo (3/3 EEFF)
    full_stmts = [
        s for s in statements
        if s.revenue != 0 and s.total_assets != 0 and s.operating_cash_flow != 0
    ]
    check(f"Al menos 1 statement completo (3/3 EEFF): {len(full_stmts)}", len(full_stmts) >= 1)

    print(f"\n  RESULTADO: {checks_passed}/{checks_total} checks pasados")
    print(f"  VEREDICTO: {'APROBADO' if checks_passed >= 8 else 'NECESITA AJUSTES'}")


if __name__ == "__main__":
    main()
