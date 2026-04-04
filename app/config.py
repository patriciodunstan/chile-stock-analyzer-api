from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "Chile Stock Analyzer"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "sqlite+aiosqlite:////tmp/chile_stocks.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Bolsa de Santiago
    bolsa_santiago_base_url: str = "https://www.bolsadesantiago.com/api"

    # Banco Central
    banco_central_api_url: str = (
        "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
    )
    banco_central_api_user: str = ""
    banco_central_api_pass: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
