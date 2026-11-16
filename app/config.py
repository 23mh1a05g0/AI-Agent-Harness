"""Application Configuration Module using Pydantic Settings."""

from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Configuration settings loaded from environment or .env file."""

    APP_NAME: str = "AI Agent Harness"
    APP_ENV: str = "development"
    DEBUG: bool = True

    API_PORT: int = 8000

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/agent_harness"

    TRUST_THRESHOLD: int = 3

    MOCK_LLM_ENABLED: bool = True

    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_BASE_URL: Optional[str] = None

    LOG_LEVEL: str = "INFO"
    TRACES_FILE_PATH: str = str(BASE_DIR / "traces" / "traces.jsonl")

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
