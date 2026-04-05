"""Formatea respuestas de la API en mensajes legibles para Telegram."""
from __future__ import annotations


def fmt_scan(data: dict) -> str:
    total = data.get("total_scanned", 0)
    opps = data.get("opportunities", 0)
    results = data.get("results", [])

    lines = [f"📊 *Monday Scan* — {opps}/{total} oportunidades\n"]

    # Top 5 con señal
    shown = 0
    for r in results:
        sig = r.get("best_signal")
        if not sig:
            continue
        if shown >= 5:
            break
        action = sig.get("action", "")
        if action != "BUY":
            continue
        ticker = r.get("ticker", "")
        strength = sig.get("strength", 0)
        strategy = sig.get("strategy", "").replace("_", " ").title()
        entry = sig.get("entry_price", 0)
        sl = sig.get("stop_loss", 0)
        tp = sig.get("take_profit", 0)
        rr = sig.get("risk_reward", 0)
        reasons = sig.get("reasons", [])

        lines.append(
            f"*{ticker}* — {strategy} ({strength}/100)\n"
            f"  Entrada: ${entry:,.0f}  SL: ${sl:,.0f}  TP: ${tp:,.0f}\n"
            f"  R/R: {rr:.1f}x\n"
            f"  {reasons[0] if reasons else ''}\n"
        )
        shown += 1

    if shown == 0:
        lines.append("Sin señales de compra claras hoy.")

    lines.append("\nUsa /open TICKER para abrir un trade.")
    return "\n".join(lines)


def fmt_portfolio(data: dict) -> str:
    cap_avail = data.get("capital_available", 0)
    cap_pos = data.get("capital_in_positions", 0)
    unreal = data.get("unrealized_pnl", 0)
    unreal_pct = data.get("unrealized_pnl_pct", 0)
    trades = data.get("open_trades", [])

    sign = "+" if unreal >= 0 else ""
    lines = [
        "💼 *Portfolio Paper*\n",
        f"Capital disponible: ${cap_avail:,.0f} CLP",
        f"En posiciones: ${cap_pos:,.0f} CLP",
        f"P&L no realizado: {sign}{unreal:,.0f} CLP ({sign}{unreal_pct:.1f}%)\n",
    ]

    if not trades:
        lines.append("Sin posiciones abiertas.")
    else:
        for t in trades:
            ticker = t.get("ticker", "")
            entry = t.get("entry_price", 0)
            current = t.get("current_price", entry)
            pnl_pct = t.get("unrealized_pnl_pct", 0)
            sl = t.get("stop_loss", 0)
            tp = t.get("take_profit", 0)
            sign_t = "+" if pnl_pct >= 0 else ""
            emoji = "🟢" if pnl_pct > 0 else ("🔴" if pnl_pct < 0 else "⚪")
            lines.append(
                f"{emoji} *{ticker}* — Entrada ${entry:,.0f} → Actual ${current:,.0f}\n"
                f"   P&L: {sign_t}{pnl_pct:.1f}%  |  SL ${sl:,.0f}  TP ${tp:,.0f}"
            )

    return "\n".join(lines)


def fmt_check(data: dict) -> str:
    executed = data.get("executed", [])
    still_open = data.get("still_open", [])

    lines = ["🔍 *Check de precios*\n"]

    if executed:
        lines.append("*Trades ejecutados automáticamente:*")
        for t in executed:
            emoji = t.get("emoji", "⚪")
            ticker = t.get("ticker", "")
            trigger = t.get("trigger", "")
            price = t.get("current_price", 0)
            pnl_pct = t.get("pnl_pct", 0)
            pnl = t.get("pnl", 0)
            sign = "+" if pnl >= 0 else ""
            label = "Take Profit ✅" if trigger == "TAKE_PROFIT" else "Stop Loss ❌"
            lines.append(
                f"{emoji} *{ticker}* — {label}\n"
                f"   Precio: ${price:,.0f}  |  P&L: {sign}{pnl:,.0f} CLP ({sign}{pnl_pct:.1f}%)"
            )
    else:
        lines.append("Ningún SL/TP cruzado.")

    if still_open:
        lines.append("\n*Posiciones que siguen abiertas:*")
        for t in still_open:
            ticker = t.get("ticker", "")
            price = t.get("current_price")
            pnl_pct = t.get("pnl_pct", 0)
            dist_sl = t.get("distance_to_sl_pct", 0)
            dist_tp = t.get("distance_to_tp_pct", 0)
            sign = "+" if pnl_pct >= 0 else ""
            if price:
                lines.append(
                    f"⚪ *{ticker}* — ${price:,.0f}  ({sign}{pnl_pct:.1f}%)\n"
                    f"   {dist_sl:.1f}% sobre SL  |  {dist_tp:.1f}% para TP"
                )
            else:
                lines.append(f"⚠️ *{ticker}* — precio no disponible")

    return "\n".join(lines)


