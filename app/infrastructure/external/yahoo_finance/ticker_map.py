"""Mapeo de tickers chilenos (Bolsa de Santiago) a Yahoo Finance.

Yahoo Finance usa el sufijo .SN para acciones de la Bolsa de Santiago.
Algunos tickers tienen diferencias de nomenclatura.
"""

# Mapeo: nemo Bolsa Santiago → ticker Yahoo Finance
SANTIAGO_TO_YAHOO: dict[str, str] = {
    # Minería
    "SQM-B": "SQM-B.SN",
    "CAP": "CAP.SN",
    # Banca
    "BCI": "BCI.SN",
    "BSANTANDER": "BSANTANDER.SN",
    "CHILE": "CHILE.SN",
    "ITAUCORP": "ITAUCORP.SN",
    "SECURITY": "SECURITY.SN",
    # Retail
    "FALABELLA": "FALABELLA.SN",
    "CENCOSUD": "CENCOSUD.SN",
    "RIPLEY": "RIPLEY.SN",
    # Energía
    "COPEC": "COPEC.SN",
    "ENELAM": "ENELAM.SN",
    "COLBUN": "COLBUN.SN",
    "ECL": "ECL.SN",
    # Forestal
    "CMPC": "CMPC.SN",
    # Consumo
    "CCU": "CCU.SN",
    # Transporte
    "VAPORES": "VAPORES.SN",
    # AFP
    "PROVIDA": "PROVIDA.SN",
    # Inmobiliario
    "PARAUCO": "PARAUCO.SN",
    # Servicios Básicos
    "AGUAS-A": "AGUAS-A.SN",
}

# Inverso: Yahoo → Bolsa Santiago
YAHOO_TO_SANTIAGO: dict[str, str] = {v: k for k, v in SANTIAGO_TO_YAHOO.items()}


def to_yahoo_ticker(nemo: str) -> str:
    """Convierte nemo de Bolsa de Santiago a ticker de Yahoo Finance."""
    nemo_upper = nemo.upper()
    if nemo_upper in SANTIAGO_TO_YAHOO:
        return SANTIAGO_TO_YAHOO[nemo_upper]
    # Fallback genérico: agregar .SN
    return f"{nemo_upper}.SN"


def to_santiago_nemo(yahoo_ticker: str) -> str:
    """Convierte ticker de Yahoo Finance a nemo de Bolsa de Santiago."""
    if yahoo_ticker in YAHOO_TO_SANTIAGO:
        return YAHOO_TO_SANTIAGO[yahoo_ticker]
    # Fallback: quitar .SN
    return yahoo_ticker.replace(".SN", "")
