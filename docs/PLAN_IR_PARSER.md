# Plan: IR Financial Report Parser

## Contexto

Los resultados del diagnóstico (2026-03-23) confirman que Yahoo Finance cubre 14/15 tickers con ~97% de métricas fundamentales. Sin embargo, para análisis de value investing profesional necesitamos acceso a los estados financieros completos (EEFF) directamente desde las empresas — no solo las métricas resumen de Yahoo.

Las páginas de Investor Relations de empresas chilenas ofrecen:
- **PDFs**: Financial Statements, Earnings Release, Presentaciones
- **XLSX**: Earnings Release Tables (SQM confirmado, otros por verificar)
- **Periodicidad**: Trimestral + Anual

## Objetivo

Construir un sistema automatizado que:
1. Descubra y descargue reportes financieros desde páginas IR
2. Extraiga datos tabulares (EEFF) de PDFs y XLSX
3. Normalice los datos a un formato común (FinancialStatement entity)
4. Persista para análisis posterior y cross-validation con Yahoo Finance

## Arquitectura

```
┌──────────────────────────────────────────────────┐
│                  IR Parser System                  │
├──────────────────────────────────────────────────┤
│                                                    │
│  application/interfaces/                           │
│    financial_report_provider.py  ← ABC interface   │
│                                                    │
│  infrastructure/external/ir_reports/               │
│    base_scraper.py      ← Abstract IR scraper      │
│    sqm_scraper.py       ← SQM-specific impl       │
│    falabella_scraper.py ← Falabella-specific impl  │
│    cap_scraper.py       ← CAP-specific impl        │
│    bci_scraper.py       ← BCI-specific impl        │
│    cencosud_scraper.py  ← Cencosud-specific impl   │
│    registry.py          ← Factory/registry          │
│                                                    │
│  infrastructure/parsers/                            │
│    pdf_financial_parser.py  ← pdfplumber tables    │
│    xlsx_financial_parser.py ← openpyxl/pandas      │
│    normalizer.py            ← Raw → Entity map     │
│                                                    │
│  application/use_cases/reports/                     │
│    fetch_financial_report.py   ← Orchestrator      │
│    parse_financial_report.py   ← Parse + normalize │
│                                                    │
│  presentation/api/v1/endpoints/                     │
│    reports.py  ← GET /reports/{ticker}             │
│                                                    │
└──────────────────────────────────────────────────┘
```

## Hallazgos de Investigación IR

### SQM (ir.sqm.com)
- **URL Quarterly:** `ir.sqm.com/financials/quarterly-results`
- **Formatos:** PDF (Financial Statement, Earnings Release, Presentation) + **XLSX** (Earnings Release Tables)
- **Patrón URL XLSX:** `/system/files-encrypted/nasdaq_kms/assets/{YYYY}/{MM}/{DD}/Tables_{Q}Q{YYYY}_eng.xlsx`
- **Patrón URL PDF:** `/static-files/{uuid}` (no predecible)
- **Plataforma:** Q4Web/Nasdaq IR (estructura estándar)
- **Histórico:** Disponible desde 2022+

### Falabella (investors.grupofalabella.com)
- **URL:** `investors.grupofalabella.com/inversionistas/informacion-financiera/`
- **Sección:** "Estados Financieros" con link "ver todos"
- **Formatos:** PDFs descargables
- **Plataforma:** WordPress custom

### CAP (investor.cap.cl)
- **URL:** `investor.cap.cl/en/`
- **Pendiente:** Estructura exacta por confirmar

### BCI (bci.cl/investor-relations)
- **URL:** `bci.cl/investor-relations`
- **Nota:** También disponible via CMF API v3 (datos bancarios estructurados)

### Cencosud (cencosud.com/inversionistas)
- **URL:** `cencosud.com/en/inversionistas`
- **Pendiente:** Estructura exacta por confirmar

## Historias de Usuario

### HU-IR-001: Scraper de reportes SQM (MVP)

**Como** analista de inversiones
**Quiero** que el sistema descargue automáticamente los XLSX de earnings release de SQM
**Para** tener datos financieros tabulares listos para análisis sin intervención manual

**Criterios de Aceptación:**
- [ ] Scraper navega ir.sqm.com y descubre links a XLSX de earnings release
- [ ] Descarga XLSX del último trimestre disponible
- [ ] Soporta descarga de histórico (últimos 8 trimestres)
- [ ] Almacena archivos en `data/reports/sqm/` con naming consistente
- [ ] Logging de cada paso (descubrimiento, descarga, verificación)
- [ ] Manejo de errores (404, timeout, formato inesperado)

**Tareas Técnicas:**
- [ ] Crear `base_scraper.py` (ABC con métodos discover/download)
- [ ] Implementar `sqm_scraper.py` (httpx + parsing de HTML)
- [ ] Tests unitarios con HTML mockeado
- [ ] Test de integración con URL real

**Estimación:** M

### HU-IR-002: Parser de XLSX financiero

**Como** analista de inversiones
**Quiero** que el sistema extraiga datos del XLSX de earnings de SQM
**Para** tener income statement, balance sheet y cash flow estructurados

