from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MIPI_", extra="ignore")

    env: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://mipi:mipi_local@localhost:5432/mipi"
    redis_url: str = "redis://localhost:6379/0"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "mipi-local"
    object_storage_access_key: str = "mipi_local"
    object_storage_secret_key: str = "change-me-now"


@lru_cache
def get_settings() -> Settings:
    return Settings()
