import pytest

from app.config.settings import (
    Environment,
    LogLevel,
    get_settings,
    parse_telegram_allowed_user_ids,
)


def set_required_env(monkeypatch):
    monkeypatch.setenv(
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setenv(
        "SUPABASE_SECRET_KEY",
        "fake-secret",
    )
    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN",
        "fake-telegram-token",
    )
    monkeypatch.delenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        raising=False,
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

    set_required_env(monkeypatch)

    settings = get_settings()

    assert (
        settings.environment
        == Environment.DEVELOPMENT
    )
    assert settings.log_level == LogLevel.INFO
    assert (
        settings.telegram_allowed_user_ids
        == frozenset()
    )


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

    set_required_env(monkeypatch)

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

    set_required_env(monkeypatch)

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

    set_required_env(monkeypatch)

    with pytest.raises(
        ValueError,
        match="LOG_LEVEL inválido",
    ):
        get_settings()


def test_missing_supabase_url_is_rejected(
    monkeypatch,
):
    set_required_env(monkeypatch)

    monkeypatch.delenv(
        "SUPABASE_URL",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="SUPABASE_URL",
    ):
        get_settings()


def test_missing_supabase_secret_key_is_rejected(
    monkeypatch,
):
    set_required_env(monkeypatch)

    monkeypatch.delenv(
        "SUPABASE_SECRET_KEY",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="SUPABASE_SECRET_KEY",
    ):
        get_settings()


def test_missing_telegram_bot_token_is_rejected(
    monkeypatch,
):
    set_required_env(monkeypatch)

    monkeypatch.delenv(
        "TELEGRAM_BOT_TOKEN",
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="TELEGRAM_BOT_TOKEN",
    ):
        get_settings()


def test_empty_telegram_allowed_users_is_safe():
    result = parse_telegram_allowed_user_ids("")

    assert result == frozenset()


def test_telegram_allowed_users_parses_single_id():
    result = parse_telegram_allowed_user_ids(
        "123456789"
    )

    assert result == frozenset({
        123456789,
    })


def test_telegram_allowed_users_parses_multiple_ids():
    result = parse_telegram_allowed_user_ids(
        "123, 456,123"
    )

    assert result == frozenset({
        123,
        456,
    })


def test_invalid_telegram_allowed_user_is_rejected():
    with pytest.raises(
        ValueError,
        match="valor inválido",
    ):
        parse_telegram_allowed_user_ids(
            "123,banana"
        )


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
    ],
)
def test_non_positive_telegram_user_id_is_rejected(
    value,
):
    with pytest.raises(
        ValueError,
        match="IDs positivos",
    ):
        parse_telegram_allowed_user_ids(
            value
        )


def test_settings_read_telegram_allowed_users(
    monkeypatch,
):
    set_required_env(monkeypatch)

    monkeypatch.setenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        "123,456",
    )

    settings = get_settings()

    assert (
        settings.telegram_allowed_user_ids
        == frozenset({
            123,
            456,
        })
    )