"""Normalización de datos financieros extraídos → Entidades de dominio.

Mapea los campos extraídos de XLSX/PDF (que varían por empresa y formato)
a los campos estandarizados de FinancialStatement.

Ejemplo:
    "Revenues" → revenue
    "Cost of sales" → cost_of_revenue
    "Total assets" → total_assets
    "Net cash from operating activities" → operating_cash_flow
"""
from __future__ import annotations

import logging
import re

from app.domain.entities.financial import FinancialStatement
from app.infrastructure.parsers.xlsx_financial_parser import ParsedFinancialData

logger = logging.getLogger(__name__)

# Mapeo de labels extraídos → campo de FinancialStatement
# Cada campo tiene múltiples variantes (EN + ES) para ser robusto
_FIELD_MAPPING: dict[str, list[str]] = {
    # === Income Statement ===
    "revenue": [
        "revenue", "revenues", "net revenue", "net revenues",
        "total revenue", "total revenues", "net sales", "sales",
        "ingresos", "ingresos netos", "ventas netas", "ingresos de actividades ordinarias",
    ],
    "cost_of_revenue": [
        "cost of sales", "cost of revenue", "cost of goods sold", "cogs",
        "costo de ventas", "costo de los ingresos",
    ],
    "gross_profit": [
        "gross profit", "gross margin", "ganancia bruta", "margen bruto",
        "utilidad bruta",
    ],
    "operating_income": [
        "operating income", "operating profit", "operating earnings",
        "resultado operacional", "utilidad operacional", "ganancia operacional",
        "income from operations",
    ],
    "ebitda": [
        "ebitda", "adjusted ebitda",
    ],
    "depreciation_amortization": [
        "depreciation and amortization", "depreciation and amortization expenses",
        "depreciation & amortization", "d&a",
        "depreciación y amortización",
    ],
    "ebit": [
        "ebit", "earnings before interest and tax",
    ],
    "net_income": [
        "net income", "net profit", "net earnings", "profit for the period",
        "utilidad neta", "ganancia neta", "resultado neto",
        "profit attributable to owners", "net income attributable",
        "profit attributable to the owners",
        "profit attributable to sqm shareholders",
    ],
    "interest_expense": [
        "interest expense", "finance costs", "financial costs",
        "financial expenses", "finance expense",
        "gastos financieros", "costos financieros",
    ],

    # === Balance Sheet ===
    "total_assets": [
        "total assets", "activos totales", "total de activos",
    ],
    "total_liabilities": [
        "total liabilities", "pasivos totales", "total de pasivos",
    ],
    "total_equity": [
        "total equity", "total stockholders equity",
        "total shareholders' equity", "shareholders' equity",
        "patrimonio total", "total del patrimonio",
        "total equity attributable",
        "equity attributable to owners",
    ],
    "total_debt": [
        "total debt", "total borrowings", "total financial debt",
        "deuda total", "deuda financiera total",
        "total financial liabilities",
    ],
    "short_term_debt": [
        "short-term debt", "short term debt", "current portion of long-term debt",
        "short-term borrowings", "current financial liabilities",
        "deuda corto plazo", "deuda a corto plazo",
    ],
    "long_term_debt": [
        "long-term debt", "long term debt", "long-term borrowings",
        "non-current financial liabilities", "long-term financial liabilities",
        "deuda largo plazo", "deuda a largo plazo",
    ],
    "long_term_liabilities": [
        "total long-term liabilities", "total non-current liabilities",
        "long-term liabilities", "non-current liabilities",
        "pasivos no corrientes", "pasivos a largo plazo",
    ],
    "cash_and_equivalents": [
        "cash and cash equivalents", "cash and equivalents",
        "efectivo y equivalentes", "cash",
    ],
    "current_assets": [
        "total current assets", "current assets",
        "activos corrientes totales", "activos corrientes",
    ],
    "current_liabilities": [
        "total current liabilities", "current liabilities",
        "pasivos corrientes totales", "pasivos corrientes",
    ],

    # === Cash Flow ===
    "operating_cash_flow": [
        "net cash from operating activities",
        "cash flows from operating activities",
        "net cash provided by operating activities",
        "flujo de efectivo de actividades de operación",
        "cash generated from operations",
    ],
    "capital_expenditure": [
        "capital expenditures", "capex", "capital expenditure",
        "purchases of property", "additions to property",
        "gastos de capital", "inversiones en activo fijo",
    ],
    "free_cash_flow": [
        "free cash flow", "fcf", "flujo de caja libre",
    ],
    "dividends_paid": [
        "dividends paid", "dividend paid", "payment of dividends",
        "dividendos pagados",
    ],
}

