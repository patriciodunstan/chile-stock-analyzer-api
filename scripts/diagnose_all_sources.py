"""
Script de diagnóstico COMPLETO: valida TODAS las fuentes de datos disponibles
para análisis fundamental de acciones chilenas.

Ejecutar en tu máquina local:
    cd chile-stock-analyzer
    pip install yfinance httpx
    python scripts/diagnose_all_sources.py

Fuentes que prueba:
  1. Yahoo Finance (.SN tickers) - fundamentals + precios
  2. CMF API v3 (bancos) - estados financieros bancarios
  3. EODHD (demo) - precios EOD
  4. Banco Central API SIETE - indicadores macro

Genera: scripts/output/data_coverage_report.json
"""

import sys
import json
import time
from datetime import datetime, date
from pathlib import Path

# ============================================================
# Configuración
# ============================================================

TICKERS = {
    "SQM-B": {"yahoo": "SQM-B.SN", "sector": "Minería", "nombre": "SQM"},
    "CAP": {"yahoo": "CAP.SN", "sector": "Minería/Acero", "nombre": "CAP S.A."},
    "BCI": {"yahoo": "BCI.SN", "sector": "Banca", "nombre": "Banco BCI"},
    "BSANTANDER": {"yahoo": "BSANTANDER.SN", "sector": "Banca", "nombre": "Banco Santander Chile"},
    "FALABELLA": {"yahoo": "FALABELLA.SN", "sector": "Retail", "nombre": "Falabella"},
    "COPEC": {"yahoo": "COPEC.SN", "sector": "Energía/Forestal", "nombre": "Empresas Copec"},
    "CENCOSUD": {"yahoo": "CENCOSUD.SN", "sector": "Retail", "nombre": "Cencosud"},
    "ENELAM": {"yahoo": "ENELAM.SN", "sector": "Energía", "nombre": "Enel Américas"},
    "CMPC": {"yahoo": "CMPC.SN", "sector": "Forestal", "nombre": "CMPC"},
    "CCU": {"yahoo": "CCU.SN", "sector": "Consumo", "nombre": "CCU"},
    "CHILE": {"yahoo": "CHILE.SN", "sector": "Banca", "nombre": "Banco de Chile"},
    "ITAUCORP": {"yahoo": "ITAUCORP.SN", "sector": "Banca", "nombre": "Itaú Corpbanca"},
    "VAPORES": {"yahoo": "VAPORES.SN", "sector": "Naviera", "nombre": "CSAV"},
    "COLBUN": {"yahoo": "COLBUN.SN", "sector": "Energía", "nombre": "Colbún"},
    "PROVIDA": {"yahoo": "PROVIDA.SN", "sector": "AFP", "nombre": "AFP Provida"},
}

FUNDAMENTAL_FIELDS = {
    # === Valorización (para calcular valor intrínseco) ===
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
    # === Rentabilidad ===
    "returnOnEquity": "ROE",
    "returnOnAssets": "ROA",
    "profitMargins": "Margen neto",
    "operatingMargins": "Margen operacional",
    "grossMargins": "Margen bruto",
    # === Estado de resultados ===
    "totalRevenue": "Revenue",
    "netIncomeToCommon": "Utilidad neta",
    "ebitda": "EBITDA",
    "trailingEps": "EPS trailing",
    "earningsGrowth": "Earnings growth",
    "revenueGrowth": "Revenue growth",
    # === Balance ===
    "totalDebt": "Deuda total",
    "totalCash": "Cash total",
    "debtToEquity": "Debt/Equity",
    "currentRatio": "Current Ratio",
    "bookValue": "Book Value",
    # === Flujo de caja ===
    "freeCashflow": "Free Cash Flow",
    "operatingCashflow": "Operating Cash Flow",
    # === Dividendos ===
    "dividendYield": "Dividend Yield",
    "payoutRatio": "Payout Ratio",
    # === Riesgo ===
    "sharesOutstanding": "Shares Outstanding",
    "beta": "Beta",
    # === EEFF históricos (DataFrames) ===
    "income_stmt": "Income Statement (anual)",
    "quarterly_income_stmt": "Income Statement (trimestral)",
    "balance_sheet": "Balance Sheet (anual)",
    "quarterly_balance_sheet": "Balance Sheet (trimestral)",
    "cashflow": "Cash Flow (anual)",
    "quarterly_cashflow": "Cash Flow (trimestral)",
}

DCF_REQUIRED = [
    "freeCashflow", "operatingCashflow", "totalRevenue", "netIncomeToCommon",
    "totalDebt", "totalCash", "sharesOutstanding", "beta",
    "revenueGrowth", "earningsGrowth", "ebitda",
]

