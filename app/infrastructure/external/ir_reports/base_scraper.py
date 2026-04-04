"""Base scraper abstracto para páginas de Investor Relations.

Define el contrato que cada scraper específico debe implementar.
Patrón Strategy: cada empresa tiene su propia implementación.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    """Tipos de reportes financieros disponibles en páginas IR."""
    FINANCIAL_STATEMENT = "financial_statement"
    EARNINGS_RELEASE = "earnings_release"
    EARNINGS_PRESENTATION = "earnings_presentation"
    EARNINGS_TABLES = "earnings_tables"  # XLSX con datos tabulares
    ANNUAL_REPORT = "annual_report"


class ReportFormat(str, Enum):
    """Formatos de archivo de reportes."""
    PDF = "pdf"
    XLSX = "xlsx"
    HTML = "html"


class ReportPeriod(str, Enum):
    """Períodos de reporte."""
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    ANNUAL = "FY"


@dataclass(frozen=True)
class ReportMetadata:
    """Metadata de un reporte financiero descubierto en la página IR.

    Inmutable (frozen) porque es un value object del dominio.
    """
    ticker: str
    company_name: str
    report_type: ReportType
    report_format: ReportFormat
    period: ReportPeriod
    year: int
    url: str
    title: str = ""
    published_date: date | None = None
    file_size_bytes: int | None = None

    @property
    def filename(self) -> str:
        """Genera nombre de archivo consistente."""
        ext = self.report_format.value
        return f"{self.ticker}_{self.period.value}_{self.year}_{self.report_type.value}.{ext}"

    @property
    def is_tabular(self) -> bool:
        """True si el reporte contiene datos tabulares directos (XLSX)."""
        return self.report_format == ReportFormat.XLSX


@dataclass
class DownloadResult:
    """Resultado de una descarga de reporte."""
    metadata: ReportMetadata
    local_path: Path
    success: bool
    error: str | None = None
    bytes_downloaded: int = 0


class BaseIRScraper(ABC):
    """Scraper abstracto para páginas de Investor Relations.

    Cada empresa implementa su propia versión porque:
    - Cada sitio tiene estructura HTML diferente
    - Los patrones de URL varían por plataforma (Q4Web, WordPress, custom)
    - Los formatos de archivo y naming conventions difieren
    """

    def __init__(self, ticker: str, company_name: str, base_url: str, data_dir: Path):
        self.ticker = ticker
        self.company_name = company_name
        self.base_url = base_url
        self.data_dir = data_dir / ticker.lower()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    async def discover_reports(
        self,
        year: int | None = None,
        period: ReportPeriod | None = None,
    ) -> list[ReportMetadata]:
        """Descubre reportes disponibles en la página IR.

        Args:
            year: Filtrar por año. None = todos los disponibles.
            period: Filtrar por período. None = todos.

        Returns:
            Lista de ReportMetadata con URLs de descarga.
        """
        ...

    @abstractmethod
    async def download_report(self, report: ReportMetadata) -> DownloadResult:
        """Descarga un reporte específico.

        Args:
            report: Metadata del reporte a descargar.

        Returns:
            DownloadResult con path local y status.
        """
        ...

    async def discover_and_download_all(
        self,
        year: int | None = None,
        period: ReportPeriod | None = None,
        formats: list[ReportFormat] | None = None,
    ) -> list[DownloadResult]:
        """Descubre y descarga todos los reportes que matchean los filtros.

        Prioriza XLSX sobre PDF cuando ambos están disponibles.
        """
        reports = await self.discover_reports(year=year, period=period)

        if formats:
            reports = [r for r in reports if r.report_format in formats]

        logger.info(
            f"[{self.ticker}] Descubiertos {len(reports)} reportes "
            f"(year={year}, period={period})"
        )

        results = []
        for report in reports:
            logger.info(
                f"[{self.ticker}] Descargando: {report.filename} "
                f"desde {report.url[:80]}..."
            )
            result = await self.download_report(report)
            results.append(result)

            if result.success:
                logger.info(
                    f"[{self.ticker}] OK: {result.local_path.name} "
                    f"({result.bytes_downloaded:,} bytes)"
                )
            else:
                logger.warning(
                    f"[{self.ticker}] FAIL: {report.filename} — {result.error}"
                )

        return results

    def _get_local_path(self, report: ReportMetadata) -> Path:
        """Genera path local para almacenar el reporte."""
        year_dir = self.data_dir / str(report.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        return year_dir / report.filename
