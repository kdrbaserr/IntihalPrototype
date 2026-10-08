from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, model_validator
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
    session_ttl_seconds: int = Field(default=28800, ge=60, le=604800)
    demo_password: SecretStr | None = None
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
    algorithm_version: str = Field(default="classical-hybrid-v2", min_length=1, max_length=100)
    similarity_threshold: Decimal = Field(default=Decimal("0.7500"), ge=0, le=1)
    word_tfidf_weight: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)
    character_tfidf_weight: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    word_overlap_weight: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    redis_host: str = "localhost"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_password: SecretStr = SecretStr("local-redis-change-me")
    redis_broker_db: int = Field(default=0, ge=0, le=15)
    redis_result_db: int = Field(default=1, ge=0, le=15)
    worker_concurrency: int = Field(default=2, ge=1)
    task_soft_timeout_seconds: int = Field(default=240, ge=1)
    task_hard_timeout_seconds: int = Field(default=300, ge=1)
    task_max_retries: int = Field(default=3, ge=0)
    analysis_manual_retry_limit: int = Field(default=3, ge=0, le=20)
    analysis_manual_retry_delay_seconds: int = Field(default=30, ge=1, le=3600)
    task_retry_backoff_seconds: int = Field(default=10, ge=1)
    task_retry_backoff_max_seconds: int = Field(default=120, ge=1)
    redis_visibility_timeout_seconds: int = Field(default=900, ge=1)
    task_result_expires_seconds: int = Field(default=86400, ge=1)

    model_config = SettingsConfigDict(
        env_file=API_DIR / ".env",
        env_file_encoding="utf-8",
        env_prefix="INTIHAL_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_auth_origins(self) -> "Settings":
        if not self.cors_origins or any(origin == "*" for origin in self.cors_origins):
            raise ValueError("Cookie authentication requires explicit CORS origins")
        if self.environment in {"staging", "production"} and any(
            not origin.startswith("https://") for origin in self.cors_origins
        ):
            raise ValueError("staging/production authentication requires HTTPS origins")
        return self

    @property
    def session_cookie_secure(self) -> bool:
        return self.environment in {"staging", "production"}

    @property
    def session_cookie_name(self) -> str:
        return "__Host-intihal_session" if self.session_cookie_secure else "intihal_session"

    @model_validator(mode="after")
    def validate_similarity_weights(self) -> "Settings":
        """Require a normalized weighted score instead of silently changing its scale."""

        total = self.word_tfidf_weight + self.character_tfidf_weight + self.word_overlap_weight
        if total != Decimal("1"):
            raise ValueError("similarity weights must add up to exactly 1")
        return self

    @model_validator(mode="after")
    def validate_worker_policy(self) -> "Settings":
        if self.task_soft_timeout_seconds >= self.task_hard_timeout_seconds:
            raise ValueError("task soft timeout must be less than hard timeout")
        if self.task_retry_backoff_seconds > self.task_retry_backoff_max_seconds:
            raise ValueError("retry backoff must not exceed its maximum")
        if self.redis_visibility_timeout_seconds <= (
            self.task_hard_timeout_seconds + self.task_retry_backoff_max_seconds
        ):
            raise ValueError("Redis visibility timeout must exceed hard timeout plus retry delay")
        if self.redis_broker_db == self.redis_result_db:
            raise ValueError("Redis broker and result databases must be different")
        return self


@lru_cache
def get_settings() -> Settings:
    """Build settings once and reuse them for every request."""

    return Settings()
