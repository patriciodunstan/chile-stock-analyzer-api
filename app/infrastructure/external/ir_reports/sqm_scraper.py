"""Scraper para la página de Investor Relations de SQM.

SQM usa la plataforma Q4Web/Nasdaq IR, que tiene una estructura predecible:
- URL base: https://ir.sqm.com
- Quarterly Results: /financials/quarterly-results
- Annual Reports: /financials/annual-reports

Cada trimestre tiene:
- Financial Statement (PDF)
- Earnings Release (PDF)
- Earnings Presentation (PDF)
- Earnings Release Tables (XLSX) — datos tabulares listos
- Webcast (HTML)

El XLSX de "Earnings Release Tables" es la fuente ideal porque:
1. Datos ya tabulares (no requiere OCR/parsing de tablas)
2. Incluye Income Statement, Balance Sheet, Cash Flow
3. Múltiples períodos comparativos
"""
from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .base_scraper import (
    BaseIRScraper,
    DownloadResult,
    ReportFormat,
    ReportMetadata,
    ReportPeriod,
    ReportType,
)

logger = logging.getLogger(__name__)

# Patrones de clasificación ordenados por especificidad (más específico primero).
# El orden importa: "earnings release tables" debe evaluarse ANTES de "earnings release".
_CLASSIFY_PATTERNS: list[tuple[str, ReportType, ReportFormat]] = [
    ("earnings release tables", ReportType.EARNINGS_TABLES, ReportFormat.XLSX),
    ("financial statement", ReportType.FINANCIAL_STATEMENT, ReportFormat.PDF),
    ("earnings presentation", ReportType.EARNINGS_PRESENTATION, ReportFormat.PDF),
    ("earnings release", ReportType.EARNINGS_RELEASE, ReportFormat.PDF),
]

# Mapeo de texto Q → ReportPeriod
_PERIOD_MAP: dict[str, ReportPeriod] = {
    "q1": ReportPeriod.Q1,
    "q2": ReportPeriod.Q2,
    "q3": ReportPeriod.Q3,
    "q4": ReportPeriod.Q4,
    "1q": ReportPeriod.Q1,
    "2q": ReportPeriod.Q2,
    "3q": ReportPeriod.Q3,
    "4q": ReportPeriod.Q4,
    "first quarter": ReportPeriod.Q1,
    "second quarter": ReportPeriod.Q2,
    "third quarter": ReportPeriod.Q3,
    "fourth quarter": ReportPeriod.Q4,
}

# Regex para detectar período/año en URLs y texto
_PERIOD_YEAR_REGEX = re.compile(r'(\d)[Qq](\d{4})')           # 4Q2025, 1Q2024
_Q_YEAR_REGEX = re.compile(r'[Qq](\d)\s*(\d{4})')             # Q4 2025
_YEAR_ONLY_REGEX = re.compile(r'/(\d{4})/')                    # /2025/

# Headers de browser para evitar bloqueos
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 60.0


