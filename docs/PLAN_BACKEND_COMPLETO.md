# Plan: Backend Funcional — Chile Stock Analyzer

## Contexto

Sistema de análisis fundamental de acciones chilenas (value investing).
Objetivo: determinar si una acción está subvalorada (valor intrínseco > precio de mercado).

### Estado Actual

| Componente | Estado | Detalle |
|---|---|---|
| Domain entities | ✅ Completo | FinancialStatement, FundamentalMetrics, Stock, StockPrice |
| MetricsCalculatorService | ✅ Completo | 22 métricas fundamentales, 29 tests |
| SQM Scraper + XLSX Parser | ✅ Completo | IS, BS, EBITDA. Cash Flow no disponible en XLSX |
| Normalizer | ✅ Completo | Exclusion patterns, source priority, campos derivados |
| SQLAlchemy Models | ✅ Completo | FinancialStatementModel, FundamentalMetricsModel, StockModel |
| API Endpoints | ✅ Estructura | 8 endpoints definidos, no probados end-to-end |
| Yahoo Finance Client | ✅ Código | Implementado, requiere internet para funcionar |
| Composite Provider | ✅ Código | Cascada Bolsa→Yahoo→EODHD |
| **Ingesta datos → DB** | ❌ Falta | No hay pipeline scraper→parser→normalizer→DB |
| **API levantando** | ❌ No probado | Nunca se ejecutó `uvicorn app.main:app` |
| **DCF Valuation** | ❌ Falta | Motor de valoración intrínseca |
| **Opportunity Scoring** | ❌ Falta | Señal buy/hold/sell con puntaje |
| **Scrapers otras empresas** | ❌ Falta | Solo SQM implementado |

### Gap Crítico

No hay forma de: (1) ingestar datos financieros al DB, (2) combinarlos con precio de mercado, (3) obtener una señal de compra/venta.

---

## Objetivo

Backend funcional que responda: **"¿Debo comprar esta acción?"** con datos cuantitativos.

Endpoint target:
```
GET /api/v1/analysis/{ticker}/signal
→ {
    ticker: "SQM-B",
    signal: "BUY",           // BUY | HOLD | SELL
    score: 78,               // 0-100
    intrinsic_value: 52400,  // CLP
    market_price: 41200,     // CLP
    margin_of_safety: 27.1,  // %
    metrics: { pe: 8.2, pb: 1.1, roe: 15.3, ... },
    reasons: ["P/E bajo vs sector", "Margen de seguridad >25%", ...]
  }
```

---

## Historias de Usuario

### FASE 1: API Funcional + Ingesta de Datos

#### HU-BE-001: Levantar API con DB

**Como** desarrollador
**Quiero** que la API FastAPI arranque correctamente con SQLite
**Para** tener una base funcional sobre la cual construir

**Criterios de Aceptación:**
- [ ] `uvicorn app.main:app` arranca sin errores
- [ ] GET /api/v1/health retorna 200
- [ ] Tablas se crean automáticamente al arrancar (init_db)
- [ ] Dependencias instaladas y resueltas

**Tareas Técnicas:**
- [ ] Instalar dependencias faltantes (aiosqlite para SQLite async)
- [ ] Verificar imports y resolver errores de arranque
- [ ] Probar endpoint health
- [ ] Fix issues de compatibilidad si los hay

**Estimación:** S

---

#### HU-BE-002: Pipeline de Ingesta de Datos Financieros

**Como** sistema
**Quiero** un endpoint/CLI que ejecute: scraper → parser → normalizer → DB
**Para** poblar la base de datos con estados financieros reales

**Criterios de Aceptación:**
- [ ] Endpoint POST /api/v1/financials/{ticker}/ingest que descarga y procesa reportes
- [ ] CLI alternativo: `python -m app.cli ingest SQM-B`
- [ ] Los FinancialStatements se persisten en DB con upsert
- [ ] Logs claros del progreso y errores
- [ ] Funciona con datos locales (XLSX ya descargados) como fallback

