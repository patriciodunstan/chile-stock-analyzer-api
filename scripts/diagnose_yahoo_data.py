"""Script de diagnóstico: qué datos entrega Yahoo Finance para cada ticker chileno.

Ejecutar: python scripts/diagnose_yahoo_data.py

Analiza cada ticker del IPSA y muestra exactamente qué campos tienen datos
y cuáles vienen como None. Esto es CRITICO para saber qué métricas podemos
calcular realmente.
"""

import sys
import json
from datetime import datetime

try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance no está instalado.")
    print("Ejecuta: pip install yfinance")
    sys.exit(1)

# Tickers chilenos con sufijo .SN para Yahoo Finance
TICKERS = {
    "SQM-B": "SQM-B.SN",
    "CAP": "CAP.SN",
    "BCI": "BCI.SN",
    "BSANTANDER": "BSANTANDER.SN",
    "FALABELLA": "FALABELLA.SN",
    "COPEC": "COPEC.SN",
    "CENCOSUD": "CENCOSUD.SN",
    "ENELAM": "ENELAM.SN",
    "CMPC": "CMPC.SN",
    "CCU": "CCU.SN",
    "CHILE": "CHILE.SN",
    "ITAUCORP": "ITAUCORP.SN",
    "VAPORES": "VAPORES.SN",
    "COLBUN": "COLBUN.SN",
    "PROVIDA": "PROVIDA.SN",
}

# Campos fundamentales que necesitamos para análisis
FUNDAMENTAL_FIELDS = {
    # Valorización
    "currentPrice": "Precio actual",
    "marketCap": "Market Cap",
    "enterpriseValue": "Enterprise Value",
    "trailingPE": "P/E trailing",
    "forwardPE": "P/E forward",
    "priceToBook": "P/B ratio",
    "priceToSalesTrailing12Months": "P/S ratio",
    "enterpriseToEbitda": "EV/EBITDA",
    "enterpriseToRevenue": "EV/Revenue",
    "pegRatio": "PEG ratio",
    # Rentabilidad
    "returnOnEquity": "ROE",
    "returnOnAssets": "ROA",
    "profitMargins": "Margen neto",
    "operatingMargins": "Margen operacional",
    "grossMargins": "Margen bruto",
    # Estado de resultados
    "totalRevenue": "Revenue",
    "netIncomeToCommon": "Utilidad neta",
    "ebitda": "EBITDA",
    "trailingEps": "EPS trailing",
    "earningsGrowth": "Earnings growth",
    "revenueGrowth": "Revenue growth",
    # Balance
    "totalDebt": "Deuda total",
    "totalCash": "Cash total",
    "debtToEquity": "Debt/Equity",
    "currentRatio": "Current Ratio",
    "bookValue": "Book Value",
    # Flujo de caja
    "freeCashflow": "Free Cash Flow",
    "operatingCashflow": "Operating Cash Flow",
    # Dividendos
    "dividendYield": "Dividend Yield",
    "payoutRatio": "Payout Ratio",
    # Acciones y riesgo
    "sharesOutstanding": "Shares Outstanding",
    "beta": "Beta",
}


def diagnose_ticker(nemo: str, yahoo_ticker: str) -> dict:
    """Analiza qué datos tiene Yahoo para un ticker."""
    result = {"nemo": nemo, "yahoo_ticker": yahoo_ticker, "fields": {}, "error": None}

    try:
        stock = yf.Ticker(yahoo_ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
            result["error"] = "No data returned from Yahoo"
            return result

        for field, label in FUNDAMENTAL_FIELDS.items():
            value = info.get(field)
            result["fields"][field] = {
                "label": label,
                "value": value,
                "has_data": value is not None,
            }

    except Exception as e:
        result["error"] = str(e)

    return result


def format_value(value) -> str:
    """Formatea un valor para display."""
    if value is None:
        return "     ✗ None"
    if isinstance(value, float):
        if abs(value) >= 1_000_000_000:
            return f"  {value/1e9:>8.2f}B"
        if abs(value) >= 1_000_000:
            return f"  {value/1e6:>8.2f}M"
        if abs(value) < 1:
            return f"  {value*100:>8.2f}%"
        return f"  {value:>10.2f}"
    if isinstance(value, int):
        return f"  {value:>10,}"
    return f"  {str(value):>10s}"


def main():
    print("=" * 90)
    print(f"  DIAGNÓSTICO YAHOO FINANCE — ACCIONES CHILENAS (.SN)")
    print(f"  Ejecutado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 90)
    print()

    all_results = []
    coverage_matrix = {}  # field -> {ticker: has_data}

    for nemo, yahoo_ticker in TICKERS.items():
        print(f"--- {nemo} ({yahoo_ticker}) ---")
        result = diagnose_ticker(nemo, yahoo_ticker)
        all_results.append(result)

        if result["error"]:
            print(f"  ERROR: {result['error']}")
            print()
            continue

        has_count = sum(1 for f in result["fields"].values() if f["has_data"])
        total = len(result["fields"])
        print(f"  Cobertura: {has_count}/{total} campos ({has_count/total*100:.0f}%)")
        print()

        for field, data in result["fields"].items():
            status = "✓" if data["has_data"] else "✗"
            val = format_value(data["value"])
            print(f"    {status} {data['label']:<25s} {val}")

            # Track coverage
            if field not in coverage_matrix:
                coverage_matrix[field] = {}
            coverage_matrix[field][nemo] = data["has_data"]

        print()

    # --- RESUMEN DE COBERTURA ---
    print("=" * 90)
    print("  MATRIZ DE COBERTURA POR CAMPO")
    print("=" * 90)
    print()

    # Header
    tickers_list = list(TICKERS.keys())
    header = f"{'Campo':<25s} "
    for t in tickers_list:
        header += f"{t[:6]:>7s} "
    header += "  TOTAL"
    print(header)
    print("-" * len(header))

    for field, label in FUNDAMENTAL_FIELDS.items():
        if field not in coverage_matrix:
            continue
        row = f"{label:<25s} "
        count = 0
        for t in tickers_list:
            has = coverage_matrix[field].get(t, False)
            row += f"{'  ✓':>7s} " if has else f"{'  ✗':>7s} "
            if has:
                count += 1
        row += f"  {count}/{len(tickers_list)}"
        print(row)

    # --- RESUMEN FINAL ---
    print()
    print("=" * 90)
    print("  VEREDICTO POR TICKER")
    print("=" * 90)
    print()

    for result in all_results:
        nemo = result["nemo"]
        if result["error"]:
            print(f"  {nemo:<15s} ✗ ERROR — No se puede usar para análisis fundamental")
            continue

        has = sum(1 for f in result["fields"].values() if f["has_data"])
        total = len(result["fields"])
        pct = has / total * 100

        # Verificar campos críticos para DCF
        critical = ["freeCashflow", "beta", "totalDebt", "totalCash", "sharesOutstanding"]
        critical_ok = all(result["fields"].get(f, {}).get("has_data", False) for f in critical)

        if pct >= 80 and critical_ok:
            verdict = "✓ COMPLETO — Análisis fundamental + DCF posible"
        elif pct >= 50:
            verdict = "△ PARCIAL — Métricas básicas sí, DCF tal vez no"
        else:
            verdict = "✗ INSUFICIENTE — No alcanza para análisis fundamental"

        print(f"  {nemo:<15s} {pct:>3.0f}% cobertura — {verdict}")

    # Guardar JSON con resultados completos
    output_file = "scripts/yahoo_diagnosis_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResultados guardados en: {output_file}")


if __name__ == "__main__":
    main()
