from app.config.settings import (
    Environment,
    LogLevel,
    Settings,
)
from app.database import client as client_module


def test_create_supabase_client_uses_settings(
    monkeypatch,
):
    settings = Settings(
    environment=Environment.TEST,
    log_level=LogLevel.INFO,
    supabase_url="https://example.supabase.co",
    supabase_secret_key="fake-secret",
    telegram_bot_token="fake-telegram-token",
    telegram_allowed_user_ids=frozenset(),
    )
    fake_client = object()

    def fake_create_client(url, key):
        assert url == settings.supabase_url
        assert key == settings.supabase_secret_key

        return fake_client

    monkeypatch.setattr(
        client_module,
        "create_client",
        fake_create_client,
    )

    result = client_module.create_supabase_client(
        settings
    )

    assert result is fake_client