**Criterios de Aceptación:**
- [ ] Lee XLSX y detecta sheets de Income Statement, Balance Sheet, Cash Flow
- [ ] Extrae todos los valores numéricos con sus labels
- [ ] Maneja moneda (USD millions para SQM)
- [ ] Output: dict con estructura {periodo: {metrica: valor}}
- [ ] Maneja múltiples períodos por archivo (comparativos)

**Tareas Técnicas:**
- [ ] Crear `xlsx_financial_parser.py` usando openpyxl/pandas
- [ ] Mapping de labels comunes a campos normalizados
- [ ] Tests con XLSX real de SQM

**Estimación:** M

### HU-IR-003: Parser de PDF financiero

**Como** analista de inversiones
**Quiero** que el sistema extraiga tablas financieras de PDFs de earnings release
**Para** cubrir empresas que no proveen XLSX (Falabella, CAP, etc.)

**Criterios de Aceptación:**
- [ ] Lee PDF con pdfplumber
- [ ] Detecta tablas con datos financieros
- [ ] Extrae Income Statement, Balance Sheet, Cash Flow
- [ ] Maneja tablas que cruzan múltiples páginas
- [ ] Accuracy >90% vs datos manuales
- [ ] Fallback: si la tabla no se puede parsear, marca como "manual_review"

**Tareas Técnicas:**
- [ ] Crear `pdf_financial_parser.py` usando pdfplumber
- [ ] Heurísticas para detectar tablas EEFF vs otras tablas
- [ ] Normalización de números (miles, millones, paréntesis=negativo)
- [ ] Tests con PDFs reales de SQM y Falabella

**Estimación:** L

### HU-IR-004: Normalización a entidades de dominio

**Como** desarrollador del sistema
**Quiero** que los datos extraídos de XLSX/PDF se mapeen a la entidad FinancialStatement
**Para** tener una fuente de datos unificada independiente del formato de origen

**Criterios de Aceptación:**
- [ ] Mapper de campos extraídos a campos de FinancialStatement
- [ ] Manejo de monedas (CLP, USD, UF) con conversión
- [ ] Detección de período (Q1, Q2, Q3, Q4, Annual)
- [ ] Validación de consistencia (assets = liabilities + equity)
- [ ] Persistencia via FinancialRepository

**Tareas Técnicas:**
- [ ] Crear `normalizer.py` con field mapping configurable
- [ ] Extender `FinancialStatement` entity si faltan campos
- [ ] Crear use case `parse_financial_report.py`
- [ ] Tests de normalización

**Estimación:** M

### HU-IR-005: Scrapers para otras empresas

**Como** analista de inversiones
**Quiero** que el sistema soporte las 5 empresas prioritarias
**Para** tener cobertura completa de reportes financieros

**Criterios de Aceptación:**
- [ ] Scraper Falabella (investors.grupofalabella.com)
- [ ] Scraper CAP (investor.cap.cl)
- [ ] Scraper BCI (bci.cl/investor-relations)
- [ ] Scraper Cencosud (cencosud.com/inversionistas)
- [ ] Registry que mapea ticker → scraper correcto

**Tareas Técnicas:**
- [ ] Implementar scrapers específicos
- [ ] `registry.py` con factory pattern
- [ ] Tests por empresa

**Estimación:** L

### HU-IR-006: Endpoint API para reportes

**Como** usuario del dashboard
**Quiero** consultar reportes financieros via API
**Para** ver los EEFF extraídos de cada empresa

**Criterios de Aceptación:**
- [ ] GET /api/v1/reports/{ticker}/latest — último reporte
- [ ] GET /api/v1/reports/{ticker}/history — histórico
- [ ] GET /api/v1/reports/{ticker}/download — trigger descarga
- [ ] Response incluye source (xlsx/pdf), período, datos normalizados
- [ ] Cross-validation flag vs Yahoo Finance

**Tareas Técnicas:**
- [ ] Crear router `reports.py`
- [ ] Schemas Pydantic para response
- [ ] Use case `fetch_financial_report.py`

**Estimación:** M

## Fases de Implementación

### Fase 1 — MVP SQM (HU-IR-001 + HU-IR-002)
- Scraper SQM + Parser XLSX
- Validar que extraemos datos correctos
- ~3-4 horas de desarrollo

### Fase 2 — PDF Parser (HU-IR-003)
- Parser genérico de PDF para earnings
- Testear con Falabella y CAP
- ~4-5 horas de desarrollo

### Fase 3 — Normalización + API (HU-IR-004 + HU-IR-006)
- Mapping a entidades de dominio
- Endpoints REST
- ~3 horas de desarrollo

### Fase 4 — Expansión (HU-IR-005)
- Scrapers para las 4 empresas restantes
- ~4 horas de desarrollo

## Dependencias

- `pdfplumber` — extracción de tablas PDF
- `openpyxl` — lectura de XLSX
- `httpx` — HTTP client async (ya en proyecto)
- `beautifulsoup4` — parsing HTML de páginas IR
