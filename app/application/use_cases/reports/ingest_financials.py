"""Use Case: Ingestar datos financieros desde XLSX/PDF.

Flujo:
1. Recibir archivo XLSX (upload o path local)
2. Parsear con XLSXFinancialParser
3. Normalizar con normalize_all_periods
4. Persistir cada FinancialStatement en DB (upsert)
5. Retornar resumen de ingesta
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.domain.entities.financial import FinancialStatement
from app.domain.repositories.financial_repository import FinancialRepository
from app.infrastructure.parsers.xlsx_financial_parser import XLSXFinancialParser
from app.infrastructure.parsers.normalizer import normalize_all_periods

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Resultado de una ingesta de datos financieros."""

    ticker: str
    source_file: str
    periods_processed: list[str] = field(default_factory=list)
    statements_saved: int = 0
    fields_mapped: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.statements_saved > 0 and len(self.errors) == 0

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "source_file": self.source_file,
            "success": self.success,
            "periods_processed": self.periods_processed,
            "statements_saved": self.statements_saved,
            "fields_mapped": self.fields_mapped,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class IngestFinancialsUseCase:
    """Orquesta la ingesta: XLSX → Parse → Normalize → DB."""

    financial_repository: FinancialRepository

    async def execute_from_file(
        self, file_path: Path, ticker: str
    ) -> IngestResult:
        """Ingesta desde archivo XLSX local.

        Args:
            file_path: Ruta al archivo XLSX
            ticker: Ticker de la empresa (ej: "SQM-B")

        Returns:
            IngestResult con resumen de la operación
        """
        result = IngestResult(ticker=ticker, source_file=str(file_path))

        # 1. Validar archivo
        if not file_path.exists():
            result.errors.append(f"Archivo no encontrado: {file_path}")
            return result

        if file_path.suffix.lower() not in (".xlsx", ".xls"):
            result.errors.append(
                f"Formato no soportado: {file_path.suffix}. Use .xlsx"
            )
            return result

        # 2. Parse XLSX
        try:
            parser = XLSXFinancialParser()
            parsed = parser.parse(file_path, ticker=ticker)

            if parsed.completeness_score == 0:
                result.errors.append(
                    "Parser no extrajo datos. Verifique formato del archivo."
                )
                result.warnings.extend(parsed.parsing_warnings)
                return result

            result.warnings.extend(parsed.parsing_warnings)

        except Exception as e:
            result.errors.append(f"Error parseando XLSX: {e}")
            logger.exception(f"Parse error for {ticker}: {e}")
            return result

        # 3. Normalize → FinancialStatement entities
        try:
            statements = normalize_all_periods(parsed)

            if not statements:
                result.errors.append(
                    "Normalización no produjo statements. "
                    "Verifique que los labels del XLSX sean reconocidos."
                )
                return result

        except Exception as e:
            result.errors.append(f"Error normalizando: {e}")
            logger.exception(f"Normalize error for {ticker}: {e}")
            return result

        # 4. Persist cada statement
        saved = 0
        for stmt in statements:
            try:
                await self.financial_repository.save_statement(stmt)
                saved += 1

                # Contar campos no-cero para métricas de calidad
                non_zero = _count_non_zero_fields(stmt)
                result.fields_mapped[stmt.period] = non_zero

                logger.info(
                    f"Saved {ticker} {stmt.period}: {non_zero} campos"
                )

            except Exception as e:
                result.warnings.append(
                    f"Error guardando {stmt.period}: {e}"
                )
                logger.error(f"Save error for {ticker} {stmt.period}: {e}")

        result.statements_saved = saved
        result.periods_processed = [s.period for s in statements]

        logger.info(
            f"Ingesta {ticker}: {saved}/{len(statements)} períodos guardados"
        )

        return result


def _count_non_zero_fields(stmt: FinancialStatement) -> int:
    """Cuenta campos financieros con valor no-cero."""
    financial_fields = [
        "revenue", "cost_of_revenue", "gross_profit", "operating_income",
        "ebitda", "ebit", "net_income", "interest_expense",
        "total_assets", "total_liabilities", "total_equity", "total_debt",
        "cash_and_equivalents", "current_assets", "current_liabilities",
        "operating_cash_flow", "capital_expenditure", "free_cash_flow",
        "dividends_paid",
    ]
    return sum(1 for f in financial_fields if getattr(stmt, f, 0) != 0)
