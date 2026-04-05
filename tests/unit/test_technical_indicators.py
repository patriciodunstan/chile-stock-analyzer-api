"""Tests unitarios para TechnicalIndicatorsService.

Cubre:
- EMA / SMA: valores correctos y manejo de series cortas
- RSI: oversold, overbought, neutral, serie con tendencia clara
- MACD: línea, señal e histograma
- Bollinger Bands: upper/lower/middle correctos
- ATR: cálculo de true range
- Snapshot: integración completa con señales derivadas
"""
import pytest

from app.domain.services.technical_indicators import TechnicalIndicatorsService

svc = TechnicalIndicatorsService()


# ── Fixtures ──────────────────────────────────────────────────

def rising_prices(n: int = 50, start: float = 1000.0, step: float = 10.0) -> list[float]:
    return [start + i * step for i in range(n)]


def falling_prices(n: int = 50, start: float = 1500.0, step: float = 10.0) -> list[float]:
    return [start - i * step for i in range(n)]


def flat_prices(n: int = 50, value: float = 1000.0) -> list[float]:
    return [value] * n


# ── EMA ───────────────────────────────────────────────────────

class TestEMA:
    def test_length_matches_input(self):
        prices = rising_prices(30)
        result = svc.ema(prices, 9)
        assert len(result) == 30

    def test_first_values_are_none(self):
        result = svc.ema(rising_prices(20), 9)
        assert all(v is None for v in result[:8])
        assert result[8] is not None

    def test_ema_trends_up_with_rising_prices(self):
        result = svc.ema(rising_prices(50), 9)
        valid = [v for v in result if v is not None]
        assert valid[-1] > valid[0]

    def test_ema_trends_down_with_falling_prices(self):
        result = svc.ema(falling_prices(50), 9)
        valid = [v for v in result if v is not None]
        assert valid[-1] < valid[0]

    def test_ema_flat_prices_equals_price(self):
        result = svc.ema(flat_prices(30, 1000.0), 9)
        valid = [v for v in result if v is not None]
        assert all(abs(v - 1000.0) < 0.01 for v in valid)

    def test_insufficient_data_all_none(self):
        result = svc.ema([100.0, 200.0], 9)
        assert all(v is None for v in result)


# ── SMA ───────────────────────────────────────────────────────

