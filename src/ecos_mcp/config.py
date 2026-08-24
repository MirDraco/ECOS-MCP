from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ecos_api_key: str | None = None
    ecos_base_url: str = "https://ecos.bok.or.kr/api"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 18765
    ecos_timeout_seconds: float = 20.0
    ecos_max_retries: int = 2
    cache_enabled: bool = True
    cache_path: str = "data/ecos_cache.sqlite3"
    cache_ttl_seconds: int = 86400
    recent_cache_ttl_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