VALUATION_REQUIRED = [
    "trailingPE", "priceToBook", "enterpriseToEbitda", "returnOnEquity",
    "profitMargins", "debtToEquity", "currentPrice", "bookValue",
    "dividendYield",
]


def print_header(text: str):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def print_subheader(text: str):
    print(f"\n--- {text} ---")


# ============================================================
# 1. Yahoo Finance
# ============================================================
def test_yahoo_finance() -> dict:
    print_header("1. YAHOO FINANCE - Datos Fundamentales (.SN)")

    try:
        import yfinance as yf
    except ImportError:
        print("  [ERROR] yfinance no instalado. Ejecuta: pip install yfinance")
        return {"status": "not_installed", "tickers": {}}

    results = {}

    for nemo, config in TICKERS.items():
        yahoo_ticker = config["yahoo"]
        print(f"\n  Probando {nemo} ({yahoo_ticker})...", end=" ", flush=True)

        try:
            ticker = yf.Ticker(yahoo_ticker)
            info = ticker.info

            if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
                print("SIN DATOS")
                results[nemo] = {
                    "status": "no_data",
                    "fields_available": 0,
                    "fields_total": len(FUNDAMENTAL_FIELDS),
                    "available": {},
                    "missing": list(FUNDAMENTAL_FIELDS.keys()),
                }
                continue

            available = {}
            missing = []

            # Campos info
            for field, label in FUNDAMENTAL_FIELDS.items():
                if field.endswith("_stmt") or field.endswith("_sheet") or field == "cashflow" or field.startswith("quarterly_"):
                    continue  # DataFrames se verifican aparte
                val = info.get(field)
                if val is not None:
                    available[field] = {"label": label, "value": val}
                else:
                    missing.append(field)

            # DataFrames de EEFF
            dataframe_fields = {
                "income_stmt": "income_stmt",
                "quarterly_income_stmt": "quarterly_income_stmt",
                "balance_sheet": "balance_sheet",
                "quarterly_balance_sheet": "quarterly_balance_sheet",
                "cashflow": "cashflow",
                "quarterly_cashflow": "quarterly_cashflow",
            }

            for field, attr in dataframe_fields.items():
                try:
                    df = getattr(ticker, attr, None)
                    if df is not None and not df.empty:
                        rows = len(df)
                        cols = len(df.columns)
                        periods = list(df.columns.strftime("%Y-%m-%d")) if hasattr(df.columns, 'strftime') else [str(c) for c in df.columns]
                        available[field] = {
                            "label": FUNDAMENTAL_FIELDS[field],
                            "value": f"{rows} filas x {cols} periodos",
                            "periods": periods[:4],  # últimos 4 periodos
                        }
                    else:
                        missing.append(field)
                except Exception:
                    missing.append(field)

            total_fields = len(FUNDAMENTAL_FIELDS)
            avail_count = len(available)
            pct = (avail_count / total_fields) * 100

            # Verificar campos críticos para DCF
            dcf_available = sum(1 for f in DCF_REQUIRED if f in available)
            dcf_total = len(DCF_REQUIRED)

            # Verificar campos para valorización básica
            val_available = sum(1 for f in VALUATION_REQUIRED if f in available)
            val_total = len(VALUATION_REQUIRED)

            verdict = "COMPLETO" if pct >= 70 else "PARCIAL" if pct >= 40 else "INSUFICIENTE"
            dcf_verdict = "VIABLE" if dcf_available >= 8 else "PARCIAL" if dcf_available >= 5 else "NO VIABLE"

            print(f"{verdict} ({avail_count}/{total_fields} = {pct:.0f}%) | DCF: {dcf_verdict} ({dcf_available}/{dcf_total})")

            results[nemo] = {
                "status": verdict.lower(),
                "sector": config["sector"],
                "fields_available": avail_count,
                "fields_total": total_fields,
                "coverage_pct": round(pct, 1),
                "dcf_fields": f"{dcf_available}/{dcf_total}",
                "dcf_verdict": dcf_verdict.lower(),
                "valuation_fields": f"{val_available}/{val_total}",
                "available": {k: v for k, v in available.items()},
                "missing": missing,
            }

            time.sleep(0.5)  # rate limiting

        except Exception as e:
            print(f"ERROR: {e}")
            results[nemo] = {"status": "error", "error": str(e)}

    return {"status": "tested", "tickers": results}