def fmt_review(data: dict) -> str:
    positions = data.get("positions", [])
    summary = data.get("summary", "")

    lines = ["📅 *Friday Review*\n"]
    if summary:
        lines.append(f"{summary}\n")

    if not positions:
        lines.append("Sin posiciones abiertas para revisar.")
        return "\n".join(lines)

    for p in positions:
        ticker = p.get("ticker", "")
        recommendation = p.get("recommendation", "HOLD")
        pnl_pct = p.get("pnl_pct", 0)
        reason = p.get("reason", "")
        emoji = "✅" if recommendation == "CLOSE" else "🔒"
        sign = "+" if pnl_pct >= 0 else ""
        lines.append(
            f"{emoji} *{ticker}* — {recommendation}  ({sign}{pnl_pct:.1f}%)\n"
            f"   {reason}"
        )

    lines.append("\nUsa /close para cerrar la posición abierta.")
    return "\n".join(lines)


def fmt_performance(data: dict) -> str:
    total = data.get("total_trades", 0)
    wins = data.get("winning_trades", 0)
    losses = data.get("losing_trades", 0)
    win_rate = data.get("win_rate", 0)
    pnl = data.get("total_pnl", 0)
    pnl_pct = data.get("total_pnl_pct", 0)
    pf = data.get("profit_factor", 0)
    avg_win = data.get("avg_win", 0)
    avg_loss = data.get("avg_loss", 0)
    dd = data.get("max_drawdown", 0)
    best = data.get("best_trade")
    worst = data.get("worst_trade")

    sign = "+" if pnl >= 0 else ""
    emoji_pnl = "🟢" if pnl >= 0 else "🔴"
    emoji_pf = "✅" if pf >= 1.5 else ("⚠️" if pf >= 1.0 else "❌")
    emoji_wr = "✅" if win_rate >= 45 else "⚠️"

    lines = [
        "📈 *Performance Paper Trading*\n",
        f"Trades totales: {total}  ({wins} ✅ / {losses} ❌)",
        f"{emoji_wr} Win Rate: {win_rate:.1f}%  (target: >45%)",
        f"{emoji_pf} Profit Factor: {pf:.2f}x  (target: >1.5x)",
        f"{emoji_pnl} P&L total: {sign}{pnl:,.0f} CLP  ({sign}{pnl_pct:.1f}%)",
        "",
        f"Avg ganancia: +{avg_win:,.0f} CLP",
        f"Avg pérdida: -{avg_loss:,.0f} CLP",
        f"Max drawdown: {dd:.1f}%",
    ]

    if best:
        lines.append(f"\n🏆 Mejor: {best.get('ticker')} {best.get('pnl_pct', 0):+.1f}%")
    if worst:
        lines.append(f"💩 Peor: {worst.get('ticker')} {worst.get('pnl_pct', 0):+.1f}%")

    return "\n".join(lines)


def fmt_indicators(ticker: str, data: dict) -> str:
    rsi = data.get("rsi")
    rsi_sig = data.get("rsi_signal", "NEUTRAL")
    ema_cross = data.get("ema_cross", "NEUTRAL")
    macd_trend = data.get("macd_trend", "NEUTRAL")
    bb_pos = data.get("bb_position", "MIDDLE")
    bb_pct = data.get("bb_pct")
    last = data.get("last_price", 0)
    atr = data.get("atr")
    vol_ratio = data.get("volume_ratio")

    rsi_emoji = "🔴" if rsi_sig == "OVERBOUGHT" else ("🟢" if rsi_sig == "OVERSOLD" else "⚪")
    ema_emoji = "🟢" if ema_cross == "BULLISH" else ("🔴" if ema_cross == "BEARISH" else "⚪")
    macd_emoji = "🟢" if macd_trend == "BULLISH" else ("🔴" if macd_trend == "BEARISH" else "⚪")
    bb_emoji = "🟢" if bb_pos == "LOWER" else ("🔴" if bb_pos == "UPPER" else "⚪")

    rsi_str = f"{rsi:.1f}" if rsi else "N/A"
    bb_str = f"{bb_pct*100:.0f}%" if bb_pct is not None else "N/A"
    vol_str = f"{vol_ratio:.1f}x" if vol_ratio else "N/A"

    return (
        f"📊 *Indicadores {ticker}* — ${last:,.0f}\n\n"
        f"{rsi_emoji} RSI: {rsi_str}  ({rsi_sig})\n"
        f"{ema_emoji} EMA cross: {ema_cross}\n"
        f"{macd_emoji} MACD: {macd_trend}\n"
        f"{bb_emoji} Bollinger: {bb_pos}  ({bb_str})\n"
        f"⚡ ATR: {atr:.0f}" if atr else "⚡ ATR: N/A"
    ) + f"\n📦 Volumen: {vol_str}"
