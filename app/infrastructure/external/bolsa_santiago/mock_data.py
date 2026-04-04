"""Datos mock realistas del mercado chileno para desarrollo y testing.

Precios basados en datos reales de marzo 2025 del IPSA.
Se usan cuando la API de la Bolsa de Santiago no está disponible.
"""

from datetime import datetime, timedelta
import random

# Datos reales aproximados del IPSA - marzo 2025
IPSA_CONSTITUENTS = [
    {"nemo": "SQM-B", "companyName": "Sociedad Química y Minera de Chile", "sector": "Minería"},
    {"nemo": "CAP", "companyName": "CAP S.A.", "sector": "Minería"},
    {"nemo": "BCI", "companyName": "Banco de Crédito e Inversiones", "sector": "Banca"},
    {"nemo": "BSANTANDER", "companyName": "Banco Santander Chile", "sector": "Banca"},
    {"nemo": "FALABELLA", "companyName": "Falabella S.A.", "sector": "Retail"},
    {"nemo": "COPEC", "companyName": "Empresas Copec S.A.", "sector": "Energía"},
    {"nemo": "CENCOSUD", "companyName": "Cencosud S.A.", "sector": "Retail"},
    {"nemo": "ENELAM", "companyName": "Enel Américas S.A.", "sector": "Energía"},
    {"nemo": "ENELCHILE", "companyName": "Enel Chile S.A.", "sector": "Energía"},
    {"nemo": "CMPC", "companyName": "Empresas CMPC S.A.", "sector": "Forestal"},
    {"nemo": "CCU", "companyName": "Compañía Cervecerías Unidas S.A.", "sector": "Consumo"},
    {"nemo": "CHILE", "companyName": "Banco de Chile", "sector": "Banca"},
    {"nemo": "ITAUCORP", "companyName": "Itaú Corpbanca", "sector": "Banca"},
    {"nemo": "VAPORES", "companyName": "Compañía Sud Americana de Vapores", "sector": "Transporte"},
    {"nemo": "COLBUN", "companyName": "Colbún S.A.", "sector": "Energía"},
    {"nemo": "PROVIDA", "companyName": "AFP Provida S.A.", "sector": "AFP"},
    {"nemo": "PARAUCO", "companyName": "Parque Arauco S.A.", "sector": "Inmobiliario"},
    {"nemo": "AGUAS-A", "companyName": "Aguas Andinas S.A.", "sector": "Servicios Básicos"},
    {"nemo": "ECL", "companyName": "Engie Energía Chile S.A.", "sector": "Energía"},
    {"nemo": "SECURITY", "companyName": "Grupo Security S.A.", "sector": "Financiero"},
    {"nemo": "RIPLEY", "companyName": "Ripley Corp S.A.", "sector": "Retail"},
]