# ============================================================
# 2. CMF API v3 (Bancos)
# ============================================================
def test_cmf_api() -> dict:
    print_header("2. CMF API v3 - Estados Financieros Bancarios")

    try:
        import httpx
    except ImportError:
        print("  [ERROR] httpx no instalado. Ejecuta: pip install httpx")
        return {"status": "not_installed"}

    # Endpoints públicos de CMF API
    base_url = "https://api.cmfchile.cl/api-sbifv3/recursos_702"

    endpoints_to_test = {
        "instituciones": f"{base_url}/bancos/instituciones?apikey=demo&formato=json",
        "balance": f"{base_url}/balances/bci/periodos/2024/12?apikey=demo&formato=json",
    }

    results = {}
    for name, url in endpoints_to_test.items():
        print(f"  Probando {name}...", end=" ", flush=True)
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json() if "json" in resp.headers.get("content-type", "") else resp.text[:500]
                    print(f"OK (status={resp.status_code})")
                    results[name] = {"status": "ok", "status_code": resp.status_code, "sample": str(data)[:200]}
                else:
                    print(f"ERROR (status={resp.status_code})")
                    results[name] = {"status": "error", "status_code": resp.status_code}
        except Exception as e:
            print(f"ERROR: {e}")
            results[name] = {"status": "error", "error": str(e)}

    print("\n  NOTA: CMF API v3 tiene datos estructurados SOLO para bancos.")
    print("  Para emisores no-bancarios, usar CMF XBRL o scraping de EEFF.")

    return {"status": "tested", "endpoints": results}


# ============================================================
# 3. EODHD
# ============================================================
def test_eodhd() -> dict:
    print_header("3. EODHD - Datos EOD + Fundamentals")

    try:
        import httpx
    except ImportError:
        return {"status": "not_installed"}

    base_url = "https://eodhd.com/api"
    api_key = "demo"  # demo key: 20 requests/day

    test_ticker = "SQM-B.SN"

    endpoints = {
        "eod_price": f"{base_url}/eod/{test_ticker}?api_token={api_key}&fmt=json&from=2025-01-01&to=2025-01-31",
        "fundamentals": f"{base_url}/fundamentals/{test_ticker}?api_token={api_key}&fmt=json",
    }

    results = {}
    for name, url in endpoints.items():
        print(f"  Probando {name} (SQM-B)...", end=" ", flush=True)
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        print(f"OK ({len(data)} registros)")
                        results[name] = {"status": "ok", "record_count": len(data)}
                    elif isinstance(data, dict):
                        keys = list(data.keys())[:10]
                        print(f"OK (keys: {keys})")
                        results[name] = {"status": "ok", "top_keys": keys}
                    else:
                        print(f"OK")
                        results[name] = {"status": "ok"}
                else:
                    print(f"ERROR (status={resp.status_code})")
                    results[name] = {"status": "error", "status_code": resp.status_code}
        except Exception as e:
            print(f"ERROR: {e}")
            results[name] = {"status": "error", "error": str(e)}

    print("\n  NOTA: EODHD demo = 20 req/día. Fundamentals puede requerir plan pago.")

    return {"status": "tested", "endpoints": results}


# ============================================================
# 4. Banco Central API SIETE
# ============================================================
def test_banco_central() -> dict:
    print_header("4. BANCO CENTRAL - API SIETE (Indicadores Macro)")

    try:
        import httpx
    except ImportError:
        return {"status": "not_installed"}

    base_url = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"

    series = {
        "USD/CLP": "F073.TCO.PRE.Z.D",
        "UF": "F073.UFF.PRE.Z.D",
        "TPM": "F022.TPM.TIN.D001.NO.Z.D",
    }

    results = {}
    today = date.today().isoformat()

    for name, serie_id in series.items():
        print(f"  Probando {name} ({serie_id})...", end=" ", flush=True)
        params = {
            "user": "anonymous",
            "pass": "",
            "firstdate": "2025-01-01",
            "lastdate": today,
            "timeseries": serie_id,
            "function": "GetSeries",
        }
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(base_url, params=params)
                if resp.status_code == 200:
                    text = resp.text[:300]
                    has_data = "Valor" in text or "value" in text.lower()
                    print(f"OK ({'con datos' if has_data else 'sin datos'})")
                    results[name] = {"status": "ok", "has_data": has_data}
                else:
                    print(f"ERROR (status={resp.status_code})")
                    results[name] = {"status": "error", "status_code": resp.status_code}
        except Exception as e:
            print(f"ERROR: {e}")
            results[name] = {"status": "error", "error": str(e)}

    return {"status": "tested", "series": results}