**Tareas Técnicas:**
- [ ] Crear IngestFinancialsUseCase que orqueste scraper+parser+normalizer+repo
- [ ] Endpoint POST en financials.py
- [ ] CLI entry point básico
- [ ] Test de integración con XLSX local de SQM

**Estimación:** M

---

#### HU-BE-003: Ingesta desde XLSX Local (sin internet)

**Como** usuario
**Quiero** poder ingestar datos desde archivos XLSX que ya tengo
**Para** no depender de internet para poblar datos

**Criterios de Aceptación:**
- [ ] Endpoint POST /api/v1/financials/{ticker}/ingest-file que acepta upload XLSX
- [ ] También acepta path local a archivo existente
- [ ] Retorna resumen: períodos procesados, campos mapeados, warnings

**Tareas Técnicas:**
- [ ] Endpoint con UploadFile de FastAPI
- [ ] Reutilizar XLSXParser + Normalizer existentes
- [ ] Persistir en DB

**Estimación:** S

---

### FASE 2: Market Data (Precios Tiempo Real)

#### HU-BE-004: Obtener Precios de Mercado

**Como** sistema
**Quiero** obtener el precio actual de acciones chilenas desde Yahoo Finance
**Para** calcular ratios de valorización (P/E, P/B, EV/EBITDA)

**Criterios de Aceptación:**
- [ ] GET /api/v1/stocks/{ticker}/price retorna precio real
- [ ] Fallback en cascada funciona (Bolsa→Yahoo→EODHD)
- [ ] Precio se persiste en stock_prices para historial
- [ ] Market cap disponible para cálculos

**Tareas Técnicas:**
- [ ] Verificar que YahooFinanceClient funciona con acciones .SN
- [ ] Ajustar BolsaSantiagoClient si la API cambió
- [ ] Test de integración con datos reales
- [ ] Cache de precios (no consultar más de 1 vez por minuto)

**Estimación:** M

---

#### HU-BE-005: Precio Tiempo Real con WebSocket (v2)

**Como** usuario del dashboard
**Quiero** ver precios actualizados en tiempo real
**Para** tomar decisiones con datos frescos

**Criterios de Aceptación:**
- [ ] WebSocket endpoint ws://host/api/v1/stocks/live
- [ ] Push de precios cada 30-60 segundos durante horario bursátil
- [ ] Fallback a polling si WebSocket no disponible

**Tareas Técnicas:**
- [ ] FastAPI WebSocket endpoint
- [ ] Background task con APScheduler para polling periódico
- [ ] Broadcast a conexiones activas

**Estimación:** L (diferir a v2)

---

### FASE 3: Motor de Valoración + Señal Buy/Sell

#### HU-BE-006: Servicio DCF (Discounted Cash Flow)

**Como** sistema de análisis
**Quiero** calcular el valor intrínseco de una acción usando DCF
**Para** comparar con precio de mercado y determinar si está subvalorada

**Criterios de Aceptación:**
- [ ] Proyecta FCF a 5 años basado en históricos + growth rate
- [ ] Calcula WACC (costo promedio ponderado de capital)
- [ ] Calcula valor terminal con perpetuity growth model
- [ ] Retorna rango: [valor_conservador, valor_base, valor_optimista]
- [ ] Funciona sin Cash Flow (usa EBITDA - CapEx estimado como proxy)

**Tareas Técnicas:**
- [ ] DCFValuationService en domain/services/
- [ ] Tests unitarios con escenarios conocidos
- [ ] Parámetros configurables (growth rate, WACC, terminal growth)
- [ ] Manejo de edge cases (datos insuficientes, empresas con pérdidas)

**Estimación:** L

---

#### HU-BE-007: Opportunity Scoring (Señal Buy/Hold/Sell)

**Como** inversionista
**Quiero** un puntaje de 0-100 y señal clara (BUY/HOLD/SELL)
**Para** saber rápidamente si una acción es oportunidad de compra