# Precios base realistas en CLP (marzo 2025 aproximado)
STOCK_PRICES: dict[str, dict] = {
    "SQM-B": {"lastPrice": 42850, "openPrice": 42500, "highPrice": 43200, "lowPrice": 42100, "closePrice": 42650, "volume": 1250000, "marketCap": 11_520_000_000_000, "changePercent": 0.47},
    "CAP": {"lastPrice": 7890, "openPrice": 7800, "highPrice": 7950, "lowPrice": 7750, "closePrice": 7830, "volume": 450000, "marketCap": 1_180_000_000_000, "changePercent": 0.77},
    "BCI": {"lastPrice": 28950, "openPrice": 28700, "highPrice": 29100, "lowPrice": 28500, "closePrice": 28800, "volume": 320000, "marketCap": 3_050_000_000_000, "changePercent": 0.52},
    "BSANTANDER": {"lastPrice": 42.5, "openPrice": 42.0, "highPrice": 43.0, "lowPrice": 41.8, "closePrice": 42.2, "volume": 8500000, "marketCap": 7_990_000_000_000, "changePercent": 0.71},
    "FALABELLA": {"lastPrice": 2785, "openPrice": 2760, "highPrice": 2810, "lowPrice": 2740, "closePrice": 2770, "volume": 3200000, "marketCap": 7_020_000_000_000, "changePercent": 0.54},
    "COPEC": {"lastPrice": 6950, "openPrice": 6900, "highPrice": 7020, "lowPrice": 6850, "closePrice": 6920, "volume": 280000, "marketCap": 9_050_000_000_000, "changePercent": 0.43},
    "CENCOSUD": {"lastPrice": 1920, "openPrice": 1900, "highPrice": 1940, "lowPrice": 1890, "closePrice": 1910, "volume": 4100000, "marketCap": 5_480_000_000_000, "changePercent": 0.52},
    "ENELAM": {"lastPrice": 118.5, "openPrice": 117.0, "highPrice": 119.0, "lowPrice": 116.5, "closePrice": 117.8, "volume": 15000000, "marketCap": 4_370_000_000_000, "changePercent": 0.59},
    "ENELCHILE": {"lastPrice": 62.5, "openPrice": 61.8, "highPrice": 63.0, "lowPrice": 61.5, "closePrice": 62.0, "volume": 18000000, "marketCap": 3_050_000_000_000, "changePercent": 0.48},
    "CMPC": {"lastPrice": 1650, "openPrice": 1630, "highPrice": 1670, "lowPrice": 1620, "closePrice": 1640, "volume": 1800000, "marketCap": 4_120_000_000_000, "changePercent": 0.61},
    "CCU": {"lastPrice": 6100, "openPrice": 6050, "highPrice": 6150, "lowPrice": 6000, "closePrice": 6070, "volume": 180000, "marketCap": 2_250_000_000_000, "changePercent": 0.49},
    "CHILE": {"lastPrice": 95.2, "openPrice": 94.5, "highPrice": 95.8, "lowPrice": 94.0, "closePrice": 94.8, "volume": 12000000, "marketCap": 9_620_000_000_000, "changePercent": 0.42},
    "ITAUCORP": {"lastPrice": 3.15, "openPrice": 3.10, "highPrice": 3.18, "lowPrice": 3.08, "closePrice": 3.12, "volume": 45000000, "marketCap": 1_680_000_000_000, "changePercent": 0.96},
    "VAPORES": {"lastPrice": 52.5, "openPrice": 52.0, "highPrice": 53.0, "lowPrice": 51.5, "closePrice": 52.2, "volume": 9000000, "marketCap": 2_680_000_000_000, "changePercent": 0.57},
    "COLBUN": {"lastPrice": 142, "openPrice": 140, "highPrice": 143, "lowPrice": 139, "closePrice": 141, "volume": 5500000, "marketCap": 2_520_000_000_000, "changePercent": 0.71},
    "PROVIDA": {"lastPrice": 2150, "openPrice": 2130, "highPrice": 2170, "lowPrice": 2110, "closePrice": 2140, "volume": 95000, "marketCap": 580_000_000_000, "changePercent": 0.47},
    "PARAUCO": {"lastPrice": 1580, "openPrice": 1560, "highPrice": 1600, "lowPrice": 1550, "closePrice": 1570, "volume": 350000, "marketCap": 1_420_000_000_000, "changePercent": 0.64},
    "AGUAS-A": {"lastPrice": 285, "openPrice": 283, "highPrice": 287, "lowPrice": 281, "closePrice": 284, "volume": 2200000, "marketCap": 1_510_000_000_000, "changePercent": 0.35},
    "ECL": {"lastPrice": 870, "openPrice": 860, "highPrice": 880, "lowPrice": 855, "closePrice": 865, "volume": 420000, "marketCap": 920_000_000_000, "changePercent": 0.58},
    "SECURITY": {"lastPrice": 198, "openPrice": 196, "highPrice": 200, "lowPrice": 195, "closePrice": 197, "volume": 1100000, "marketCap": 680_000_000_000, "changePercent": 0.51},
    "RIPLEY": {"lastPrice": 285, "openPrice": 282, "highPrice": 288, "lowPrice": 280, "closePrice": 283, "volume": 2800000, "marketCap": 520_000_000_000, "changePercent": 0.71},
}


def get_mock_price(ticker: str) -> dict | None:
    """Retorna precio mock con variación aleatoria pequeña."""
    base = STOCK_PRICES.get(ticker.upper())
    if not base:
        return None

    # Simular variación intraday de ±0.5%
    jitter = 1 + random.uniform(-0.005, 0.005)
    return {
        "nemo": ticker.upper(),
        "lastPrice": round(base["lastPrice"] * jitter, 2),
        "openPrice": base["openPrice"],
        "highPrice": base["highPrice"],
        "lowPrice": base["lowPrice"],
        "closePrice": base["closePrice"],
        "volume": base["volume"] + random.randint(-10000, 10000),
        "marketCap": base["marketCap"],
        "changePercent": round(base["changePercent"] + random.uniform(-0.3, 0.3), 2),
    }


def get_mock_history(ticker: str, days: int = 30) -> list[dict]:
    """Genera historial mock con tendencia realista."""
    base = STOCK_PRICES.get(ticker.upper())
    if not base:
        return []

    history = []
    price = base["lastPrice"]
    now = datetime.utcnow()

    for i in range(days, 0, -1):
        # Random walk con drift leve positivo
        daily_return = random.gauss(0.0002, 0.015)
        price = price * (1 + daily_return)

        day = now - timedelta(days=i)
        high = price * (1 + abs(random.gauss(0, 0.008)))
        low = price * (1 - abs(random.gauss(0, 0.008)))

        history.append({
            "date": day.isoformat(),
            "open": round(price * (1 + random.uniform(-0.005, 0.005)), 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(price, 2),
            "volume": base["volume"] + random.randint(-50000, 50000),
        })

    return history
