# Swing Trading — Chile Stock Analyzer

Módulo de swing trading sobre acciones del IPSA chileno, diseñado para operar
con capital reducido en días específicos de la semana.

---

## Contexto y restricciones

| Parámetro | Valor |
|-----------|-------|
| Capital inicial | 200.000 CLP |
| Días disponibles para operar activamente | Lunes y viernes (home office) |
| Horizonte de validación | 2 meses |
| Max posición simultánea | 1 (50% del capital) |
| Reserva mínima | 100.000 CLP (50%) |

### Por qué lunes y viernes

**Lunes:**
- Las noticias del fin de semana están "priced in" al abrir
- Stocks oversold del viernes frecuentemente rebotan (gap fade)
- Momento óptimo para escanear entradas

**Viernes:**
- Institucionales cierran posiciones → mayor volumen y volatilidad
- Última oportunidad para tomar ganancia o cortar pérdida antes del fin de semana
- Entrada táctica en stocks que bajan sin noticia negativa (Friday Dip)

---

## Estrategias implementadas

### Estrategia 1 — Monday Bounce (principal)

Aprovecha stocks sobrevendidos del viernes que rebotan el lunes.

**Condiciones de entrada (lunes mañana):**
- RSI(14) < 35 → oversold
- Precio en o cerca de banda inferior Bollinger (dentro del 2%)
- Cayó >3% la semana anterior o el viernes

**Gestión:**
- Stop loss: -5% del precio de entrada
- Take profit: +10%
- Ratio riesgo/beneficio: 1:2
- Horizon: hasta el viernes siguiente (máx 5 días)

**Señal de salida anticipada:**
- RSI > 65 → salir aunque no llegue al target
- Precio toca banda superior Bollinger → salir

---

### Estrategia 2 — Weekly Momentum

Captura tendencias de corto plazo con confirmación técnica.

**Condiciones de entrada (lunes):**
- EMA9 cruzó EMA21 hacia arriba en los últimos 3 días
- MACD histograma positivo y creciendo (momentum confirmado)
- Volumen lunes > promedio 10 días (confirmación de fuerza)

**Gestión:**
- Stop loss: -4% (más ajustado porque hay confirmación de tendencia)
- Take profit: +10%
- Horizon: hasta el viernes siguiente

---

### Estrategia 3 — Friday Dip

Entrada táctica en stocks que bajan sin razón fundamental el viernes.

**Condiciones de entrada (viernes 4-5 PM):**
- Cayó >2% en el día sin noticia negativa
- RSI < 40
- Precio cerca de soporte técnico (EMA21 o mínimo semanal)

**Gestión:**
- Stop loss: -4% (activo el fin de semana)
- Take profit: +6% (target conservador para el lunes siguiente)
- Horizon: vender lunes al abrir o martes máximo

---

## Gestión de riesgo con 200.000 CLP

```
Capital total:         200.000 CLP
Max por posición:      100.000 CLP  → max 1 posición simultánea
Reserva permanente:    100.000 CLP
Stop loss por trade:   5% → pérdida máxima: 5.000 CLP
Take profit por trade: 10% → ganancia objetivo: 10.000 CLP
Ratio R/R mínimo:      1:2

Breakeven matemático:
  Con ratio 1:2, necesitas win rate > 33% para ser rentable
  Target realista: win rate 45-55% → rentabilidad ~5-10% mensual
```

### Comisiones a considerar
| Corredora | Comisión estimada por trade |
|-----------|----------------------------|
| Renta 4   | ~0.5% |
| Banchile  | ~0.5-0.8% |
| Fintual   | Variable |

Con 100.000 CLP por posición → ~500 CLP por trade (entrada + salida = ~1.000 CLP por ciclo)

---

## Stocks recomendados para swing

| Ticker | Sector | Por qué sirve para swing |
|--------|--------|--------------------------|
| BSANTANDER | Banca | Alta liquidez, spread bajo, sigue mercado |
| COPEC | Holding | Tendencias claras, buen volumen |
| FALABELLA | Retail | Muy líquido, correlaciona con consumo |
| BCI | Banca | Movimientos suaves, predecible |
| SQM-B | Minería | Volátil (litio) — alto potencial, alto riesgo |

**Evitar con capital pequeño:** ENELCHILE, COLBUN (baja liquidez, spreads altos).

---

## Indicadores técnicos implementados

