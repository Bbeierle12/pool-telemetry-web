"""Application configuration using Pydantic settings."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    app_name: str = "Pool Telemetry"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production")

    # Database - Railway provides DATABASE_URL, we need to convert for async
    database_url: str = Field(default="sqlite+aiosqlite:///./data/pool_telemetry.db")

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_postgres_url(cls, v: str) -> str:
        """Convert PostgreSQL URL to async format for SQLAlchemy."""
        if v and v.startswith("postgresql://"):
            # Railway provides postgresql:// but SQLAlchemy async needs postgresql+asyncpg://
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # CORS
    allowed_origins: List[str] = Field(default=["http://localhost:5173", "http://localhost:3000"])

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        """Parse allowed origins from string or list."""
        if isinstance(v, str):
            # Handle comma-separated string or single URL
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Storage
    data_directory: Path = Field(default=Path("./data"))
    max_upload_size_mb: int = 2000
    frame_quality: int = 85

    # API Keys (from environment)
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")

    # Gemini settings
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_frame_interval_ms: int = 33

    # Video settings
    default_resolution: str = "1080p"
    default_framerate: int = 30
    hls_segment_duration: int = 2

    # Cost tracking
    cost_warning_threshold: float = 5.0
    cost_stop_threshold: float = 10.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
