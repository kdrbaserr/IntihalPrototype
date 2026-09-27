from pytest import MonkeyPatch

from intihal_api.core.config import get_settings


def test_settings_are_loaded_from_prefixed_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTIHAL_ENVIRONMENT", "test")
    monkeypatch.setenv("INTIHAL_DEBUG", "true")
    monkeypatch.setenv(
        "INTIHAL_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test",
    )
    get_settings.cache_clear()

    try:
        settings = get_settings()

        assert settings.environment == "test"
        assert settings.debug is True
        assert settings.database_url == "postgresql+asyncpg://test:test@localhost:5432/test"
    finally:
        get_settings.cache_clear()
