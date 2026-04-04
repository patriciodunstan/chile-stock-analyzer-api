"""Seed data: EEFF FY2025 de las 10 empresas IPSA Top.

Fuentes: Earnings releases, press releases, memorias anuales 2025.
Datos en la moneda de reporte de cada empresa (ver company.eeff_currency).

NOTA: Estos datos son aproximaciones basadas en reportes públicos.
Para producción, reemplazar con ingesta automatizada desde Yahoo Finance / CMF.

Uso:
    python scripts/seed_ipsa_data.py
"""
import asyncio
import sys
from pathlib import Path

# Agregar project root al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.domain.entities.financial import FinancialStatement
from app.infrastructure.persistence.database import async_session_factory, init_db


# ============================================================
# EEFF FY2025 — Datos en moneda de reporte de cada empresa
# ============================================================
# Unidades: Millones (USD o CLP según empresa)
# Fuentes: Earnings releases Q4 2025, memorias anuales

SEED_DATA: list[dict] = [
    # ── SQM-B (USD Millions) ──
    # Fuente: SQM Q4 2025 Earnings Release XLSX
    {
        "ticker": "SQM-B",
        "period": "2025-FY",
        "revenue": 4576.2,
        "cost_of_revenue": -3223.6,
        "gross_profit": 1352.6,
        "operating_income": 1153.4,
        "ebitda": 1576.0,
        "ebit": 1153.4,
        "net_income": 588.1,
        "interest_expense": -192.7,
        "total_assets": 14504.8,
        "total_liabilities": 8813.5,
        "total_equity": 5691.3,
        "total_debt": 4691.4,
        "cash_and_equivalents": 1635.5,
        "current_assets": 5578.3,
        "current_liabilities": 1707.2,
    },
    {
        "ticker": "SQM-B",
        "period": "2024-FY",
        "revenue": 4528.8,
        "cost_of_revenue": -3201.7,
        "gross_profit": 1327.1,
        "operating_income": 1172.0,
        "ebitda": 1514.4,
        "ebit": 1172.0,
        "net_income": -404.4,
        "interest_expense": -197.5,
        "total_assets": 14200.0,
        "total_liabilities": 8700.0,
        "total_equity": 5500.0,
        "total_debt": 4500.0,
        "cash_and_equivalents": 1800.0,
        "current_assets": 5400.0,
        "current_liabilities": 1600.0,
    },

    # ── FALABELLA (CLP Millions) ──
    # Revenue ~12.7B USD ≈ 11,684,000 CLP MM (TC~920)
    # EBITDA ~1,270,000 CLP MM; Net Income ~535,000 CLP MM
    {
        "ticker": "FALABELLA",
        "period": "2025-FY",
        "revenue": 11_684_000.0,
        "cost_of_revenue": -7_660_000.0,
        "gross_profit": 4_024_000.0,
        "operating_income": 1_050_000.0,
        "ebitda": 1_270_000.0,
        "ebit": 1_050_000.0,
        "net_income": 535_000.0,
        "interest_expense": -285_000.0,
        "total_assets": 19_500_000.0,
        "total_liabilities": 12_800_000.0,
        "total_equity": 6_700_000.0,
        "total_debt": 4_050_000.0,
        "cash_and_equivalents": 1_393_000.0,
        "current_assets": 5_200_000.0,
        "current_liabilities": 4_800_000.0,
    },
    {
        "ticker": "FALABELLA",
        "period": "2024-FY",
        "revenue": 10_350_000.0,
        "cost_of_revenue": -6_900_000.0,
        "gross_profit": 3_450_000.0,
        "operating_income": 780_000.0,
        "ebitda": 1_020_000.0,
        "ebit": 780_000.0,
        "net_income": 191_000.0,
        "interest_expense": -310_000.0,
        "total_assets": 18_800_000.0,
        "total_liabilities": 12_500_000.0,
        "total_equity": 6_300_000.0,
        "total_debt": 4_200_000.0,
        "cash_and_equivalents": 1_100_000.0,
        "current_assets": 4_900_000.0,
        "current_liabilities": 4_600_000.0,
    },

    # ── CENCOSUD (CLP Millions) ──
    # Revenue: CLP 16,595,000 MM; Net Income: CLP 398,119 MM
    {
        "ticker": "CENCOSUD",
        "period": "2025-FY",
        "revenue": 16_595_000.0,
        "cost_of_revenue": -12_150_000.0,
        "gross_profit": 4_445_000.0,
        "operating_income": 1_080_000.0,
        "ebitda": 1_650_000.0,
        "ebit": 1_080_000.0,
        "net_income": 398_119.0,
        "interest_expense": -380_000.0,
        "total_assets": 18_200_000.0,
        "total_liabilities": 11_900_000.0,
        "total_equity": 6_300_000.0,
        "total_debt": 5_280_000.0,
        "cash_and_equivalents": 850_000.0,
        "current_assets": 4_100_000.0,
        "current_liabilities": 5_200_000.0,
    },
    {
        "ticker": "CENCOSUD",
        "period": "2024-FY",
        "revenue": 16_493_815.0,
        "cost_of_revenue": -12_100_000.0,
        "gross_profit": 4_393_815.0,
        "operating_income": 980_000.0,
        "ebitda": 1_750_000.0,
        "ebit": 980_000.0,
        "net_income": 233_600.0,
        "interest_expense": -360_000.0,
        "total_assets": 17_500_000.0,
        "total_liabilities": 11_300_000.0,
        "total_equity": 6_200_000.0,
        "total_debt": 5_100_000.0,
        "cash_and_equivalents": 900_000.0,
        "current_assets": 4_000_000.0,
        "current_liabilities": 5_000_000.0,
    },

    # ── BCI (CLP Millions) ──
    # Banco — ingresos operacionales, utilidad neta
    {
        "ticker": "BCI",
        "period": "2025-FY",
        "revenue": 3_200_000.0,        # Ingresos operacionales
        "gross_profit": 3_200_000.0,    # Bancos: revenue ≈ gross profit
        "operating_income": 850_000.0,
        "ebitda": 950_000.0,
        "ebit": 850_000.0,
        "net_income": 520_000.0,
        "interest_expense": -1_800_000.0,  # Gasto financiero (fondeo)
        "total_assets": 62_000_000.0,
        "total_liabilities": 57_200_000.0,
        "total_equity": 4_800_000.0,
        "total_debt": 8_500_000.0,       # Bonos + deuda subordinada
        "cash_and_equivalents": 3_500_000.0,
        "current_assets": 25_000_000.0,
        "current_liabilities": 22_000_000.0,
    },
    {
        "ticker": "BCI",
        "period": "2024-FY",
        "revenue": 2_980_000.0,
        "gross_profit": 2_980_000.0,
        "operating_income": 750_000.0,
        "ebitda": 840_000.0,
        "ebit": 750_000.0,
        "net_income": 460_000.0,
        "interest_expense": -1_700_000.0,
        "total_assets": 58_000_000.0,
        "total_liabilities": 53_500_000.0,
        "total_equity": 4_500_000.0,
        "total_debt": 8_000_000.0,
        "cash_and_equivalents": 3_200_000.0,
        "current_assets": 23_000_000.0,
        "current_liabilities": 20_000_000.0,
    },

    # ── CHILE / Banco de Chile (CLP Millions) ──
    # Net income: CLP 1,192,262 MM; Revenue (operating): ~3,026,000 MM
    {
        "ticker": "CHILE",
        "period": "2025-FY",
        "revenue": 3_026_000.0,
        "gross_profit": 3_026_000.0,
        "operating_income": 1_500_000.0,
        "ebitda": 1_600_000.0,
        "ebit": 1_500_000.0,
        "net_income": 1_192_262.0,
        "interest_expense": -2_100_000.0,
        "total_assets": 56_000_000.0,
        "total_liabilities": 51_000_000.0,
        "total_equity": 5_000_000.0,
        "total_debt": 7_200_000.0,
        "cash_and_equivalents": 4_200_000.0,
        "current_assets": 22_000_000.0,
        "current_liabilities": 19_000_000.0,
    },
    {
        "ticker": "CHILE",
        "period": "2024-FY",
        "revenue": 2_850_000.0,
        "gross_profit": 2_850_000.0,
        "operating_income": 1_450_000.0,
        "ebitda": 1_540_000.0,
        "ebit": 1_450_000.0,
        "net_income": 1_207_800.0,
        "interest_expense": -1_950_000.0,
        "total_assets": 53_000_000.0,
        "total_liabilities": 48_200_000.0,
        "total_equity": 4_800_000.0,
        "total_debt": 6_800_000.0,
        "cash_and_equivalents": 3_800_000.0,
        "current_assets": 20_000_000.0,
        "current_liabilities": 18_000_000.0,
    },

    # ── COPEC (CLP Millions) ──
    # Revenue (TTM) ~28.3B USD ≈ 26,036,000 CLP MM
    {
        "ticker": "COPEC",
        "period": "2025-FY",
        "revenue": 26_036_000.0,
        "cost_of_revenue": -22_800_000.0,
        "gross_profit": 3_236_000.0,
        "operating_income": 1_350_000.0,
        "ebitda": 2_200_000.0,
        "ebit": 1_350_000.0,
        "net_income": 680_000.0,
        "interest_expense": -520_000.0,
        "total_assets": 22_000_000.0,
        "total_liabilities": 13_500_000.0,
        "total_equity": 8_500_000.0,
        "total_debt": 7_100_000.0,
        "cash_and_equivalents": 1_800_000.0,
        "current_assets": 6_500_000.0,
        "current_liabilities": 5_800_000.0,
    },
    {
        "ticker": "COPEC",
        "period": "2024-FY",
        "revenue": 24_500_000.0,
        "cost_of_revenue": -21_500_000.0,
        "gross_profit": 3_000_000.0,
        "operating_income": 1_200_000.0,
        "ebitda": 2_050_000.0,
        "ebit": 1_200_000.0,
        "net_income": 550_000.0,
        "interest_expense": -480_000.0,
        "total_assets": 21_000_000.0,
        "total_liabilities": 13_000_000.0,
        "total_equity": 8_000_000.0,
        "total_debt": 6_800_000.0,
        "cash_and_equivalents": 1_600_000.0,
        "current_assets": 6_200_000.0,
        "current_liabilities": 5_500_000.0,
    },

    # ── CAP (USD Millions) ──
    # Minería hierro + acero
    {
        "ticker": "CAP",
        "period": "2025-FY",
        "revenue": 3_800.0,
        "cost_of_revenue": -2_900.0,
        "gross_profit": 900.0,
        "operating_income": 520.0,
        "ebitda": 780.0,
        "ebit": 520.0,
        "net_income": 280.0,
        "interest_expense": -85.0,
        "total_assets": 7_200.0,
        "total_liabilities": 3_800.0,
        "total_equity": 3_400.0,
        "total_debt": 1_600.0,
        "cash_and_equivalents": 450.0,
        "current_assets": 2_100.0,
        "current_liabilities": 1_300.0,
    },
    {
        "ticker": "CAP",
        "period": "2024-FY",
        "revenue": 3_500.0,
        "cost_of_revenue": -2_750.0,
        "gross_profit": 750.0,
        "operating_income": 380.0,
        "ebitda": 650.0,
        "ebit": 380.0,
        "net_income": 180.0,
        "interest_expense": -90.0,
        "total_assets": 6_900.0,
        "total_liabilities": 3_600.0,
        "total_equity": 3_300.0,
        "total_debt": 1_500.0,
        "cash_and_equivalents": 400.0,
        "current_assets": 1_900.0,
        "current_liabilities": 1_200.0,
    },

    # ── ENELCHILE (CLP Millions) ──
    # Revenue: 4,663M USD ≈ 4,289,960 CLP MM; EBITDA 1,473M USD ≈ 1,355,160 CLP MM
    {
        "ticker": "ENELCHILE",
        "period": "2025-FY",
        "revenue": 4_289_960.0,
        "cost_of_revenue": -2_800_000.0,
        "gross_profit": 1_489_960.0,
        "operating_income": 980_000.0,
        "ebitda": 1_355_160.0,
        "ebit": 980_000.0,
        "net_income": 494_960.0,   # 538M USD
        "interest_expense": -180_000.0,
        "total_assets": 11_500_000.0,
        "total_liabilities": 6_800_000.0,
        "total_equity": 4_700_000.0,
        "total_debt": 2_800_000.0,
        "cash_and_equivalents": 650_000.0,
        "current_assets": 2_200_000.0,
        "current_liabilities": 2_000_000.0,
    },
    {
        "ticker": "ENELCHILE",
        "period": "2024-FY",
        "revenue": 3_885_000.0,
        "cost_of_revenue": -2_600_000.0,
        "gross_profit": 1_285_000.0,
        "operating_income": 500_000.0,
        "ebitda": 750_000.0,
        "ebit": 500_000.0,
        "net_income": -120_000.0,
        "interest_expense": -170_000.0,
        "total_assets": 11_000_000.0,
        "total_liabilities": 6_500_000.0,
        "total_equity": 4_500_000.0,
        "total_debt": 2_700_000.0,
        "cash_and_equivalents": 580_000.0,
        "current_assets": 2_000_000.0,
        "current_liabilities": 1_900_000.0,
    },

    # ── CMPC (USD Millions) ──
    # Revenue: 7,604M USD; EBITDA: 1,410M USD
    {
        "ticker": "CMPC",
        "period": "2025-FY",
        "revenue": 7_604.0,
        "cost_of_revenue": -5_700.0,
        "gross_profit": 1_904.0,
        "operating_income": 920.0,
        "ebitda": 1_410.0,
        "ebit": 920.0,
        "net_income": 380.0,
        "interest_expense": -220.0,
        "total_assets": 14_500.0,
        "total_liabilities": 7_800.0,
        "total_equity": 6_700.0,
        "total_debt": 3_900.0,
        "cash_and_equivalents": 800.0,
        "current_assets": 3_500.0,
        "current_liabilities": 2_300.0,
    },
    {
        "ticker": "CMPC",
        "period": "2024-FY",
        "revenue": 6_800.0,
        "cost_of_revenue": -5_200.0,
        "gross_profit": 1_600.0,
        "operating_income": 750.0,
        "ebitda": 1_200.0,
        "ebit": 750.0,
        "net_income": 290.0,
        "interest_expense": -210.0,
        "total_assets": 13_800.0,
        "total_liabilities": 7_500.0,
        "total_equity": 6_300.0,
        "total_debt": 3_700.0,
        "cash_and_equivalents": 700.0,
        "current_assets": 3_200.0,
        "current_liabilities": 2_200.0,
    },

    # ── COLBUN (CLP Millions) ──
    # Energía — empresa mediana
    {
        "ticker": "COLBUN",
        "period": "2025-FY",
        "revenue": 2_450_000.0,
        "cost_of_revenue": -1_750_000.0,
        "gross_profit": 700_000.0,
        "operating_income": 420_000.0,
        "ebitda": 620_000.0,
        "ebit": 420_000.0,
        "net_income": 250_000.0,
        "interest_expense": -85_000.0,
        "total_assets": 6_500_000.0,
        "total_liabilities": 3_200_000.0,
        "total_equity": 3_300_000.0,
        "total_debt": 1_400_000.0,
        "cash_and_equivalents": 350_000.0,
        "current_assets": 1_200_000.0,
        "current_liabilities": 900_000.0,
    },
    {
        "ticker": "COLBUN",
        "period": "2024-FY",
        "revenue": 2_200_000.0,
        "cost_of_revenue": -1_600_000.0,
        "gross_profit": 600_000.0,
        "operating_income": 350_000.0,
        "ebitda": 540_000.0,
        "ebit": 350_000.0,
        "net_income": 200_000.0,
        "interest_expense": -80_000.0,
        "total_assets": 6_200_000.0,
        "total_liabilities": 3_000_000.0,
        "total_equity": 3_200_000.0,
        "total_debt": 1_350_000.0,
        "cash_and_equivalents": 300_000.0,
        "current_assets": 1_100_000.0,
        "current_liabilities": 850_000.0,
    },
]


async def seed():
    """Inserta seed data en la base de datos."""
    await init_db()

    async with async_session_factory() as session:
        from app.infrastructure.persistence.repositories.sqlalchemy_financial_repository import (
            SQLAlchemyFinancialRepository,
        )

        repo = SQLAlchemyFinancialRepository(session)

        count = 0
        for data in SEED_DATA:
            stmt = FinancialStatement(**data)
            await repo.save_statement(stmt)
            count += 1

        await session.commit()
        print(f"\n✅ Seed completado: {count} statements insertados")
        print(f"   Empresas: {len(set(d['ticker'] for d in SEED_DATA))}")
        print(f"   Períodos por empresa: FY2024 + FY2025")


if __name__ == "__main__":
    asyncio.run(seed())
