"""Puerto de salida — proveedor de datos macroeconómicos."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date as date_type


@dataclass
class MacroIndicators:
    """Indicadores macroeconómicos de Chile."""

    uf_value: float  # Valor UF actual en CLP
    dollar_clp: float  # Tipo de cambio USD/CLP
    tpm: float  # Tasa de Política Monetaria (%)
    inflation_12m: float  # Inflación 12 meses (%)
    risk_free_rate: float  # Tasa libre de riesgo (BCP-10)
    observation_date: date_type | None = None


class MacroDataProvider(ABC):
    """Interfaz para obtener datos macroeconómicos del Banco Central."""

    @abstractmethod
    async def get_current_indicators(self) -> MacroIndicators:
        pass

    @abstractmethod
    async def get_uf(self) -> float:
        pass

    @abstractmethod
    async def get_usd_clp(self) -> float:
        """Tipo de cambio USD/CLP del día."""
        pass

    @abstractmethod
    async def get_risk_free_rate(self) -> float:
        """Tasa libre de riesgo (BCP-10 o similar)."""
        pass
