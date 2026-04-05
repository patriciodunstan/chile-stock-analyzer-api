"""Indicadores técnicos para análisis de swing trading.

Servicio de dominio puro: solo cálculos, sin IO, sin side effects.
Todos los métodos reciben listas de precios y retornan listas de valores.

Indicadores implementados:
- EMA  (Exponential Moving Average)
- SMA  (Simple Moving Average)
- RSI  (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR  (Average True Range) — para stop loss dinámico
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# ============================================================
# Dataclasses de resultado
# ============================================================

@dataclass
class MACDResult:
    macd_line: list[float | None]
    signal_line: list[float | None]
    histogram: list[float | None]


@dataclass
class BollingerResult:
    upper: list[float | None]
    middle: list[float | None]   # SMA20
    lower: list[float | None]
    bandwidth: list[float | None]  # (upper - lower) / middle → volatilidad relativa


@dataclass
class TechnicalSnapshot:
    """Snapshot de todos los indicadores para el último precio disponible.

    Se usa para la evaluación de señales en un ticker.
    """
    ticker: str
    last_price: float
    last_volume: int

    # RSI
    rsi: float | None           # 0-100
    rsi_signal: str             # "OVERSOLD" | "OVERBOUGHT" | "NEUTRAL"

    # EMA
    ema9: float | None
    ema21: float | None
    ema_cross: str              # "BULLISH" | "BEARISH" | "NEUTRAL"

    # MACD
    macd_line: float | None
    macd_signal: float | None
    macd_histogram: float | None
    macd_trend: str             # "BULLISH" | "BEARISH" | "NEUTRAL"

    # Bollinger Bands
    bb_upper: float | None
    bb_middle: float | None
    bb_lower: float | None
    bb_position: str            # "UPPER" | "LOWER" | "MIDDLE"
    bb_pct: float | None        # % posición dentro de la banda (0=lower, 1=upper)

    # ATR (para stop loss dinámico)
    atr: float | None
    atr_stop_loss: float | None  # last_price - 1.5×ATR

    # Volumen
    volume_avg10: float | None
    volume_ratio: float | None  # volume / avg10 (>1.5 = volumen alto)


# ============================================================
# TechnicalIndicatorsService
# ============================================================

class TechnicalIndicatorsService:
    """Calcula indicadores técnicos sobre series de precios.

    Puro, sin IO, sin side effects. Todos los métodos son estáticos.
    """

    # ----------------------------------------------------------
    # EMA / SMA
    # ----------------------------------------------------------

    @staticmethod
    def ema(prices: list[float], period: int) -> list[float | None]:
        """Exponential Moving Average.

        Requiere al menos `period` precios para calcular el primer valor.
        Los valores anteriores se retornan como None.
        """
        if len(prices) < period:
            return [None] * len(prices)

        result: list[float | None] = [None] * (period - 1)
        k = 2.0 / (period + 1)

        # Primer valor: SMA del período inicial
        first_ema = sum(prices[:period]) / period
        result.append(first_ema)

        for price in prices[period:]:
            prev = result[-1]
            result.append(price * k + prev * (1 - k))  # type: ignore[operator]

        return result

    @staticmethod
    def sma(prices: list[float], period: int) -> list[float | None]:
        """Simple Moving Average."""
        result: list[float | None] = []
        for i in range(len(prices)):
            if i < period - 1:
                result.append(None)
            else:
                result.append(sum(prices[i - period + 1: i + 1]) / period)
        return result

    # ----------------------------------------------------------
    # RSI
    # ----------------------------------------------------------

    @staticmethod
    def rsi(prices: list[float], period: int = 14) -> list[float | None]:
        """Relative Strength Index (Wilder smoothing method).

        Valores:
          < 30 → oversold (señal de compra)
          > 70 → overbought (señal de venta)
        """
        if len(prices) < period + 1:
            return [None] * len(prices)

        result: list[float | None] = [None] * period

        # Calcular cambios
        changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [max(c, 0.0) for c in changes]
        losses = [abs(min(c, 0.0)) for c in changes]

        # Primer promedio (SMA del período inicial)
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        def _rsi_value(avg_g: float, avg_l: float) -> float:
            if avg_l == 0:
                return 100.0
            rs = avg_g / avg_l
            return 100.0 - (100.0 / (1 + rs))

        result.append(_rsi_value(avg_gain, avg_loss))

        # Wilder smoothing para el resto
        for i in range(period, len(changes)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            result.append(_rsi_value(avg_gain, avg_loss))

        return result

    # ----------------------------------------------------------
    # MACD
    # ----------------------------------------------------------

    @classmethod
    def macd(
        cls,
        prices: list[float],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> MACDResult:
        """MACD = EMA_fast - EMA_slow.

        Señal alcista: histograma positivo y creciendo.
        Señal bajista: histograma negativo y cayendo.
        """
        ema_fast = cls.ema(prices, fast)
        ema_slow = cls.ema(prices, slow)

        macd_line: list[float | None] = []
        for f, s in zip(ema_fast, ema_slow):
            if f is None or s is None:
                macd_line.append(None)
            else:
                macd_line.append(f - s)

        # Signal line = EMA9 del MACD line (solo sobre valores no None)
        macd_values_only = [v for v in macd_line if v is not None]
        if len(macd_values_only) < signal:
            signal_line: list[float | None] = [None] * len(macd_line)
        else:
            none_prefix = next(i for i, v in enumerate(macd_line) if v is not None)
            signal_values = cls.ema(macd_values_only, signal)
            signal_line = [None] * none_prefix + signal_values  # type: ignore[assignment]

        histogram: list[float | None] = []
        for m, s_val in zip(macd_line, signal_line):
            if m is None or s_val is None:
                histogram.append(None)
            else:
                histogram.append(m - s_val)

        return MACDResult(
            macd_line=macd_line,
            signal_line=signal_line,
            histogram=histogram,
        )

    # ----------------------------------------------------------
    # Bollinger Bands
    # ----------------------------------------------------------

    @classmethod
    def bollinger_bands(
        cls,
        prices: list[float],
        period: int = 20,
        std_multiplier: float = 2.0,
    ) -> BollingerResult:
        """Bollinger Bands = SMA ± k×σ.

        Precio cerca de lower band → oversold.
        Precio cerca de upper band → overbought.
        """
        middle = cls.sma(prices, period)
        upper: list[float | None] = []
        lower: list[float | None] = []
        bandwidth: list[float | None] = []

        for i, mid in enumerate(middle):
            if mid is None or i < period - 1:
                upper.append(None)
                lower.append(None)
                bandwidth.append(None)
            else:
                window = prices[i - period + 1: i + 1]
                std = math.sqrt(sum((p - mid) ** 2 for p in window) / period)
                u = mid + std_multiplier * std
                lo = mid - std_multiplier * std
                upper.append(u)
                lower.append(lo)
                bandwidth.append((u - lo) / mid if mid != 0 else None)

        return BollingerResult(upper=upper, middle=middle, lower=lower, bandwidth=bandwidth)

    # ----------------------------------------------------------
    # ATR — Average True Range
    # ----------------------------------------------------------

    @staticmethod
    def atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int = 14,
    ) -> list[float | None]:
        """Average True Range — mide volatilidad.

        True Range = max(high-low, |high-prev_close|, |low-prev_close|)
        """
        if len(highs) < 2:
            return [None] * len(highs)

        true_ranges: list[float] = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            true_ranges.append(tr)

        if len(true_ranges) < period:
            return [None] * len(highs)

        result: list[float | None] = [None, None]  # 2 iniciales sin valor

        # Primer ATR = SMA de true_ranges[:period]
        first_atr = sum(true_ranges[:period]) / period
        result.append(first_atr)

        for tr in true_ranges[period:]:
            prev_atr = result[-1]
            result.append((prev_atr * (period - 1) + tr) / period)  # type: ignore[operator]

        # Ajustar longitud para coincidir con la serie original
        while len(result) < len(highs):
            result.insert(0, None)

        return result[:len(highs)]

    # ----------------------------------------------------------
    # Snapshot completo
    # ----------------------------------------------------------

    @classmethod
    def snapshot(
        cls,
        ticker: str,
        closes: list[float],
        highs: list[float],
        lows: list[float],
        volumes: list[int],
    ) -> TechnicalSnapshot | None:
        """Calcula todos los indicadores y retorna el estado actual (último valor).

        Requiere al menos 30 precios para resultados significativos.
        Retorna None si no hay suficientes datos.
        """
        if len(closes) < 26:  # mínimo para MACD slow=26
            return None

        last_price = closes[-1]
        last_volume = volumes[-1] if volumes else 0

        # RSI
        rsi_series = cls.rsi(closes, 14)
        rsi_val = rsi_series[-1]
        if rsi_val is None:
            rsi_signal = "NEUTRAL"
        elif rsi_val < 35:
            rsi_signal = "OVERSOLD"
        elif rsi_val > 65:
            rsi_signal = "OVERBOUGHT"
        else:
            rsi_signal = "NEUTRAL"

        # EMA 9 / 21
        ema9_series = cls.ema(closes, 9)
        ema21_series = cls.ema(closes, 21)
        ema9_val = ema9_series[-1]
        ema21_val = ema21_series[-1]

        if ema9_val is not None and ema21_val is not None:
            prev9 = ema9_series[-2]
            prev21 = ema21_series[-2]
            if (
                prev9 is not None and prev21 is not None
                and prev9 <= prev21 and ema9_val > ema21_val
            ):
                ema_cross = "BULLISH"
            elif (
                prev9 is not None and prev21 is not None
                and prev9 >= prev21 and ema9_val < ema21_val
            ):
                ema_cross = "BEARISH"
            elif ema9_val > ema21_val:
                ema_cross = "BULLISH"
            else:
                ema_cross = "BEARISH"
        else:
            ema_cross = "NEUTRAL"

        # MACD
        macd_result = cls.macd(closes)
        macd_line_val = macd_result.macd_line[-1]
        macd_signal_val = macd_result.signal_line[-1]
        macd_hist_val = macd_result.histogram[-1]
        macd_prev_hist = macd_result.histogram[-2] if len(macd_result.histogram) > 1 else None

        if macd_hist_val is not None and macd_hist_val > 0:
            if macd_prev_hist is not None and macd_hist_val > macd_prev_hist:
                macd_trend = "BULLISH"  # positivo y creciendo
            else:
                macd_trend = "NEUTRAL"
        elif macd_hist_val is not None and macd_hist_val < 0:
            macd_trend = "BEARISH"
        else:
            macd_trend = "NEUTRAL"

        # Bollinger Bands
        bb = cls.bollinger_bands(closes)
        bb_upper_val = bb.upper[-1]
        bb_middle_val = bb.middle[-1]
        bb_lower_val = bb.lower[-1]

        bb_pct = None
        bb_position = "MIDDLE"
        if bb_upper_val and bb_lower_val and bb_upper_val != bb_lower_val:
            bb_pct = (last_price - bb_lower_val) / (bb_upper_val - bb_lower_val)
            if bb_pct <= 0.15:
                bb_position = "LOWER"
            elif bb_pct >= 0.85:
                bb_position = "UPPER"
            else:
                bb_position = "MIDDLE"

        # ATR
        atr_series = cls.atr(highs, lows, closes)
        atr_val = atr_series[-1]
        atr_stop = (last_price - 1.5 * atr_val) if atr_val else None

        # Volumen
        float_volumes = [float(v) for v in volumes]
        vol_avg10 = sum(float_volumes[-10:]) / min(10, len(float_volumes)) if float_volumes else None
        vol_ratio = (last_volume / vol_avg10) if vol_avg10 and vol_avg10 > 0 else None

        return TechnicalSnapshot(
            ticker=ticker,
            last_price=last_price,
            last_volume=last_volume,
            rsi=round(rsi_val, 2) if rsi_val is not None else None,
            rsi_signal=rsi_signal,
            ema9=round(ema9_val, 2) if ema9_val is not None else None,
            ema21=round(ema21_val, 2) if ema21_val is not None else None,
            ema_cross=ema_cross,
            macd_line=round(macd_line_val, 4) if macd_line_val is not None else None,
            macd_signal=round(macd_signal_val, 4) if macd_signal_val is not None else None,
            macd_histogram=round(macd_hist_val, 4) if macd_hist_val is not None else None,
            macd_trend=macd_trend,
            bb_upper=round(bb_upper_val, 2) if bb_upper_val is not None else None,
            bb_middle=round(bb_middle_val, 2) if bb_middle_val is not None else None,
            bb_lower=round(bb_lower_val, 2) if bb_lower_val is not None else None,
            bb_position=bb_position,
            bb_pct=round(bb_pct, 3) if bb_pct is not None else None,
            atr=round(atr_val, 2) if atr_val is not None else None,
            atr_stop_loss=round(atr_stop, 2) if atr_stop is not None else None,
            volume_avg10=round(vol_avg10, 0) if vol_avg10 is not None else None,
            volume_ratio=round(vol_ratio, 2) if vol_ratio is not None else None,
        )