# Invertir el mapping para búsqueda rápida: label → field_name
_LABEL_TO_FIELD: dict[str, str] = {}
for field_name, labels in _FIELD_MAPPING.items():
    for label in labels:
        _LABEL_TO_FIELD[label.lower()] = field_name

# Patrones de exclusión: si un label matchea un campo pero contiene alguno
# de estos substrings, el match es inválido. Evita falsos positivos como
# "Total Liabilities & Shareholders' Equity" → total_liabilities
_EXCLUSION_PATTERNS: dict[str, list[str]] = {
    "total_liabilities": [
        "equity", "shareholders", "stockholders", "patrimonio",
    ],
    "net_income": [
        "before minority", "before non-controlling",
        "antes de minoritario", "antes de interés minoritario",
    ],
    "total_equity": [
        "liabilities",  # Excluir "Total Liabilities and Equity"
    ],
    "current_assets": [
        "non-current", "non current", "no corriente",
    ],
    "current_liabilities": [
        "non-current", "non current", "no corriente",
    ],
}


def normalize_to_financial_statement(
    parsed_data: ParsedFinancialData,
    period_key: str,
) -> FinancialStatement | None:
    """Normaliza datos extraídos de un período a FinancialStatement.

    Args:
        parsed_data: Datos parseados del XLSX/PDF
        period_key: Key del período a normalizar (ej: "Q4 2025", "FY 2025")

    Returns:
        FinancialStatement populado, o None si no hay datos
    """
    # Recopilar métricas de los 3 estados para este período
    all_metrics: dict[str, float | None] = {}

    for source_name, source_data in [
        ("income_statement", parsed_data.income_statement),
        ("balance_sheet", parsed_data.balance_sheet),
        ("cash_flow", parsed_data.cash_flow),
        ("ebitda_data", parsed_data.ebitda_data),
    ]:
        if period_key in source_data:
            all_metrics.update(source_data[period_key])

    if not all_metrics:
        logger.warning(f"No hay datos para período '{period_key}'")
        return None

    # Mapear cada métrica extraída a un campo de FinancialStatement
    mapped: dict[str, float] = {}

    for label, value in all_metrics.items():
        if value is None:
            continue

        field_name = _match_label_to_field(label)
        if field_name:
            mapped[field_name] = value
            logger.debug(f"  Mapeado: '{label}' → {field_name} = {value}")

    if not mapped:
        logger.warning(f"Ninguna métrica pudo mapearse para '{period_key}'")
        return None

    # Normalizar período
    normalized_period = _normalize_period_key(period_key, parsed_data.ticker)

    # Construir entidad
    stmt = FinancialStatement(
        ticker=parsed_data.ticker,
        period=normalized_period,
    )

    # Asignar campos mapeados (solo los que existen en FinancialStatement)
    for field_name, value in mapped.items():
        if hasattr(stmt, field_name):
            setattr(stmt, field_name, value)

    # Calcular campos derivados si faltan (pasar extras para cálculos)
    _calculate_derived_fields(stmt, extra_mapped=mapped)

    logger.info(
        f"  Normalizado {period_key} → {normalized_period}: "
        f"{len(mapped)} campos mapeados"
    )

    return stmt


