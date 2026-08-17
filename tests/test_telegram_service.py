import pytest

from app.telegram.service import poll_once


class FakeTelegramClient:
    def __init__(
        self,
        updates: list[dict],
        fail_send: bool = False,
    ):
        self.updates = updates
        self.fail_send = fail_send

        self.get_updates_calls = []
        self.sent_messages = []

    def get_updates(
        self,
        offset=None,
        timeout=30,
        limit=100,
    ):
        self.get_updates_calls.append(
            {
                "offset": offset,
                "timeout": timeout,
                "limit": limit,
            }
        )

        return self.updates

    def send_message(
        self,
        chat_id: int,
        text: str,
    ):
        if self.fail_send:
            raise RuntimeError(
                "falha simulada"
            )

        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
            }
        )

        return {
            "message_id": 1,
        }


def create_start_update(
    update_id: int = 100,
    user_id: int = 123,
    chat_id: int = 456,
) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "from": {
                "id": user_id,
            },
            "chat": {
                "id": chat_id,
            },
            "text": "/start",
        },
    }


def test_poll_once_without_updates_keeps_offset():
    client = FakeTelegramClient(
        updates=[],
    )

    result = poll_once(
        client,
        allowed_user_ids={123},
        offset=50,
    )

    assert result == 50

    assert client.sent_messages == []


def test_poll_once_requests_only_one_update():
    client = FakeTelegramClient(
        updates=[],
    )

    poll_once(
        client,
        allowed_user_ids={123},
        offset=50,
        timeout=20,
    )

    assert client.get_updates_calls == [
        {
            "offset": 50,
            "timeout": 20,
            "limit": 1,
        }
    ]


def test_authorized_start_is_answered():
    client = FakeTelegramClient(
        updates=[
            create_start_update(),
        ]
    )

    result = poll_once(
        client,
        allowed_user_ids={123},
    )

    assert result == 101

    assert client.sent_messages == [
        {
            "chat_id": 456,
            "text": (
                "Investment Bot iniciado. "
                "Acesso autorizado."
            ),
        }
    ]


def test_unauthorized_user_is_not_answered():
    client = FakeTelegramClient(
        updates=[
            create_start_update(
                user_id=999,
            ),
        ]
    )

    result = poll_once(
        client,
        allowed_user_ids={123},
    )

    assert result == 101
    assert client.sent_messages == []


def test_invalid_update_id_is_rejected():
    client = FakeTelegramClient(
        updates=[
            {
                "update_id": "errado",
            },
        ]
    )

    with pytest.raises(
        ValueError,
        match="update_id",
    ):
        poll_once(
            client,
            allowed_user_ids={123},
        )


def test_send_failure_is_not_hidden():
    client = FakeTelegramClient(
        updates=[
            create_start_update(),
        ],
        fail_send=True,
    )

    with pytest.raises(
        RuntimeError,
        match="falha simulada",
    ):
        poll_once(
            client,
            allowed_user_ids={123},
        )