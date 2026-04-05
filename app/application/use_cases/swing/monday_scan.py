"""Use Case: Monday Scan — escanea oportunidades de swing para el lunes.

Consulta precios históricos de todas las empresas activas,
calcula indicadores técnicos y evalúa las 3 estrategias.
Retorna ranking ordenado por strength de señal.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.domain.entities.company import COMPANY_REGISTRY, Company
from app.domain.services.swing_signal_service import (
    MondayScanResult,
    SwingSignalService,
)
from app.domain.services.technical_indicators import TechnicalIndicatorsService
from app.application.interfaces.market_data_provider import MarketDataProvider
from app.domain.repositories.stock_repository import StockRepository

logger = logging.getLogger(__name__)

_INDICATORS = TechnicalIndicatorsService()
_MIN_PRICES = 30   # mínimo de precios históricos para calcular indicadores


@dataclass
class MondayScanUseCase:
    stock_repository: StockRepository
    market_provider: MarketDataProvider
    max_capital_per_trade: float = 100_000.0

    async def execute(self, sector_filter: str | None = None) -> list[MondayScanResult]:
        """Escanea todas las empresas activas y retorna ranking de oportunidades.

        Args:
            sector_filter: Filtrar por sector (ej: "Minería"). None = todas.

        Returns:
            Lista ordenada por strength de señal (mayor primero).
        """
        signal_service = SwingSignalService(self.max_capital_per_trade)
        companies = list(COMPANY_REGISTRY.values())

        if sector_filter:
            companies = [c for c in companies if c.sector.value == sector_filter]

        sem = asyncio.Semaphore(5)

        async def scan_one(company: Company) -> MondayScanResult | None:
            async with sem:
                try:
                    return await self._scan_company(company, signal_service)
                except Exception as e:
                    logger.warning("Error escaneando %s: %s", company.ticker, e)
                    return None

        results_raw = await asyncio.gather(*[scan_one(c) for c in companies])
        results = [r for r in results_raw if r is not None]

        # Ordenar: primero los con oportunidad BUY, luego por strength desc
        results.sort(key=lambda r: (0 if r.has_opportunity else 1, -r.strength))
        return results

    async def _scan_company(
        self, company: Company, signal_service: SwingSignalService
    ) -> MondayScanResult:
        """Escanea una empresa y retorna su MondayScanResult."""
        prices = await self.stock_repository.get_price_history(
            company.ticker, limit=60
        )

        if len(prices) < _MIN_PRICES:
            # Intentar obtener precio actual al menos
            try:
                current = await self.market_provider.get_price(company.ticker)
                prices = [current]
            except Exception:
                pass

        if len(prices) < _MIN_PRICES:
            return MondayScanResult(
                ticker=company.ticker,
                name=company.name,
                sector=company.sector.value,
                best_signal=None,
                all_signals=[],
                snapshot={"error": f"Datos insuficientes ({len(prices)} precios, mínimo {_MIN_PRICES})"},
            )

        closes = [p.close_price or p.price for p in prices]
        highs = [p.high or p.price for p in prices]
        lows = [p.low or p.price for p in prices]
        volumes = [p.volume or 0 for p in prices]

        snap = _INDICATORS.snapshot(
            ticker=company.ticker,
            closes=closes,
            highs=highs,
            lows=lows,
            volumes=volumes,
        )

        if snap is None:
            return MondayScanResult(
                ticker=company.ticker,
                name=company.name,
                sector=company.sector.value,
                best_signal=None,
                all_signals=[],
                snapshot={"error": "No se pudieron calcular indicadores"},
            )

        # Calcular cambio semanal (últimos 5 días)
        week_change = 0.0
        if len(closes) >= 6:
            week_change = (closes[-1] - closes[-6]) / closes[-6] * 100

        day_change = 0.0
        if len(prices) >= 2:
            prev = closes[-2]
            day_change = (closes[-1] - prev) / prev * 100 if prev > 0 else 0.0

        signals = signal_service.evaluate_all(snap, week_change, day_change)
        best = signal_service.best_signal(signals)

        return MondayScanResult(
            ticker=company.ticker,
            name=company.name,
            sector=company.sector.value,
            best_signal=best,
            all_signals=signals,
            snapshot={
                "last_price": snap.last_price,
                "rsi": snap.rsi,
                "rsi_signal": snap.rsi_signal,
                "ema9": snap.ema9,
                "ema21": snap.ema21,
                "ema_cross": snap.ema_cross,
                "macd_histogram": snap.macd_histogram,
                "macd_trend": snap.macd_trend,
                "bb_position": snap.bb_position,
                "bb_pct": snap.bb_pct,
                "volume_ratio": snap.volume_ratio,
                "week_change_pct": round(week_change, 2),
                "day_change_pct": round(day_change, 2),
            },
        )
