"""Parser de archivos PDF de reportes financieros.

Usa pdfplumber para extraer tablas de PDFs de earnings release.
Más complejo que XLSX porque:
1. Las tablas pueden cruzar múltiples páginas
2. El layout varía entre empresas
3. Puede haber tablas no-financieras (ej: producción, operaciones)

Heurísticas para identificar tablas EEFF:
- Income Statement: contiene "Revenue", "Net Income", "EBITDA"
- Balance Sheet: contiene "Assets", "Liabilities", "Equity"
- Cash Flow: contiene "Operating", "Investing", "Financing"
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .xlsx_financial_parser import ParsedFinancialData

logger = logging.getLogger(__name__)

# Keywords que identifican cada tipo de EEFF en tablas PDF
_INCOME_INDICATORS = [
    "revenue", "net income", "ebitda", "gross profit", "operating income",
    "ingresos", "utilidad neta", "ganancia bruta", "resultado operacional",
    "cost of sales", "costo de ventas",
]
_BALANCE_INDICATORS = [
    "total assets", "total liabilities", "equity", "current assets",
    "activos totales", "pasivos totales", "patrimonio", "activos corrientes",
    "cash and cash equivalents", "efectivo",
]
_CASHFLOW_INDICATORS = [
    "operating activities", "investing activities", "financing activities",
    "actividades de operación", "actividades de inversión",
    "cash generated", "free cash flow",
]


class PDFFinancialParser:
    """Parser de reportes financieros en formato PDF.

    Extrae tablas usando pdfplumber y las clasifica como
    Income Statement, Balance Sheet o Cash Flow.
    """

    def parse(self, file_path: Path, ticker: str = "") -> ParsedFinancialData:
        """Parsea un PDF y extrae los estados financieros.

        Args:
            file_path: Path al PDF
            ticker: Ticker de la empresa

        Returns:
            ParsedFinancialData con los datos extraídos
        """
        try:
            import pdfplumber
        except ImportError:
            raise ImportError(
                "pdfplumber requerido para parsear PDFs. "
                "Instalar: pip install pdfplumber"
            )

        logger.info(f"Parseando PDF: {file_path.name}")

        result = ParsedFinancialData(
            source_file=str(file_path),
            ticker=ticker,
        )

        with pdfplumber.open(file_path) as pdf:
            logger.info(f"  Páginas: {len(pdf.pages)}")

            all_tables: list[dict] = []

            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                if not tables:
                    continue

                logger.debug(f"  Página {page_num}: {len(tables)} tablas encontradas")

                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 3:
                        continue

                    classification = self._classify_table(table)
                    if classification:
                        all_tables.append({
                            "page": page_num,
                            "table_idx": table_idx,
                            "type": classification,
                            "data": table,
                        })
                        logger.info(
                            f"  Página {page_num}, Tabla {table_idx}: "
                            f"clasificada como {classification}"
                        )

            # Procesar tablas clasificadas
            for table_info in all_tables:
                data, periods = self._process_table(table_info["data"])
                table_type = table_info["type"]

                if table_type == "income_statement" and not result.has_income_statement:
                    result.income_statement = data
                    result.periods_found = periods
                elif table_type == "balance_sheet" and not result.has_balance_sheet:
                    result.balance_sheet = data
                    if not result.periods_found:
                        result.periods_found = periods
                elif table_type == "cash_flow" and not result.has_cash_flow:
                    result.cash_flow = data
                    if not result.periods_found:
                        result.periods_found = periods

        completeness = result.completeness_score
        logger.info(
            f"  Completitud: {completeness:.0%} "
            f"(IS={result.has_income_statement}, "
            f"BS={result.has_balance_sheet}, "
            f"CF={result.has_cash_flow})"
        )

        if completeness < 1.0:
            result.parsing_warnings.append(
                f"Solo se extrajeron {int(completeness*3)}/3 estados financieros del PDF"
            )

        return result

    def _classify_table(self, table: list[list]) -> str | None:
        """Clasifica una tabla como income/balance/cashflow o None.

        Concatena todo el texto de la tabla y busca indicadores clave.
        """
        text = " ".join(
            str(cell).lower()
            for row in table
            for cell in row
            if cell is not None
        )

        scores = {
            "income_statement": sum(1 for kw in _INCOME_INDICATORS if kw in text),
            "balance_sheet": sum(1 for kw in _BALANCE_INDICATORS if kw in text),
            "cash_flow": sum(1 for kw in _CASHFLOW_INDICATORS if kw in text),
        }

        # Necesita al menos 2 indicadores para clasificar
        best = max(scores, key=scores.get)
        if scores[best] >= 2:
            return best

        return None

    def _process_table(
        self, table: list[list],
    ) -> tuple[dict[str, dict[str, float | None]], list[str]]:
        """Procesa una tabla clasificada y extrae datos por período.

        Similar a _extract_sheet_data de XLSX pero adaptado a tablas PDF.
        """
        if not table or len(table) < 2:
            return {}, []

        # Encontrar header row
        header_row_idx = self._find_header_in_table(table)
        if header_row_idx is None:
            # Usar primera fila como header
            header_row_idx = 0

        headers = table[header_row_idx]
        periods = [
            str(h).strip()
            for h in headers[1:]
            if h is not None and str(h).strip()
        ]

        if not periods:
            return {}, []

        data: dict[str, dict[str, float | None]] = {p: {} for p in periods}

        for row_idx in range(header_row_idx + 1, len(table)):
            row = table[row_idx]
            if not row or not row[0]:
                continue

            label = str(row[0]).strip()
            if not label or len(label) < 2:
                continue

            # Clean label
            label = re.sub(r'\s+', ' ', label).strip()

            for col_idx, period in enumerate(periods):
                value_col = col_idx + 1
                if value_col < len(row):
                    parsed = self._parse_pdf_number(row[value_col])
                    data[period][label] = parsed

        return data, periods

    def _find_header_in_table(self, table: list[list]) -> int | None:
        """Encuentra la fila header en una tabla PDF."""
        period_pattern = re.compile(
            r'(?:\d{4})|(?:[QqTt]\d)|(?:FY)|(?:YTD)|'
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        )

        for idx, row in enumerate(table[:5]):
            if not row:
                continue
            matches = sum(
                1 for cell in row[1:]
                if cell and period_pattern.search(str(cell))
            )
            if matches >= 2:
                return idx

        return None

    def _parse_pdf_number(self, value) -> float | None:
        """Convierte un valor de celda PDF a float.

        PDF cells pueden tener más ruido que XLSX:
        - Espacios como separadores de miles
        - Paréntesis para negativos
        - Guiones para ceros
        - Texto mezclado
        """
        if value is None:
            return None

        text = str(value).strip()

        if not text or text in ("—", "–", "-", "n/a", "N/A", ""):
            return 0.0

        # Paréntesis = negativo
        is_negative = text.startswith("(") and text.endswith(")")
        if is_negative:
            text = text[1:-1]

        # Extraer solo la parte numérica
        # Maneja: "1.234,5" (formato ES) y "1,234.5" (formato EN)
        text = text.replace(" ", "").replace("$", "").replace("%", "")

        # Detectar formato de número (punto o coma como decimal)
        if re.match(r'^[\d.]+,\d{1,2}$', text):
            # Formato europeo/español: 1.234,56
            text = text.replace(".", "").replace(",", ".")
        else:
            # Formato anglosajón: 1,234.56
            text = text.replace(",", "")

        try:
            result = float(text)
            return -result if is_negative else result
        except ValueError:
            return None
