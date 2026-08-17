import pytest

from app.config.settings import (
    Environment,
    LogLevel,
    Settings,
)
from app.telegram import runner


class FakeTelegramClient:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def create_settings(
    allowed_user_ids=frozenset({123}),
):
    return Settings(
        environment=Environment.TEST,
        log_level=LogLevel.INFO,
        supabase_url="https://example.supabase.co",
        supabase_secret_key="fake-secret",
        telegram_bot_token="fake-token",
        telegram_allowed_user_ids=allowed_user_ids,
    )


def test_runner_rejects_empty_whitelist():
    settings = create_settings(
        allowed_user_ids=frozenset(),
    )

    with pytest.raises(
        RuntimeError,
        match="sem usuários autorizados",
    ):
        runner.run_bot_once(settings)


def test_runner_processes_one_poll(
    monkeypatch,
):
    settings = create_settings()

    fake_client = FakeTelegramClient()

    monkeypatch.setattr(
        runner,
        "TelegramClient",
        lambda token: fake_client,
    )

    def fake_poll_once(
        client,
        allowed_user_ids,
        offset,
    ):
        assert client is fake_client
        assert (
            allowed_user_ids
            == frozenset({123})
        )
        assert offset == 50

        return 51

    monkeypatch.setattr(
        runner,
        "poll_once",
        fake_poll_once,
    )

    result = runner.run_bot_once(
        settings,
        offset=50,
    )

    assert result == 51
    assert fake_client.closed is True


def test_runner_closes_client_after_failure(
    monkeypatch,
):
    settings = create_settings()

    fake_client = FakeTelegramClient()

    monkeypatch.setattr(
        runner,
        "TelegramClient",
        lambda token: fake_client,
    )

    def fake_poll_once(
        client,
        allowed_user_ids,
        offset,
    ):
        raise RuntimeError(
            "falha simulada"
        )

    monkeypatch.setattr(
        runner,
        "poll_once",
        fake_poll_once,
    )

    with pytest.raises(
        RuntimeError,
        match="falha simulada",
    ):
        runner.run_bot_once(settings)

    assert fake_client.closed is True   