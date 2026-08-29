"""
Centralized configuration loaded from environment variables.
No secrets are hardcoded. See .env.example for required variables.
"""
import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database - Supabase Postgres connection string
    # e.g. postgresql://postgres:[password]@db.xxxx.supabase.co:5432/postgres
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./local_dev.db")

    # Optional LLM key (Anthropic). If absent, the deterministic investigation
    # engine is used automatically so the deployed demo always works.
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")

    # CORS - comma separated list of allowed origins, e.g. your Vercel URL
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    ENV: str = os.getenv("ENV", "development")
    PORT: int = int(os.getenv("PORT", "8000"))

    MODEL_DIR: str = os.getenv("MODEL_DIR", "app/models_store")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
