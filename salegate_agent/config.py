"""Settings. The only place that reads .env, mirroring salegate/app/config.py."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Values from .env. Secrets are read here and never logged or echoed."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    salegate_api_base: str = "http://127.0.0.1:8000"
    request_timeout_s: float = 10.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
