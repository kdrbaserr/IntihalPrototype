from pytest import MonkeyPatch

from intihal_api.core.config import get_settings


def test_settings_are_loaded_from_prefixed_environment(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("INTIHAL_ENVIRONMENT", "test")
    monkeypatch.setenv("INTIHAL_DEBUG", "true")
    get_settings.cache_clear()

    try:
        settings = get_settings()

        assert settings.environment == "test"
        assert settings.debug is True
    finally:
        get_settings.cache_clear()
