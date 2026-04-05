"""Bot de Telegram para swing trading — Chile Stock Analyzer.

Comandos:
  /scan              → Monday scan (top 5 oportunidades)
  /open TICKER       → Abrir trade paper con la mejor señal del ticker
  /close             → Cerrar posición abierta al precio actual (yfinance)
  /check             → Verificar precios reales y auto-ejecutar SL/TP
  /portfolio         → Ver posiciones abiertas con P&L actual
  /review            → Friday review (recomendación HOLD/CLOSE)
  /indicators TICKER → Indicadores técnicos de un ticker
  /perf              → Performance acumulada (win rate, P&L, etc.)
  /help              → Lista de comandos
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

import telegram_bot.api_client as api
from telegram_bot.config import TELEGRAM_BOT_TOKEN
from telegram_bot.formatters import (
    fmt_check,
    fmt_indicators,
    fmt_performance,
    fmt_portfolio,
    fmt_review,
    fmt_scan,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────

async def _reply(update: Update, text: str) -> None:
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def _reply_error(update: Update, error: Exception) -> None:
    await _reply(update, f"❌ Error: {error}")


# ── Comandos ──────────────────────────────────────────────────

async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, (
        "🤖 *Chile Swing Bot*\n\n"
        "/scan — Monday scan: top oportunidades\n"
        "/open TICKER — Abrir trade (ej: /open FALABELLA)\n"
        "/close — Cerrar posición abierta al precio actual\n"
        "/check — Verificar SL/TP automático con precio real\n"
        "/portfolio — Ver posiciones abiertas\n"
        "/review — Friday review: recomienda HOLD o CLOSE\n"
        "/indicators TICKER — Indicadores técnicos\n"
        "/perf — Performance acumulada\n"
    ))


async def cmd_scan(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, "⏳ Escaneando mercado...")
    try:
        data = await api.get("/swing/monday-scan")
        await _reply(update, fmt_scan(data))
    except Exception as e:
        await _reply_error(update, e)


async def cmd_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await _reply(update, "Uso: /open TICKER\nEjemplo: /open FALABELLA")
        return

    ticker = ctx.args[0].upper()
    await _reply(update, f"⏳ Buscando mejor señal para {ticker}...")

    try:
        # Obtener indicadores del ticker
        indicators = await api.get(f"/swing/{ticker}/indicators")

        # Obtener señal del scan
        scan = await api.get("/swing/monday-scan")
        best_signal = None
        for r in scan.get("results", []):
            if r.get("ticker") == ticker and r.get("best_signal"):
                best_signal = r["best_signal"]
                break

        if not best_signal or best_signal.get("action") != "BUY":
            await _reply(update, (
                f"⚠️ *{ticker}* no tiene señal de compra activa.\n"
                f"RSI: {indicators.get('rsi', 'N/A')} | EMA: {indicators.get('ema_cross')} | "
                f"MACD: {indicators.get('macd_trend')}\n\n"
                "Usa /indicators TICKER para ver el detalle."
            ))
            return

        body = {
            "ticker": ticker,
            "strategy": best_signal["strategy"],
            "entry_price": best_signal["entry_price"],
            "stop_loss": best_signal["stop_loss"],
            "take_profit": best_signal["take_profit"],
        }
        trade = await api.post("/swing/paper/open", body)

        strategy_label = best_signal["strategy"].replace("_", " ").title()
        await _reply(update, (
            f"✅ *Trade abierto: {ticker}*\n\n"
            f"Estrategia: {strategy_label}\n"
            f"Entrada: ${body['entry_price']:,.0f} CLP\n"
            f"Stop Loss: ${body['stop_loss']:,.0f} CLP  (-{abs((body['stop_loss']-body['entry_price'])/body['entry_price']*100):.1f}%)\n"
            f"Take Profit: ${body['take_profit']:,.0f} CLP  (+{abs((body['take_profit']-body['entry_price'])/body['entry_price']*100):.1f}%)\n"
            f"Capital: ${trade.get('capital_used', 100000):,.0f} CLP\n\n"
            f"ID: `{trade.get('id', '')[:8]}...`\n"
            f"Usa /check para monitorear SL/TP automático."
        ))

    except Exception as e:
        msg = str(e)
        if "posición" in msg.lower() or "máximo" in msg.lower():
            await _reply(update, f"⚠️ {msg}\nUsa /close para cerrar la posición actual.")
        else:
            await _reply_error(update, e)


async def cmd_close(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, "⏳ Obteniendo precio actual y cerrando posición...")
    try:
        # Usar check-prices para obtener precio real y cerrar
        result = await api.post("/swing/paper/check-prices")
        still_open = result.get("still_open", [])

        if not still_open and not result.get("executed"):
            await _reply(update, "No hay posiciones abiertas.")
            return

        if result.get("executed"):
            # Ya se cerró automáticamente (SL o TP cruzado)
            await _reply(update, fmt_check(result))
            return

        # Cerrar manualmente al precio actual
        trade = still_open[0]
        trade_id = trade.get("id")
        price = trade.get("current_price")

        if not price:
            await _reply(update, "⚠️ No se pudo obtener precio actual. Intenta en unos minutos.")
            return

        closed = await api.post(f"/swing/paper/close/{trade_id}", {"exit_price": price})
        pnl = closed.get("pnl", 0)
        pnl_pct = closed.get("pnl_pct", 0)
        sign = "+" if pnl >= 0 else ""
        emoji = "🟢" if pnl >= 0 else "🔴"

        await _reply(update, (
            f"{emoji} *Trade cerrado: {closed.get('ticker')}*\n\n"
            f"Precio salida: ${price:,.0f} CLP\n"
            f"P&L: {sign}{pnl:,.0f} CLP  ({sign}{pnl_pct:.1f}%)\n\n"
            "Usa /perf para ver tu performance acumulada."
        ))

    except Exception as e:
        await _reply_error(update, e)


async def cmd_check(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, "⏳ Verificando precios en tiempo real...")
    try:
        result = await api.post("/swing/paper/check-prices")
        await _reply(update, fmt_check(result))
    except Exception as e:
        await _reply_error(update, e)


async def cmd_portfolio(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await api.get("/swing/paper/portfolio")
        await _reply(update, fmt_portfolio(data))
    except Exception as e:
        await _reply_error(update, e)


async def cmd_review(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await _reply(update, "⏳ Analizando posiciones para el viernes...")
    try:
        data = await api.get("/swing/friday-review")
        await _reply(update, fmt_review(data))
    except Exception as e:
        await _reply_error(update, e)


async def cmd_indicators(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not ctx.args:
        await _reply(update, "Uso: /indicators TICKER\nEjemplo: /indicators COPEC")
        return
    ticker = ctx.args[0].upper()
    try:
        data = await api.get(f"/swing/{ticker}/indicators")
        await _reply(update, fmt_indicators(ticker, data))
    except Exception as e:
        await _reply_error(update, e)


async def cmd_perf(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await api.get("/swing/paper/performance")
        await _reply(update, fmt_performance(data))
    except Exception as e:
        await _reply_error(update, e)


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("review", cmd_review))
    app.add_handler(CommandHandler("indicators", cmd_indicators))
    app.add_handler(CommandHandler("perf", cmd_perf))

    logger.info("Bot iniciado. Escuchando comandos...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
