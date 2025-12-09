"""
Application Configuration

Pydantic Settings for environment variable management.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # App
    app_name: str = "GGP Poker Video Catalog API"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    database_url: str = "postgresql://pokervod:pokervod123@localhost:5432/pokervod"

    # API
    cors_origins: str = '["http://localhost:3000"]'

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string"""
        try:
            return json.loads(self.cors_origins)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Global settings instance for easy import
settings = get_settings()