def normalize_all_periods(
    parsed_data: ParsedFinancialData,
) -> list[FinancialStatement]:
    """Normaliza todos los períodos de un ParsedFinancialData.

    Primero normaliza los period keys (ej: "Q4 2025" y "Dec 2025" → "2025-Q4"),
    luego mergea datos de diferentes estados financieros que comparten el mismo
    período normalizado.

    Returns:
        Lista de FinancialStatement, uno por período normalizado.
    """
    # Paso 1: Construir mapa de período normalizado → métricas mergeadas
    merged: dict[str, dict[str, float | None]] = {}

    for source_name, source_data in [
        ("income_statement", parsed_data.income_statement),
        ("balance_sheet", parsed_data.balance_sheet),
        ("cash_flow", parsed_data.cash_flow),
        ("ebitda_data", parsed_data.ebitda_data),
    ]:
        for raw_period, metrics in source_data.items():
            norm_period = _normalize_period_key(raw_period, parsed_data.ticker)
            if norm_period not in merged:
                merged[norm_period] = {}
            # Mergear métricas (no sobreescribir si ya existe)
            for label, value in metrics.items():
                if label not in merged[norm_period] or merged[norm_period][label] is None:
                    merged[norm_period][label] = value

    # Paso 2: Convertir cada período mergeado a FinancialStatement
    # Mapear con prioridad por fuente: IS > BS > CF > EBITDA
    # Procesamos las fuentes en orden de prioridad y usamos "first wins"
    # para evitar que EBITDA sobreescriba valores más precisos del IS
    _SOURCES_PRIORITY = [
        ("income_statement", parsed_data.income_statement),
        ("balance_sheet", parsed_data.balance_sheet),
        ("cash_flow", parsed_data.cash_flow),
        ("ebitda_data", parsed_data.ebitda_data),
    ]

    results = []
    for norm_period in sorted(merged.keys()):
        # Mapear labels a campos con prioridad por fuente
        mapped: dict[str, float] = {}

        for source_name, source_data in _SOURCES_PRIORITY:
            for raw_period, metrics in source_data.items():
                if _normalize_period_key(raw_period, parsed_data.ticker) != norm_period:
                    continue
                for label, value in metrics.items():
                    if value is None:
                        continue
                    field_name = _match_label_to_field(label)
                    if field_name and field_name not in mapped:
                        # First wins: fuente con mayor prioridad prevalece
                        mapped[field_name] = value

        if not mapped:
            continue

        stmt = FinancialStatement(
            ticker=parsed_data.ticker,
            period=norm_period,
        )

        for field_name, value in mapped.items():
            if hasattr(stmt, field_name):
                setattr(stmt, field_name, value)

        _calculate_derived_fields(stmt, extra_mapped=mapped)
        results.append(stmt)

        logger.info(
            f"  Normalizado {norm_period}: {len(mapped)} campos mapeados"
        )

    logger.info(
        f"  Normalización completada: {len(results)} períodos"
    )
    return results


def _match_label_to_field(label: str) -> str | None:
    """Busca el campo de FinancialStatement que corresponde a un label.

    Usa matching exacto primero, luego fuzzy (contains).
    Aplica patrones de exclusión para evitar falsos positivos.
    """
    label_lower = label.lower().strip()

    def _is_excluded(field_name: str) -> bool:
        """Verifica si el label debe excluirse para este campo."""
        exclusions = _EXCLUSION_PATTERNS.get(field_name, [])
        return any(excl in label_lower for excl in exclusions)

    # Match exacto
    if label_lower in _LABEL_TO_FIELD:
        field = _LABEL_TO_FIELD[label_lower]
        if not _is_excluded(field):
            return field

    # Match parcial (el label contiene el keyword)
    for keyword, field_name in _LABEL_TO_FIELD.items():
        if keyword in label_lower:
            if not _is_excluded(field_name):
                return field_name

    # Match parcial inverso (el keyword contiene el label)
    for keyword, field_name in _LABEL_TO_FIELD.items():
        if label_lower in keyword:
            if not _is_excluded(field_name):
                return field_name

    return None