# ============================================================
# 5. Resumen y reporte
# ============================================================
def generate_report(yahoo_results: dict, cmf_results: dict, eodhd_results: dict, bcch_results: dict):
    print_header("RESUMEN DE COBERTURA DE DATOS")

    report = {
        "generated_at": datetime.now().isoformat(),
        "sources": {
            "yahoo_finance": yahoo_results,
            "cmf_api": cmf_results,
            "eodhd": eodhd_results,
            "banco_central": bcch_results,
        },
        "conclusions": {},
    }

    # Análisis Yahoo
    if yahoo_results.get("tickers"):
        tickers = yahoo_results["tickers"]
        complete = sum(1 for t in tickers.values() if t.get("status") == "completo")
        partial = sum(1 for t in tickers.values() if t.get("status") == "parcial")
        insufficient = sum(1 for t in tickers.values() if t.get("status") == "insuficiente")
        dcf_viable = sum(1 for t in tickers.values() if t.get("dcf_verdict") == "viable")

        print(f"\n  YAHOO FINANCE:")
        print(f"    Tickers testeados: {len(tickers)}")
        print(f"    Cobertura completa (>70%): {complete}")
        print(f"    Cobertura parcial (40-70%): {partial}")
        print(f"    Cobertura insuficiente (<40%): {insufficient}")
        print(f"    DCF viable: {dcf_viable}/{len(tickers)}")

        print(f"\n  Detalle por ticker:")
        print(f"  {'Ticker':<15} {'Sector':<20} {'Cobertura':<12} {'DCF':<12} {'Valoración':<12}")
        print(f"  {'-'*70}")
        for nemo, data in sorted(tickers.items(), key=lambda x: x[1].get("coverage_pct", 0), reverse=True):
            if data.get("status") in ("error", "no_data"):
                print(f"  {nemo:<15} {data.get('sector','?'):<20} {'ERROR':<12}")
                continue
            print(f"  {nemo:<15} {data.get('sector','?'):<20} {data.get('coverage_pct',0):>5.1f}%      {data.get('dcf_verdict','?'):<12} {data.get('valuation_fields','?'):<12}")

        report["conclusions"]["yahoo"] = {
            "complete_tickers": complete,
            "dcf_viable_tickers": dcf_viable,
            "recommendation": "Yahoo Finance es la principal fuente gratuita para fundamentals. Complementar con CMF XBRL para EEFF detallados."
        }

    # Recomendaciones finales
    print_header("RECOMENDACIONES")
    print("""
  1. PRECIOS: Bolsa de Santiago API (mock) > Yahoo Finance > EODHD
     → Ya implementado con CompositeProvider cascade

  2. FUNDAMENTALS (métricas): Yahoo Finance (.SN)
     → Única fuente gratuita con P/E, ROE, FCF, EV/EBITDA
     → Cobertura variable por ticker — revisar resultados arriba

  3. EEFF DETALLADOS (income statement, balance, cash flow):
     → Yahoo Finance DataFrames (anual + trimestral)
     → CMF XBRL (formato estructurado, todas las empresas)
     → Páginas de Relación con Inversionistas (PDFs)

  4. INDICADORES MACRO: Banco Central API SIETE
     → USD/CLP, UF, TPM, Tasa libre de riesgo
     → Ya implementado en BancoCentralClient

  5. BANCOS ESPECÍFICAMENTE: CMF API v3
     → Datos estructurados para BCI, Santander, Chile, Itaú

  ESTRATEGIA RECOMENDADA:
  ┌─────────────────────────────────────────────────┐
  │  Yahoo Finance → fundamentals + EEFF históricos │
  │  CMF XBRL      → EEFF oficiales verificación    │
  │  CMF API v3    → bancos específicamente          │
  │  Banco Central → macro (tasas, tipo cambio)      │
  │  Company IR    → memorias anuales (complemento)  │
  └─────────────────────────────────────────────────┘
    """)

    # Guardar reporte JSON
    output_dir = Path("scripts/output")
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "data_coverage_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n  Reporte guardado en: {report_path}")
    return report


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 70)
    print("  DIAGNÓSTICO DE FUENTES DE DATOS - Chile Stock Analyzer")
    print(f"  Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    yahoo_results = test_yahoo_finance()
    cmf_results = test_cmf_api()
    eodhd_results = test_eodhd()
    bcch_results = test_banco_central()

    report = generate_report(yahoo_results, cmf_results, eodhd_results, bcch_results)

    print("\n" + "=" * 70)
    print("  DIAGNÓSTICO COMPLETADO")
    print("=" * 70)


if __name__ == "__main__":
    main()
