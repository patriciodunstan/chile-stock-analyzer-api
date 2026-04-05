"""Cliente HTTP para la API del Banco Central de Chile (SIETE REST).

Documentación: https://si3.bcentral.cl/SieteRestWS
Series relevantes:
- F073.TCO.PRE.Z.D  → Tipo de cambio USD/CLP
- F073.UFF.PRE.Z.D  → Valor UF
- F022.TPM.TIN.D001.NO.Z.D → Tasa de Política Monetaria
- F032.IRR.TIP.B010.D001.S01.Z.D → Tasa BCP-10 (proxy risk-free)
"""

import logging
from datetime import date, timedelta

import httpx

from app.application.interfaces.macro_data_provider import (
    MacroDataProvider,
    MacroIndicators,
)
from app.config import get_settings
from app.domain.exceptions import ExternalAPIError

logger = logging.getLogger(__name__)

# Series del Banco Central
SERIES = {
    "usd_clp": "F073.TCO.PRE.Z.D",
    "uf": "F073.UFF.PRE.Z.D",
    "tpm": "F022.TPM.TIN.D001.NO.Z.D",
    "bcp10": "F032.IRR.TIP.B010.D001.S01.Z.D",
}


class BancoCentralClient(MacroDataProvider):
    """Implementación del proveedor de datos macroeconómicos vía API SIETE."""

    def __init__(self):
        settings = get_settings()
        self._base_url = settings.banco_central_api_url
        self._user = settings.banco_central_api_user
        self._password = settings.banco_central_api_pass

    async def _get_series(
        self,
        series_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """Consulta una serie del Banco Central."""
        if to_date is None:
            to_date = date.today()
        if from_date is None:
            from_date = to_date - timedelta(days=30)

        params = {
            "user": self._user,
            "pass": self._password,
            "function": "GetSeries",
            "timeseries": series_id,
            "firstdate": from_date.strftime("%Y-%m-%d"),
            "lastdate": to_date.strftime("%Y-%m-%d"),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(self._base_url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("Series", {}).get("Obs", [])
        except (httpx.HTTPError, httpx.RequestError) as e:
            logger.error(f"Banco Central API error for {series_id}: {e}")
            raise ExternalAPIError(
                message="Error fetching Banco Central data",
                details={"series": series_id, "error": str(e)},
            )

    async def _get_latest_value(self, series_id: str) -> float:
        """Obtiene el valor más reciente de una serie."""
        observations = await self._get_series(series_id)
        if not observations:
            return 0.0
        latest = observations[-1]
        try:
            return float(latest.get("value", 0))
        except (ValueError, TypeError):
            return 0.0

    async def get_current_indicators(self) -> MacroIndicators:
        """Obtiene todos los indicadores macro actuales."""
        uf = await self._get_latest_value(SERIES["uf"])
        usd_clp = await self._get_latest_value(SERIES["usd_clp"])
        tpm = await self._get_latest_value(SERIES["tpm"])
        bcp10 = await self._get_latest_value(SERIES["bcp10"])

        return MacroIndicators(
            uf_value=uf,
            dollar_clp=usd_clp,
            tpm=tpm,
            inflation_12m=0.0,  # Se calcula de otra serie
            risk_free_rate=bcp10,
            observation_date=date.today(),
        )

    async def get_usd_clp(self) -> float:
        """Tipo de cambio USD/CLP del día desde el Banco Central.

        Raises:
            ValueError: Si las credenciales no están configuradas.
            ExternalAPIError: Si la API no responde o retorna error.
        """
        if not self._user or not self._password:
            raise ValueError("Credenciales del Banco Central no configuradas")
        value = await self._get_latest_value(SERIES["usd_clp"])
        if value <= 0:
            raise ExternalAPIError(
                message="Banco Central retornó TC inválido",
                details={"value": value},
            )
        return value

    async def get_uf(self) -> float:
        return await self._get_latest_value(SERIES["uf"])

    async def get_risk_free_rate(self) -> float:
        return await self._get_latest_value(SERIES["bcp10"])