class SQMScraper(BaseIRScraper):
    """Scraper específico para SQM Investor Relations.

    Hereda de BaseIRScraper e implementa los métodos abstractos
    para la estructura particular de ir.sqm.com (Q4Web/Nasdaq IR).
    """

    def __init__(self, data_dir: Path):
        super().__init__(
            ticker="SQM-B",
            company_name="Sociedad Química y Minera de Chile S.A.",
            base_url="https://ir.sqm.com",
            data_dir=data_dir,
        )
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy initialization del HTTP client con retry y timeout robusto."""
        if self._client is None or self._client.is_closed:
            transport = httpx.AsyncHTTPTransport(retries=_MAX_RETRIES)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(_TIMEOUT_SECONDS, connect=30.0),
                follow_redirects=True,
                headers=_BROWSER_HEADERS,
                transport=transport,
            )
        return self._client

    async def close(self):
        """Cierra el HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def discover_reports(
        self,
        year: int | None = None,
        period: ReportPeriod | None = None,
    ) -> list[ReportMetadata]:
        """Descubre reportes en ir.sqm.com/financials/quarterly-results.

        El HTML de SQM tiene una estructura donde cada trimestre agrupa
        links de descarga (PDF/XLSX) con texto descriptivo del tipo.
        """
        client = await self._get_client()
        url = f"{self.base_url}/financials/quarterly-results"

        logger.info(f"[SQM] Fetching quarterly results page: {url}")

        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"[SQM] Error fetching quarterly results: {type(e).__name__}: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        reports: list[ReportMetadata] = []
        seen_urls: set[str] = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            text = link.get_text(strip=True).lower()

            # Solo procesar links a archivos descargables
            if not self._is_downloadable_link(href):
                continue

            # Clasificar tipo de reporte
            report_info = self._classify_link(text, href)
            if report_info is None:
                continue

            report_type, report_format = report_info

            # Detectar período y año
            detected_period, detected_year = self._detect_period_year(link, href)
            if detected_year is None:
                continue

            # Aplicar filtros del usuario
            if year is not None and detected_year != year:
                continue
            if period is not None and detected_period != period:
                continue

            # Construir URL completa
            full_url = href if href.startswith("http") else f"{self.base_url}{href}"

            # Deduplicar (la misma URL puede aparecer en varias secciones)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            report = ReportMetadata(
                ticker=self.ticker,
                company_name=self.company_name,
                report_type=report_type,
                report_format=report_format,
                period=detected_period or ReportPeriod.Q4,
                year=detected_year,
                url=full_url,
                title=link.get_text(strip=True),
            )

            reports.append(report)
            logger.debug(
                f"[SQM] Descubierto: {report.filename} "
                f"({report.report_type.value}, {report.period.value} {report.year})"
            )

        logger.info(f"[SQM] Total reportes descubiertos: {len(reports)}")
        return reports

    async def download_report(self, report: ReportMetadata) -> DownloadResult:
        """Descarga un reporte de SQM."""
        local_path = self._get_local_path(report)

        # Si ya existe, skip
        if local_path.exists() and local_path.stat().st_size > 0:
            logger.info(f"[SQM] Ya descargado: {local_path.name}")
            return DownloadResult(
                metadata=report,
                local_path=local_path,
                success=True,
                bytes_downloaded=local_path.stat().st_size,
            )

        client = await self._get_client()

        try:
            response = await client.get(report.url)
            response.raise_for_status()

            content = response.content
            if len(content) == 0:
                return DownloadResult(
                    metadata=report,
                    local_path=local_path,
                    success=False,
                    error="Archivo vacío (0 bytes)",
                )

            local_path.write_bytes(content)

            return DownloadResult(
                metadata=report,
                local_path=local_path,
                success=True,
                bytes_downloaded=len(content),
            )

        except httpx.HTTPError as e:
            return DownloadResult(
                metadata=report,
                local_path=local_path,
                success=False,
                error=f"{type(e).__name__}: {e}",
            )

    # ----------------------------------------------------------
    # Clasificación de links
    # ----------------------------------------------------------

    @staticmethod
    def _is_downloadable_link(href: str) -> bool:
        """Verifica si el link apunta a un archivo descargable."""
        href_lower = href.lower()
        return any(
            ext in href_lower
            for ext in (".pdf", ".xlsx", ".xls")
        )

    @staticmethod
    def _classify_link(
        text: str, href: str,
    ) -> tuple[ReportType, ReportFormat] | None:
        """Clasifica un link como tipo de reporte financiero.

        Prioriza clasificación por texto del link sobre extensión de archivo.
        El orden de _CLASSIFY_PATTERNS asegura que "earnings release tables"
        matchee antes que "earnings release".
        """
        # Clasificar por texto del link (más confiable)
        for keyword, report_type, report_format in _CLASSIFY_PATTERNS:
            if keyword in text:
                # Verificar formato real del archivo vs texto
                actual_format = report_format
                if href.lower().endswith(".xlsx"):
                    actual_format = ReportFormat.XLSX
                elif href.lower().endswith(".pdf"):
                    actual_format = ReportFormat.PDF
                return (report_type, actual_format)

        # Fallback: clasificar por extensión + contenido de URL
        href_lower = href.lower()
        if href_lower.endswith(".xlsx"):
            return (ReportType.EARNINGS_TABLES, ReportFormat.XLSX)
        if href_lower.endswith(".pdf"):
            if "financial" in text or "statement" in text:
                return (ReportType.FINANCIAL_STATEMENT, ReportFormat.PDF)
            if "presentation" in text:
                return (ReportType.EARNINGS_PRESENTATION, ReportFormat.PDF)
            # PDF genérico con datos financieros en el nombre del archivo
            if "table" in href_lower or "earning" in href_lower:
                return (ReportType.EARNINGS_RELEASE, ReportFormat.PDF)

        return None

    @staticmethod
    def _detect_period_year(
        link_element, href: str,
    ) -> tuple[ReportPeriod | None, int | None]:
        """Detecta período (Q1-Q4) y año del reporte.

        Estrategias en orden de confiabilidad:
        1. URL del archivo (ej: Tables_4Q2025_eng.xlsx → Q4, 2025)
        2. Heading inmediato (solo 3 niveles arriba, busca headings h2-h4)
        3. Año en path de URL (ej: /2025/... → None, 2025)

        Nota: La Estrategia 2 es limitada intencionalmente para evitar
        que links dentro de accordions capturen el heading del bloque
        principal de la página.
        """
        # Estrategia 1: Buscar en URL del archivo (más confiable)
        match = _PERIOD_YEAR_REGEX.search(href)
        if match:
            q_num = match.group(1)
            year_str = match.group(2)
            period = _PERIOD_MAP.get(f"q{q_num}")
            return (period, int(year_str))

        match = _Q_YEAR_REGEX.search(href)
        if match:
            q_num = match.group(1)
            year_str = match.group(2)
            period = _PERIOD_MAP.get(f"q{q_num}")
            return (period, int(year_str))

        # Estrategia 2: Buscar heading inmediato (limitado a 3 niveles)
        # Solo buscar en elementos heading (h2, h3, h4) cercanos, no en todo
        # el parent tree, para evitar capturar el heading de toda la sección
        parent = link_element.parent
        for _ in range(3):
            if parent is None:
                break

            # Buscar headings hermanos o el propio parent si es heading
            headings = parent.find_all(["h2", "h3", "h4", "h5"], recursive=False)
            for heading in headings:
                heading_text = heading.get_text(strip=True)
                match = _PERIOD_YEAR_REGEX.search(heading_text)
                if match:
                    q_num = match.group(1)
                    year_str = match.group(2)
                    period = _PERIOD_MAP.get(f"q{q_num}")
                    return (period, int(year_str))

                match = _Q_YEAR_REGEX.search(heading_text)
                if match:
                    q_num = match.group(1)
                    year_str = match.group(2)
                    period = _PERIOD_MAP.get(f"q{q_num}")
                    return (period, int(year_str))

            # Verificar si el parent mismo es un heading
            if parent.name in ("h2", "h3", "h4", "h5"):
                parent_text = parent.get_text(strip=True)
                match = _PERIOD_YEAR_REGEX.search(parent_text)
                if match:
                    q_num = match.group(1)
                    year_str = match.group(2)
                    period = _PERIOD_MAP.get(f"q{q_num}")
                    return (period, int(year_str))

            parent = parent.parent

        # Estrategia 3: Año en path de la URL (sin período)
        year_match = _YEAR_ONLY_REGEX.search(href)
        if year_match:
            year = int(year_match.group(1))
            # Solo aceptar si el año está en un rango razonable
            if 2015 <= year <= 2030:
                return (None, year)

        return (None, None)