### RSI — Relative Strength Index
- Período: 14
- Señal de compra: RSI < 35
- Señal de venta: RSI > 65
- Fórmula: `RSI = 100 - (100 / (1 + RS))` donde `RS = avg_gain / avg_loss`

### EMA — Exponential Moving Average
- Períodos usados: EMA9, EMA21
- Cruce EMA9 > EMA21 → tendencia alcista
- Cruce EMA9 < EMA21 → tendencia bajista

### MACD — Moving Average Convergence Divergence
- Configuración: Fast=12, Slow=26, Signal=9
- MACD Line = EMA12 - EMA26
- Signal Line = EMA9 de MACD Line
- Histograma = MACD Line - Signal Line
- Señal alcista: Histograma positivo y creciendo

### Bollinger Bands
- Período: 20, Desviación estándar: 2
- Upper Band = SMA20 + 2σ
- Lower Band = SMA20 - 2σ
- Precio cerca de Lower Band → oversold, posible rebote

---

## Arquitectura del módulo

```
app/
  domain/
    entities/
      trade.py                    → Trade, TradeStatus, TradeStrategy
    services/
      technical_indicators.py     → RSI, EMA, MACD, BollingerBands (puro, sin IO)
      swing_signal_service.py     → evalúa las 3 estrategias, retorna SwingSignal

  application/
    use_cases/
      swing/
        monday_scan.py            → escanea todas las empresas, rankea oportunidades lunes
        friday_review.py          → revisa posiciones abiertas, recomienda acción viernes
        paper_trade.py            → abre/cierra trades simulados, calcula P&L

  infrastructure/
    persistence/
      models/trade_model.py       → SQLAlchemy ORM model
      repositories/
        sqlalchemy_trade_repository.py

  presentation/
    api/v1/endpoints/
      swing.py                    → endpoints REST del módulo swing
```

---

## Endpoints del módulo

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/api/v1/swing/monday-scan` | Ranking de oportunidades para el lunes |
| GET | `/api/v1/swing/friday-review` | Estado de posiciones + recomendación cierre |
| GET | `/api/v1/swing/{ticker}/indicators` | Indicadores técnicos actuales de un ticker |
| POST | `/api/v1/swing/paper/open` | Abrir trade simulado |
| POST | `/api/v1/swing/paper/close/{trade_id}` | Cerrar trade simulado |
| GET | `/api/v1/swing/paper/portfolio` | Posiciones abiertas del portfolio paper |
| GET | `/api/v1/swing/paper/performance` | Win rate, P&L total, drawdown |

---

## Flujo de uso semanal

```
LUNES (mañana, antes de las 10 AM):
  1. GET /swing/monday-scan         → ver oportunidades rankeadas
  2. Revisar top 3 oportunidades
  3. POST /swing/paper/open          → abrir trade con la mejor señal
  4. El sistema registra entry_price, stop_loss (-5%), take_profit (+10%)

MARTES a JUEVES (monitoring pasivo):
  - Stop loss y take profit quedan registrados
  - Sistema monitorea y marca trade como STOPPED o PROFIT si se llega al nivel

VIERNES (tarde, 3-5 PM):
  1. GET /swing/paper/portfolio       → ver estado de posiciones abiertas
  2. GET /swing/friday-review         → recomendación: HOLD o CLOSE
  3. Si señal = CLOSE → POST /swing/paper/close/{id}
  4. GET /swing/paper/performance     → revisar métricas acumuladas
```

---

## Paper trading — reglas de simulación

- Capital inicial virtual: 200.000 CLP
- Máximo 1 posición abierta simultánea
- Comisión simulada: 0.5% por operación (entrada + salida)
- Stop loss se ejecuta automáticamente al precio configurado
- Take profit se ejecuta automáticamente al precio configurado
- P&L se calcula en CLP y porcentaje

### Métricas de performance
| Métrica | Descripción | Target |
|---------|-------------|--------|
| Win Rate | % de trades ganadores | >45% |
| Profit Factor | ganancias totales / pérdidas totales | >1.5 |
| Max Drawdown | mayor caída desde peak del portfolio | <15% |
| Avg Win | ganancia promedio por trade ganador | >8% |
| Avg Loss | pérdida promedio por trade perdedor | <5% |

---

## Historial de cambios

| Fecha | Versión | Cambio |
|-------|---------|--------|
| 2026-04-05 | v1.0 | Implementación inicial: indicadores, señales, paper trading |
