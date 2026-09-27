from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or `.env`."""

    app_name: str = "Intihal Prototype API"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    demo_user_id: UUID = UUID("11111111-1111-1111-1111-111111111111")
    database_url: str = (
        "postgresql+asyncpg://intihal_app:local-postgres-change-me@localhost:5432/intihal"
    )
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "intihal_minio"
    minio_secret_key: SecretStr = SecretStr("local-minio-change-me-12345")
    minio_secure: bool = False
    minio_bucket: str = "intihal-documents"
    minio_connect_timeout_seconds: float = 2.0
    minio_read_timeout_seconds: float = 5.0

    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="INTIHAL_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them for every request."""

    return Settings()
