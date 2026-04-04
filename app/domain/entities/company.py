"""Entidad Company — configuración centralizada de empresas analizables.

Actúa como Company Registry: contiene toda la metadata necesaria para
analizar una empresa (ticker, shares outstanding, moneda de EEFF, sector, etc.).
Single Source of Truth — evita hardcodear datos en múltiples archivos.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EeffCurrency(str, Enum):
    """Moneda en la que se reportan los estados financieros."""
    USD = "USD"
    CLP = "CLP"


class Sector(str, Enum):
    """Sectores del mercado chileno."""
    MINERIA = "Minería"
    RETAIL = "Retail"
    BANCA = "Banca"
    ENERGIA = "Energía"
    FORESTAL = "Forestal"
    HOLDING = "Holding"
    INDUSTRIAL = "Industrial"
    CONSUMO = "Consumo"


@dataclass(frozen=True)
class Company:
    """Configuración inmutable de una empresa analizable.

    Attributes:
        ticker: Código bursátil en la Bolsa de Santiago (ej: "SQM-B")
        name: Nombre completo de la empresa
        yahoo_ticker: Ticker en Yahoo Finance (ej: "SQM-B.SN")
        shares_outstanding: Acciones en circulación
        eeff_currency: Moneda de los estados financieros
        sector: Sector económico
        is_active: Si la empresa está activa para análisis
    """
    ticker: str
    name: str
    yahoo_ticker: str
    shares_outstanding: int
    eeff_currency: EeffCurrency
    sector: Sector
    is_active: bool = True


# ============================================================
# IPSA Top 10 — Company Registry
# ============================================================
# Fuentes: CMF, memorias anuales, Yahoo Finance
# Última actualización: Marzo 2026

COMPANY_REGISTRY: dict[str, Company] = {}


def _register(*companies: Company) -> None:
    for c in companies:
        COMPANY_REGISTRY[c.ticker] = c


_register(
    Company(
        ticker="SQM-B",
        name="Sociedad Química y Minera de Chile",
        yahoo_ticker="SQM-B.SN",
        shares_outstanding=286_000_000,
        eeff_currency=EeffCurrency.USD,
        sector=Sector.MINERIA,
    ),
    Company(
        ticker="FALABELLA",
        name="Falabella S.A.",
        yahoo_ticker="FALABELLA.SN",
        shares_outstanding=2_534_572_211,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.RETAIL,
    ),
    Company(
        ticker="CENCOSUD",
        name="Cencosud S.A.",
        yahoo_ticker="CENCOSUD.SN",
        shares_outstanding=2_863_853_090,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.RETAIL,
    ),
    Company(
        ticker="BCI",
        name="Banco de Crédito e Inversiones",
        yahoo_ticker="BCI.SN",
        shares_outstanding=112_872_564,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.BANCA,
    ),
    Company(
        ticker="CHILE",
        name="Banco de Chile",
        yahoo_ticker="CHILE.SN",
        shares_outstanding=81_269_428_218,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.BANCA,
    ),
    Company(
        ticker="COPEC",
        name="Empresas Copec S.A.",
        yahoo_ticker="COPEC.SN",
        shares_outstanding=1_299_853_848,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.HOLDING,
    ),
    Company(
        ticker="CAP",
        name="CAP S.A.",
        yahoo_ticker="CAP.SN",
        shares_outstanding=149_448_817,
        eeff_currency=EeffCurrency.USD,
        sector=Sector.MINERIA,
    ),
    Company(
        ticker="ENELCHILE",
        name="Enel Chile S.A.",
        yahoo_ticker="ENELCHILE.SN",
        shares_outstanding=69_166_557_220,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.ENERGIA,
    ),
    Company(
        ticker="CMPC",
        name="Empresas CMPC S.A.",
        yahoo_ticker="CMPC.SN",
        shares_outstanding=2_467_529_217,
        eeff_currency=EeffCurrency.USD,
        sector=Sector.FORESTAL,
    ),
    Company(
        ticker="COLBUN",
        name="Colbún S.A.",
        yahoo_ticker="COLBUN.SN",
        shares_outstanding=17_536_840_091,
        eeff_currency=EeffCurrency.CLP,
        sector=Sector.ENERGIA,
    ),
)


def get_company(ticker: str) -> Company | None:
    """Obtiene una empresa por ticker. Case-insensitive."""
    return COMPANY_REGISTRY.get(ticker.upper()) or COMPANY_REGISTRY.get(ticker)


def get_all_active_companies() -> list[Company]:
    """Retorna todas las empresas activas para análisis."""
    return [c for c in COMPANY_REGISTRY.values() if c.is_active]


def get_companies_by_sector(sector: Sector) -> list[Company]:
    """Filtra empresas por sector."""
    return [c for c in COMPANY_REGISTRY.values() if c.sector == sector and c.is_active]