**Criterios de Aceptación:**
- [ ] Score compuesto basado en: margen de seguridad, calidad (ROE, márgenes), riesgo (deuda), momentum
- [ ] Señal: BUY (score ≥ 70), HOLD (40-69), SELL (<40)
- [ ] Lista de razones en lenguaje claro ("P/E de 8.2 está por debajo del promedio sectorial")
- [ ] Endpoint GET /api/v1/analysis/{ticker}/signal

**Tareas Técnicas:**
- [ ] OpportunityScoringService en domain/services/
- [ ] Pesos configurables para cada factor del score
- [ ] Comparación vs promedios sectoriales (baseline)
- [ ] Tests con escenarios: empresa barata, empresa cara, empresa en pérdidas

**Estimación:** M

---

#### HU-BE-008: Endpoint de Análisis Completo

**Como** dashboard frontend
**Quiero** un endpoint que retorne todo el análisis de una acción
**Para** renderizar la vista de decisión en una sola llamada

**Criterios de Aceptación:**
- [ ] GET /api/v1/analysis/{ticker} retorna: precio, métricas, valoración DCF, score, señal, historial
- [ ] Calcula todo on-demand o usa cache si datos son recientes (<1h)
- [ ] Incluye comparación con períodos anteriores (tendencia)

**Tareas Técnicas:**
- [ ] FullAnalysisUseCase que orqueste todos los servicios
- [ ] Response schema consolidado
- [ ] Cache layer con TTL configurable

**Estimación:** M

---

### FASE 4: Escalar a Más Empresas

#### HU-BE-009: Scrapers Multi-Empresa

**Como** sistema
**Quiero** ingestar datos de CAP, BCI, Falabella, Cencosud
**Para** tener datos comparativos y diversificar el análisis

**Criterios de Aceptación:**
- [ ] Scraper para cada empresa que descubra reportes XLSX/PDF
- [ ] Parser adaptado o genérico que maneje variaciones de formato
- [ ] Normalizer funciona con labels de cada empresa
- [ ] Al menos IS + BS para cada empresa

**Tareas Técnicas:**
- [ ] Investigar formato IR de cada empresa
- [ ] Implementar scrapers (extender BaseScraper)
- [ ] Adaptar parser/normalizer si formatos son muy distintos
- [ ] Tests por empresa

**Estimación:** XL

---

#### HU-BE-010: Dashboard Comparativo

**Como** inversionista
**Quiero** comparar métricas de múltiples empresas lado a lado
**Para** elegir la mejor oportunidad entre varias opciones

**Criterios de Aceptación:**
- [ ] GET /api/v1/analysis/compare?tickers=SQM-B,CAP,FALABELLA
- [ ] Retorna métricas de cada empresa + ranking por score
- [ ] Identifica la mejor oportunidad del grupo

**Estimación:** M

---

## Arquitectura Propuesta

```
┌─────────────────────────────────────────────────────┐
│                   Presentation                       │
│  FastAPI endpoints + WebSocket (precios live)        │
├─────────────────────────────────────────────────────┤
│                   Application                        │
│  Use Cases: Ingest, CalculateMetrics, DCF, Scoring  │
├─────────────────────────────────────────────────────┤
│                     Domain                           │
│  Entities + Services (MetricsCalc, DCF, Scoring)     │
├─────────────────────────────────────────────────────┤
│                  Infrastructure                      │
│  Yahoo/Bolsa (precios) | Scrapers (EEFF) | SQLite   │
└─────────────────────────────────────────────────────┘
```

---

## Fases de Implementación

| Fase | HUs | Entregable | Prioridad |
|------|-----|-----------|-----------|
| **1** | BE-001, BE-002, BE-003 | API arranca, datos financieros en DB | **CRÍTICA** |
| **2** | BE-004 | Precios de mercado funcionando | **ALTA** |
| **3** | BE-006, BE-007, BE-008 | Señal buy/sell funcional | **ALTA** |
| **4** | BE-009, BE-010 | Multi-empresa + comparativo | MEDIA |
| **v2** | BE-005 | WebSocket tiempo real | BAJA |

**MVP funcional = Fases 1-3** → Backend que dice "compra SQM-B porque..."
