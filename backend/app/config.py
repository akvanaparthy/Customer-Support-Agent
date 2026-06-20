from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the repo-root .env regardless of the working directory the app is started
# from (so a single .env at the project root works for `uvicorn` run from
# backend/ AND for Docker, where injected env vars take precedence anyway).
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ROOT_ENV), extra="ignore")

    anthropic_api_key: str = ""
    model: str = "claude-sonnet-4-6"
    db_path: str = "data/crm.db"
    max_tokens: int = 1024
    refund_window_days: int = 30
    escalation_threshold: float = 500.0
    buyer_remorse_window_days: int = 14
    abuse_refund_threshold: int = 2
    price_input_per_mtok: float = 3.0
    price_output_per_mtok: float = 15.0
    enable_fault_injection: bool = True  # demo-only chaos hook; would be False in prod


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