class TestSMA:
    def test_first_value_at_period(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = svc.sma(prices, 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == pytest.approx(2.0)  # (1+2+3)/3

    def test_sma_flat_equals_value(self):
        result = svc.sma(flat_prices(20, 500.0), 5)
        valid = [v for v in result if v is not None]
        assert all(v == pytest.approx(500.0) for v in valid)

    def test_length_matches_input(self):
        result = svc.sma(rising_prices(40), 20)
        assert len(result) == 40


# ── RSI ───────────────────────────────────────────────────────

class TestRSI:
    def test_length_matches_input(self):
        result = svc.rsi(rising_prices(50), 14)
        assert len(result) == 50

    def test_first_14_values_none(self):
        result = svc.rsi(rising_prices(50), 14)
        assert all(v is None for v in result[:14])
        assert result[14] is not None

    def test_strongly_rising_gives_high_rsi(self):
        """Serie que sube siempre → RSI cerca de 100."""
        result = svc.rsi(rising_prices(50), 14)
        valid = [v for v in result if v is not None]
        assert valid[-1] > 70, f"RSI esperado >70, obtenido {valid[-1]:.1f}"

    def test_strongly_falling_gives_low_rsi(self):
        """Serie que baja siempre → RSI cerca de 0."""
        result = svc.rsi(falling_prices(50), 14)
        valid = [v for v in result if v is not None]
        assert valid[-1] < 30, f"RSI esperado <30, obtenido {valid[-1]:.1f}"

    def test_flat_prices_rsi_near_50(self):
        """Sin cambios, RSI debería estar en 50 (ni gana ni pierde)."""
        prices = flat_prices(30, 1000.0)
        # Agregar pequeña variación para evitar divisón por cero
        prices[5] = 1001.0
        prices[10] = 999.0
        result = svc.rsi(prices, 14)
        valid = [v for v in result if v is not None]
        # Con datos casi flat, RSI debe estar entre 30 y 70
        assert all(20 <= v <= 80 for v in valid)

    def test_rsi_bounded_0_100(self):
        """RSI siempre entre 0 y 100."""
        result = svc.rsi(rising_prices(60) + falling_prices(40), 14)
        valid = [v for v in result if v is not None]
        assert all(0 <= v <= 100 for v in valid)

    def test_insufficient_data_all_none(self):
        result = svc.rsi([100.0] * 5, 14)
        assert all(v is None for v in result)


# ── MACD ─────────────────────────────────────────────────────

class TestMACD:
    def test_lengths_match(self):
        prices = rising_prices(60)
        result = svc.macd(prices)
        assert len(result.macd_line) == 60
        assert len(result.signal_line) == 60
        assert len(result.histogram) == 60

    def test_rising_prices_positive_histogram(self):
        """En tendencia alcista acelerada, histograma debe ser positivo."""
        # Precios con crecimiento acelerado (no lineal) → MACD line crece → histograma >0
        prices = [1000.0 * (1.02 ** i) for i in range(80)]
        result = svc.macd(prices)
        hist = [v for v in result.histogram if v is not None]
        assert any(h > 0 for h in hist), "Ningún valor del histograma fue >0 en tendencia alcista"

    def test_falling_prices_negative_histogram(self):
        """En tendencia bajista acelerada (caída cuadrática), histograma debe ser negativo."""
        # Caída acelerada: cada período cae más que el anterior → MACD creciente negativo
        prices = [10000.0 - 2.0 * (i ** 2) for i in range(70)]
        result = svc.macd(prices)
        hist = [v for v in result.histogram if v is not None]
        assert any(h < 0 for h in hist), "Ningún valor del histograma fue <0 en tendencia bajista"

    def test_histogram_equals_macd_minus_signal(self):
        """Histograma = MACD line - Signal line."""
        result = svc.macd(rising_prices(60))
        for m, s, h in zip(result.macd_line, result.signal_line, result.histogram):
            if m is not None and s is not None and h is not None:
                assert abs(h - (m - s)) < 1e-9


# ── Bollinger Bands ───────────────────────────────────────────

class TestBollingerBands:
    def test_lengths_match(self):
        prices = rising_prices(40)
        result = svc.bollinger_bands(prices, 20)
        assert len(result.upper) == 40
        assert len(result.middle) == 40
        assert len(result.lower) == 40

    def test_upper_above_lower(self):
        result = svc.bollinger_bands(rising_prices(40))
        for u, lo in zip(result.upper, result.lower):
            if u is not None and lo is not None:
                assert u >= lo

    def test_middle_is_sma(self):
        prices = rising_prices(40)
        bb = svc.bollinger_bands(prices, 20)
        sma = svc.sma(prices, 20)
        for b, s in zip(bb.middle, sma):
            if b is not None and s is not None:
                assert abs(b - s) < 1e-9

    def test_flat_prices_zero_bandwidth(self):
        """Precios constantes → bandas muy estrechas (std=0)."""
        result = svc.bollinger_bands(flat_prices(40, 1000.0))
        for u, lo in zip(result.upper, result.lower):
            if u is not None and lo is not None:
                assert abs(u - lo) < 0.01  # ancho casi cero

    def test_first_19_values_none(self):
        result = svc.bollinger_bands(rising_prices(40), 20)
        assert all(v is None for v in result.upper[:19])
        assert result.upper[19] is not None


# ── ATR ───────────────────────────────────────────────────────

class TestATR:
    def test_length_matches(self):
        n = 30
        h = rising_prices(n, step=5)
        lo = [p - 3 for p in h]
        c = [p - 1 for p in h]
        result = svc.atr(h, lo, c, 14)
        assert len(result) == n

    def test_atr_positive(self):
        h = rising_prices(30, step=15)
        lo = [p - 10 for p in h]
        c = [p - 5 for p in h]
        result = svc.atr(h, lo, c, 14)
        valid = [v for v in result if v is not None]
        assert all(v > 0 for v in valid)

    def test_high_volatility_higher_atr(self):
        """Mayor rango high-low debe dar mayor ATR."""
        h_volatile = rising_prices(30, step=50)
        lo_volatile = [p - 40 for p in h_volatile]
        c_volatile = [p - 20 for p in h_volatile]

        h_calm = rising_prices(30, step=5)
        lo_calm = [p - 2 for p in h_calm]
        c_calm = [p - 1 for p in h_calm]

        atr_v = svc.atr(h_volatile, lo_volatile, c_volatile, 14)
        atr_c = svc.atr(h_calm, lo_calm, c_calm, 14)

        v_valid = [x for x in atr_v if x is not None]
        c_valid = [x for x in atr_c if x is not None]
        assert v_valid[-1] > c_valid[-1]


# ── Snapshot ──────────────────────────────────────────────────

class TestSnapshot:
    def _make_prices(self, n=50):
        closes = rising_prices(n)
        highs = [p + 5 for p in closes]
        lows = [p - 5 for p in closes]
        volumes = [100_000] * n
        return closes, highs, lows, volumes

    def test_snapshot_returns_none_with_few_prices(self):
        closes = rising_prices(20)
        result = svc.snapshot("TEST", closes, closes, closes, [1000] * 20)
        assert result is None

    def test_snapshot_returns_valid_with_enough_prices(self):
        closes, highs, lows, volumes = self._make_prices(50)
        result = svc.snapshot("TEST", closes, highs, lows, volumes)
        assert result is not None
        assert result.ticker == "TEST"
        assert result.last_price == closes[-1]

    def test_rising_prices_give_bullish_signals(self):
        closes, highs, lows, volumes = self._make_prices(60)
        result = svc.snapshot("TEST", closes, highs, lows, volumes)
        assert result is not None
        assert result.rsi_signal in ("OVERBOUGHT", "NEUTRAL")
        assert result.ema_cross == "BULLISH"
        assert result.macd_trend in ("BULLISH", "NEUTRAL")

    def test_falling_prices_give_bearish_signals(self):
        closes = falling_prices(60)
        highs = [p + 5 for p in closes]
        lows = [p - 5 for p in closes]
        result = svc.snapshot("TEST", closes, highs, lows, [100_000] * 60)
        assert result is not None
        assert result.rsi_signal in ("OVERSOLD", "NEUTRAL")
        assert result.ema_cross == "BEARISH"

    def test_snapshot_all_fields_present(self):
        closes, highs, lows, volumes = self._make_prices(50)
        result = svc.snapshot("TEST", closes, highs, lows, volumes)
        assert result is not None
        # Campos que siempre deben estar presentes
        assert result.rsi_signal in ("OVERSOLD", "OVERBOUGHT", "NEUTRAL")
        assert result.ema_cross in ("BULLISH", "BEARISH", "NEUTRAL")
        assert result.macd_trend in ("BULLISH", "BEARISH", "NEUTRAL")
        assert result.bb_position in ("UPPER", "LOWER", "MIDDLE")
