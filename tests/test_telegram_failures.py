import httpx
import pytest

from app.telegram.client import TelegramClient
from app.telegram.poller import poll_until_idle


class FailingReadClient:
    def __init__(self):
        self.get_updates_calls = 0

    def get_updates(
        self,
        offset=None,
        timeout=30,
        limit=100,
    ):
        self.get_updates_calls += 1

        raise RuntimeError(
            "falha simulada na leitura"
        )


class FailingSendClient:
    def __init__(self):
        self.get_updates_calls = 0
        self.send_message_calls = 0

    def get_updates(
        self,
        offset=None,
        timeout=30,
        limit=100,
    ):
        self.get_updates_calls += 1

        return [
            {
                "update_id": 100,
                "message": {
                    "from": {
                        "id": 123,
                    },
                    "chat": {
                        "id": 500,
                    },
                    "text": "/status",
                },
            }
        ]

    def send_message(
        self,
        chat_id,
        text,
    ):
        self.send_message_calls += 1

        raise RuntimeError(
            "falha simulada no envio"
        )


def test_client_propagates_network_failure(
    monkeypatch,
):
    client = TelegramClient(
        token="fake-token"
    )

    def fake_get(url):
        request = httpx.Request(
            "GET",
            url,
        )

        raise httpx.ConnectError(
            "network unavailable",
            request=request,
        )

    monkeypatch.setattr(
        client._client,
        "get",
        fake_get,
    )

    try:
        with pytest.raises(
            httpx.ConnectError
        ):
            client.get_me()
    finally:
        client.close()


def test_client_propagates_http_error(
    monkeypatch,
):
    client = TelegramClient(
        token="fake-token"
    )

    def fake_get(url):
        request = httpx.Request(
            "GET",
            url,
        )

        return httpx.Response(
            status_code=401,
            request=request,
        )

    monkeypatch.setattr(
        client._client,
        "get",
        fake_get,
    )

    try:
        with pytest.raises(
            httpx.HTTPStatusError
        ):
            client.get_me()
    finally:
        client.close()


def test_poller_propagates_read_failure():
    client = FailingReadClient()

    with pytest.raises(
        RuntimeError,
        match="falha simulada na leitura",
    ):
        poll_until_idle(
            client=client,
            allowed_user_ids={123},
        )

    assert client.get_updates_calls == 1


def test_poller_stops_on_send_failure():
    client = FailingSendClient()

    with pytest.raises(
        RuntimeError,
        match="falha simulada no envio",
    ):
        poll_until_idle(
            client=client,
            allowed_user_ids={123},
        )

    assert client.get_updates_calls == 1
    assert client.send_message_calls == 1