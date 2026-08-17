import pytest

from app.config.settings import (
    Environment,
    LogLevel,
    get_settings,
)


def test_settings_use_default_values(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = get_settings()

    assert settings.environment == Environment.DEVELOPMENT
    assert settings.log_level == LogLevel.INFO


def test_settings_read_environment_variables(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = get_settings()

    assert settings.environment == Environment.PRODUCTION
    assert settings.log_level == LogLevel.WARNING


def test_invalid_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_ENV", "banana")

    with pytest.raises(
        ValueError,
        match="APP_ENV inválido",
    ):
        get_settings()


def test_invalid_log_level_is_rejected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "QUALQUER_COISA")

    with pytest.raises(
        ValueError,
        match="LOG_LEVEL inválido",
    ):
        get_settings()