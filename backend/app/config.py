"""Backend settings (env-driven, 12-factor)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "FIFA World Cup 2026 Prediction Platform API"
    environment: str = "development"

    # Postgres — optional; API degrades to ML-artifact + fixtures mode if unset.
    database_url: str = "postgresql+psycopg://fifa:fifa@localhost:5432/fifa2026"
    use_db: bool = False

    # Redis — optional; in-process LRU fallback if unreachable.
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 900  # seconds

    # Auth (admin)
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    admin_username: str = "admin"
    admin_password: str = "admin"  # override via env in prod

    cors_origins: str = "http://localhost:3000,http://localhost:3001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
