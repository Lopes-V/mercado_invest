from app.telegram.client import TelegramClient


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response

        self.requested_url = None
        self.requested_params = None
        self.posted_url = None
        self.posted_json = None

        self.closed = False

    def get(
        self,
        url,
        params=None,
    ):
        self.requested_url = url
        self.requested_params = params

        return self.response

    def post(
        self,
        url,
        json=None,
    ):
        self.posted_url = url
        self.posted_json = json

        return self.response

    def close(self):
        self.closed = True


def create_client_with_fake_http(payload):
    client = TelegramClient(
        "fake-token"
    )

    fake_http = FakeHttpClient(
        FakeResponse(payload)
    )

    client._client.close()
    client._client = fake_http

    return client, fake_http


def test_get_me_returns_bot_data():
    client, fake_http = (
        create_client_with_fake_http(
            {
                "ok": True,
                "result": {
                    "id": 123,
                    "username": "investment_bot",
                },
            }
        )
    )

    result = client.get_me()

    assert result["id"] == 123
    assert (
        result["username"]
        == "investment_bot"
    )

    assert (
        fake_http.requested_url
        == (
            "https://api.telegram.org/"
            "botfake-token/getMe"
        )
    )


def test_get_me_rejects_invalid_payload():
    client, _ = create_client_with_fake_http(
        {
            "ok": False,
        }
    )

    try:
        client.get_me()
        assert False

    except RuntimeError as exc:
        assert (
            "Telegram rejeitou"
            in str(exc)
        )


def test_get_updates_returns_updates():
    client, fake_http = (
        create_client_with_fake_http(
            {
                "ok": True,
                "result": [
                    {
                        "update_id": 10,
                    },
                ],
            }
        )
    )

    result = client.get_updates(
        offset=10,
        timeout=20,
        limit=1,
    )

    assert result == [
        {
            "update_id": 10,
        }
    ]

    assert fake_http.requested_params == {
    "offset": 10,
    "timeout": 20,
    "limit": 1,
    }

def test_get_updates_rejects_invalid_limit():
    client = TelegramClient(
        "fake-token"
    )

    try:
        client.get_updates(
            limit=0,
        )

        assert False

    except ValueError as exc:
        assert "limit" in str(exc)

    finally:
        client.close()
        
def test_send_message_uses_chat_and_text():
    client, fake_http = (
        create_client_with_fake_http(
            {
                "ok": True,
                "result": {
                    "message_id": 1,
                },
            }
        )
    )

    result = client.send_message(
        chat_id=456,
        text="teste",
    )

    assert result["message_id"] == 1

    assert fake_http.posted_json == {
        "chat_id": 456,
        "text": "teste",
    }


def test_close_closes_http_client():
    client, fake_http = (
        create_client_with_fake_http(
            {
                "ok": True,
            }
        )
    )

    client.close()

    assert fake_http.closed is True