def _normalize_period_key(period_key: str, ticker: str) -> str:
    """Normaliza un período a formato estándar: '{YYYY}-{Q}' o '{YYYY}-FY'.

    Ejemplos:
        "Q4 2025" → "2025-Q4"
        "FY 2025" → "2025-FY"
        "Dec 2025" → "2025-Q4"
        "4Q2025" → "2025-Q4"
    """
    text = period_key.strip()

    # Patrón: Q4 2025
    match = re.match(r'[QqTt](\d)\s*(\d{4})', text)
    if match:
        return f"{match.group(2)}-Q{match.group(1)}"

    # Patrón: 4Q 2025 o 4Q2025
    match = re.match(r'(\d)[QqTt]\s*(\d{4})', text)
    if match:
        return f"{match.group(2)}-Q{match.group(1)}"

    # Patrón: FY 2025
    match = re.match(r'FY\s*(\d{4})', text, re.IGNORECASE)
    if match:
        return f"{match.group(1)}-FY"

    # Patrón: Dec 2025 → Q4
    month_to_quarter = {
        "jan": "Q1", "feb": "Q1", "mar": "Q1",
        "apr": "Q2", "may": "Q2", "jun": "Q2",
        "jul": "Q3", "aug": "Q3", "sep": "Q3",
        "oct": "Q4", "nov": "Q4", "dec": "Q4",
        "ene": "Q1", "abr": "Q2", "ago": "Q3", "dic": "Q4",
    }
    match = re.match(r'(\w{3})\w*\s*(\d{4})', text, re.IGNORECASE)
    if match:
        month = match.group(1).lower()
        year = match.group(2)
        quarter = month_to_quarter.get(month, "Q4")
        return f"{year}-{quarter}"

    # Fallback: devolver como está
    return text


def _calculate_derived_fields(stmt: FinancialStatement, extra_mapped: dict[str, float] | None = None):
    """Calcula campos que pueden derivarse de otros.

    - gross_profit = revenue - cost_of_revenue
    - free_cash_flow = operating_cash_flow - capital_expenditure
    - total_debt = short_term_debt + long_term_debt (si componentes disponibles)
    - ebitda = ebit + depreciation_amortization (si EBITDA no viene directo)
    """
    extra = extra_mapped or {}

    if stmt.gross_profit == 0 and stmt.revenue > 0 and stmt.cost_of_revenue != 0:
        stmt.gross_profit = stmt.revenue + stmt.cost_of_revenue  # cost es negativo

    if stmt.free_cash_flow == 0 and stmt.operating_cash_flow != 0 and stmt.capital_expenditure != 0:
        stmt.free_cash_flow = stmt.operating_cash_flow + stmt.capital_expenditure  # capex es negativo

    # total_debt de componentes short/long-term
    if stmt.total_debt == 0:
        short_term = extra.get("short_term_debt", 0.0)
        long_term = extra.get("long_term_debt", 0.0)
        if short_term != 0 or long_term != 0:
            stmt.total_debt = abs(short_term) + abs(long_term)

    # EBITDA = EBIT + D&A (si no viene directo)
    if stmt.ebitda == 0 and stmt.ebit != 0:
        da = abs(extra.get("depreciation_amortization", 0.0))
        if da > 0:
            stmt.ebitda = stmt.ebit + da

    # EBITDA = Operating Income + D&A (alternativa)
    if stmt.ebitda == 0 and stmt.operating_income != 0:
        da = abs(extra.get("depreciation_amortization", 0.0))
        if da > 0:
            stmt.ebitda = stmt.operating_income + da

    # EBIT = EBITDA - D&A (si no viene directo ni operating_income)
    if stmt.ebit == 0 and stmt.ebitda != 0:
        da = abs(extra.get("depreciation_amortization", 0.0))
        if da > 0:
            stmt.ebit = stmt.ebitda - da
            logger.debug(
                f"  EBIT derivado: EBITDA({stmt.ebitda}) - D&A({da}) = {stmt.ebit}"
            )

    # EBIT = operating_income (si existe y EBIT no se mapeó directamente)
    if stmt.ebit == 0 and stmt.operating_income != 0:
        stmt.ebit = stmt.operating_income

    # operating_income = EBIT (si EBIT existe pero operating_income no)
    if stmt.operating_income == 0 and stmt.ebit != 0:
        stmt.operating_income = stmt.ebit

    # total_liabilities = current_liabilities + long_term_liabilities (aprox)
    if stmt.total_liabilities == 0 and stmt.current_liabilities != 0:
        long_term_liab = extra.get("long_term_liabilities", 0.0)
        if long_term_liab == 0:
            # Intentar calcular de total_debt components si hay
            long_term_liab = extra.get("long_term_debt", 0.0)
        if long_term_liab != 0:
            stmt.total_liabilities = abs(stmt.current_liabilities) + abs(long_term_liab)
        elif stmt.total_assets > 0 and stmt.total_equity > 0:
            # Ecuación contable: A = L + E → L = A - E
            stmt.total_liabilities = stmt.total_assets - stmt.total_equity
