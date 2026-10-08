from decimal import Decimal

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from intihal_api.core.config import Settings, get_settings


def test_settings_are_loaded_from_prefixed_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTIHAL_ENVIRONMENT", "test")
    monkeypatch.setenv("INTIHAL_DEBUG", "true")
    monkeypatch.setenv(
        "INTIHAL_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",
    )
    monkeypatch.setenv("INTIHAL_MINIO_ENDPOINT", "storage.test:9000")
    monkeypatch.setenv("INTIHAL_MINIO_SECRET_KEY", "test-storage-secret")
    monkeypatch.setenv("INTIHAL_MINIO_BUCKET", "test-documents")
    get_settings.cache_clear()

    try:
        settings = get_settings()

        assert settings.environment == "test"
        assert settings.debug is True
        assert settings.database_url == "postgresql+asyncpg://test:test@localhost:5432/test"
        assert settings.minio_endpoint == "storage.test:9000"
        assert settings.minio_secret_key.get_secret_value() == "test-storage-secret"
        assert settings.minio_bucket == "test-documents"
    finally:
        get_settings.cache_clear()


def test_similarity_configuration_defaults_are_normalized() -> None:
    settings = Settings(_env_file=None)

    assert settings.algorithm_version == "classical-hybrid-v2"
    assert settings.similarity_threshold == Decimal("0.7500")
    assert (
        settings.word_tfidf_weight + settings.character_tfidf_weight + settings.word_overlap_weight
        == Decimal("1")
    )


def test_similarity_weights_must_add_up_to_one() -> None:
    with pytest.raises(ValidationError, match="similarity weights must add up to exactly 1"):
        Settings(
            _env_file=None,
            word_tfidf_weight=Decimal("0.50"),
            character_tfidf_weight=Decimal("0.30"),
            word_overlap_weight=Decimal("0.30"),
        )
