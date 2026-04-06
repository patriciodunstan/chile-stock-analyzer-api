"""Endpoints de swing trading.

GET  /swing/monday-scan              → ranking de oportunidades para el lunes
GET  /swing/friday-review            → revisión de posiciones para el viernes
GET  /swing/{ticker}/indicators      → indicadores técnicos actuales
POST /swing/paper/open               → abrir trade simulado
POST /swing/paper/close/{trade_id}   → cerrar trade simulado
GET  /swing/paper/portfolio          → estado del portfolio paper
GET  /swing/paper/performance        → métricas de performance
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import (
    DBSession,
    StockRepo,
    MarketProvider,
)
from app.infrastructure.persistence.repositories.sqlalchemy_trade_repository import (
    SQLAlchemyTradeRepository,
)
from app.application.use_cases.swing.monday_scan import MondayScanUseCase
from app.application.use_cases.swing.friday_review import FridayReviewUseCase
from app.application.use_cases.swing.paper_trade import PaperTradeUseCase
from app.domain.services.technical_indicators import TechnicalIndicatorsService

router = APIRouter(prefix="/swing", tags=["swing"])

_INDICATORS = TechnicalIndicatorsService()


# ── Dependency helpers ────────────────────────────────────────

def get_trade_repository(db: DBSession) -> SQLAlchemyTradeRepository:
    return SQLAlchemyTradeRepository(db)


TradeRepo = Annotated[SQLAlchemyTradeRepository, Depends(get_trade_repository)]


# ── Request / Response models ─────────────────────────────────

class OpenTradeRequest(BaseModel):
    ticker: str
    strategy: str              # "monday_bounce" | "weekly_momentum" | "friday_dip"
    entry_price: float
    stop_loss: float
    take_profit: float
    capital: float | None = None   # CLP a invertir (default: 100.000)


class CloseTradeRequest(BaseModel):
    exit_price: float


# ── Endpoints ─────────────────────────────────────────────────

@router.get("/monday-scan")
async def monday_scan(
    stock_repo: StockRepo,
    market: MarketProvider,
    sector: str | None = None,
):
    """Escanea todas las empresas y retorna ranking de oportunidades para el lunes.

    Evalúa las 3 estrategias (Monday Bounce, Weekly Momentum, Friday Dip)
    sobre indicadores técnicos calculados con historial de precios.

    Parámetros:
        sector: Filtrar por sector (ej: "Minería", "Retail"). Opcional.
    """
    use_case = MondayScanUseCase(
        stock_repository=stock_repo,
        market_provider=market,
    )
    try:
        results = await use_case.execute(sector_filter=sector)
        return {
            "total_scanned": len(results),
            "opportunities": sum(1 for r in results if r.has_opportunity),
            "results": [r.to_dict() for r in results],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/friday-review")
async def friday_review(
    stock_repo: StockRepo,
    trade_repo: TradeRepo,
):
    """Revisa posiciones abiertas el viernes y recomienda HOLD o CLOSE.

    Analiza cada posición considerando:
    - P&L actual (realizado vs target)
    - Proximidad al stop loss
    - Riesgo de mantener el fin de semana
    """
    use_case = FridayReviewUseCase(
        trade_repository=trade_repo,
        stock_repository=stock_repo,
    )
    try:
        result = await use_case.execute()
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{ticker}/indicators")
async def get_indicators(
    ticker: str,
    stock_repo: StockRepo,
    limit: int = 60,
):
    """Retorna snapshot de indicadores técnicos para un ticker.

    Incluye: RSI, EMA9/21, MACD, Bollinger Bands, ATR, volumen relativo.
    Requiere al menos 30 precios históricos.
    """
    prices = await stock_repo.get_price_history(ticker.upper(), limit=limit)
    if len(prices) < 26:
        raise HTTPException(
            status_code=422,
            detail=f"Datos insuficientes: {len(prices)} precios (mínimo 26). "
                   "Ejecuta GET /stocks/{ticker}/price para registrar precios.",
        )

    closes = [p.close_price or p.price for p in prices]
    highs = [p.high or p.price for p in prices]
    lows = [p.low or p.price for p in prices]
    volumes = [p.volume or 0 for p in prices]

    snap = _INDICATORS.snapshot(
        ticker=ticker.upper(),
        closes=closes,
        highs=highs,
        lows=lows,
        volumes=volumes,
    )
    if snap is None:
        raise HTTPException(status_code=422, detail="No se pudieron calcular indicadores")

    return {
        "ticker": snap.ticker,
        "last_price": snap.last_price,
        "rsi": snap.rsi,
        "rsi_signal": snap.rsi_signal,
        "ema9": snap.ema9,
        "ema21": snap.ema21,
        "ema_cross": snap.ema_cross,
        "macd_line": snap.macd_line,
        "macd_signal": snap.macd_signal,
        "macd_histogram": snap.macd_histogram,
        "macd_trend": snap.macd_trend,
        "bb_upper": snap.bb_upper,
        "bb_middle": snap.bb_middle,
        "bb_lower": snap.bb_lower,
        "bb_position": snap.bb_position,
        "bb_pct": snap.bb_pct,
        "atr": snap.atr,
        "atr_stop_loss": snap.atr_stop_loss,
        "volume_avg10": snap.volume_avg10,
        "volume_ratio": snap.volume_ratio,
        "prices_used": len(closes),
    }


@router.post("/paper/open")
async def open_paper_trade(
    body: OpenTradeRequest,
    trade_repo: TradeRepo,
):
    """Abre un trade simulado con el capital virtual del portfolio.

    Máximo 1 posición abierta simultánea (restricción de capital).
    Capital por defecto: 100.000 CLP (50% del portfolio).
    """
    use_case = PaperTradeUseCase(trade_repository=trade_repo)
    try:
        trade = await use_case.open_trade(
            ticker=body.ticker,
            strategy=body.strategy,
            entry_price=body.entry_price,
            stop_loss=body.stop_loss,
            take_profit=body.take_profit,
            capital=body.capital,
        )
        return trade.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/paper/close/{trade_id}")
async def close_paper_trade(
    trade_id: str,
    body: CloseTradeRequest,
    trade_repo: TradeRepo,
):
    """Cierra un trade simulado al precio indicado, calculando P&L neto."""
    use_case = PaperTradeUseCase(trade_repository=trade_repo)
    try:
        trade = await use_case.close_trade(trade_id, body.exit_price)
        return trade.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/paper/portfolio")
async def get_portfolio(
    trade_repo: TradeRepo,
    stock_repo: StockRepo,
):
    """Retorna estado actual del portfolio paper con P&L no realizado.

    Obtiene precios actuales del historial para calcular P&L en tiempo real.
    """
    use_case = PaperTradeUseCase(trade_repository=trade_repo)
    open_trades_raw = await trade_repo.get_open_trades(is_paper=True)

    # Obtener precios actuales para calcular P&L no realizado
    current_prices: dict[str, float] = {}
    for trade in open_trades_raw:
        prices = await stock_repo.get_price_history(trade.ticker, limit=1)
        if prices:
            current_prices[trade.ticker] = prices[-1].price

    portfolio = await use_case.get_portfolio(current_prices)
    return portfolio.to_dict()


@router.get("/paper/performance")
async def get_performance(trade_repo: TradeRepo):
    """Retorna métricas de performance del paper trading.

    Incluye: win rate, profit factor, P&L total, max drawdown,
    mejor y peor trade.
    """
    use_case = PaperTradeUseCase(trade_repository=trade_repo)
    perf = await use_case.get_performance()
    return perf.to_dict()


@router.post("/paper/check-prices")
async def check_prices(trade_repo: TradeRepo):
    """Obtiene precios reales (yfinance) y auto-ejecuta SL/TP de posiciones abiertas.

    Llama a yfinance para cada ticker con posición abierta y cierra
    automáticamente los trades que cruzaron stop loss o take profit.

    Respuesta:
    - executed: trades cerrados en esta llamada (trigger: STOP_LOSS | TAKE_PROFIT)
    - still_open: trades que siguen abiertos con P&L actual y distancia a SL/TP
    - prices_fetched: precios obtenidos de yfinance
    """
    use_case = PaperTradeUseCase(trade_repository=trade_repo)
    try:
        result = await use_case.check_and_execute_prices()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-prices")
async def refresh_prices(stock_repo: StockRepo):
    """Actualiza precios del día desde yfinance para los 10 tickers del registry.

    Llamado por el scheduler del bot de Telegram a las 18:30 CLT (lunes-viernes).
    """
    import asyncio
    from datetime import datetime, timezone
    import yfinance as yf
    from app.domain.entities.company import COMPANY_REGISTRY
    from app.domain.entities.stock import StockPrice

    companies = list(COMPANY_REGISTRY.values())
    ok: list[str] = []
    failed: list[str] = []

    async def _fetch_and_save(company) -> None:
        yf_ticker = company.yahoo_ticker or f"{company.ticker}.SN"
        try:
            def _get():
                ticker_obj = yf.Ticker(yf_ticker)
                hist = ticker_obj.history(period="2d")
                if hist.empty:
                    return None
                row = hist.iloc[-1]
                return {
                    "close": float(row["Close"]),
                    "open": float(row.get("Open") or 0),
                    "high": float(row.get("High") or 0),
                    "low": float(row.get("Low") or 0),
                    "volume": int(row.get("Volume") or 0),
                }

            data = await asyncio.to_thread(_get)
            if not data or data["close"] <= 0:
                failed.append(company.ticker)
                return

            price = StockPrice(
                ticker=company.ticker,
                price=data["close"],
                open_price=data["open"],
                high=data["high"],
                low=data["low"],
                close_price=data["close"],
                volume=data["volume"],
                timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            )
            await stock_repo.save_price(price)
            ok.append(company.ticker)
        except Exception:
            failed.append(company.ticker)

    await asyncio.gather(*[_fetch_and_save(c) for c in companies])

    return {
        "updated": len(ok),
        "failed": len(failed),
        "tickers_ok": ok,
        "tickers_failed": failed,
    }
