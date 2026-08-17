import pytest

from app.config.settings import (
    Environment,
    LogLevel,
    get_settings,
)


def set_supabase_env(monkeypatch):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SECRET_KEY",
        "fake-secret",
    )


def test_settings_use_default_values(monkeypatch):
    monkeypatch.delenv(
        "APP_ENV",
        raising=False,
    )
    monkeypatch.delenv(
        "LOG_LEVEL",
        raising=False,
    )

    set_supabase_env(monkeypatch)

    settings = get_settings()

    assert (
        settings.environment
        == Environment.DEVELOPMENT
    )
    assert settings.log_level == LogLevel.INFO


def test_settings_read_environment_variables(
    monkeypatch,
):
    monkeypatch.setenv(
        "APP_ENV",
        "production",
    )
    monkeypatch.setenv(
        "LOG_LEVEL",
        "WARNING",
    )

    set_supabase_env(monkeypatch)

    settings = get_settings()

    assert (
        settings.environment
        == Environment.PRODUCTION
    )
    assert settings.log_level == LogLevel.WARNING


def test_invalid_environment_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "APP_ENV",
        "banana",
    )

    set_supabase_env(monkeypatch)

    with pytest.raises(
        ValueError,
        match="APP_ENV inválido",
    ):
        get_settings()


def test_invalid_log_level_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "LOG_LEVEL",
        "QUALQUER_COISA",
    )

    set_supabase_env(monkeypatch)

    with pytest.raises(
        ValueError,
        match="LOG_LEVEL inválido",
    ):
        get_settings()


def test_missing_supabase_url_is_rejected(
    monkeypatch,
):
    monkeypatch.delenv(
        "SUPABASE_URL",
        raising=False,
    )
    monkeypatch.setenv(
        "SUPABASE_SECRET_KEY",
        "fake-secret",
    )

    with pytest.raises(
        ValueError,
        match="SUPABASE_URL",
    ):
        get_settings()


def test_missing_supabase_secret_key_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.delenv(
        "SUPABASE_SECRET_KEY",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="SUPABASE_SECRET_KEY",
    ):
        get_settings()