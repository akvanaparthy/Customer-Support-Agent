from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-6"
    db_path: str = "data/crm.db"
    max_tokens: int = 1024
    refund_window_days: int = 30
    escalation_threshold: float = 500.0
    price_input_per_mtok: float = 3.0
    price_output_per_mtok: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
