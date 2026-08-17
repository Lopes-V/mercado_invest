import pytest

from app.telegram.poller import poll_until_idle


class FakeTelegramClient:
    def __init__(self, updates):
        self.updates = updates
        self.sent_messages = []
        self.get_updates_calls = []

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

        available = [
            update
            for update in self.updates
            if (
                offset is None
                or update["update_id"] >= offset
            )
        ]

        return available[:limit]

    def send_message(
        self,
        chat_id,
        text,
    ):
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
            }
        )

        return {
            "chat": {
                "id": chat_id,
            },
            "text": text,
        }


def create_update(
    update_id,
    user_id,
    chat_id,
    text,
):
    return {
        "update_id": update_id,
        "message": {
            "from": {
                "id": user_id,
            },
            "chat": {
                "id": chat_id,
            },
            "text": text,
        },
    }


def test_poller_processes_multiple_updates_in_order():
    client = FakeTelegramClient(
        updates=[
            create_update(
                100,
                123,
                500,
                "/start",
            ),
            create_update(
                101,
                123,
                500,
                "/status",
            ),
        ]
    )

    offset = poll_until_idle(
        client=client,
        allowed_user_ids={123},
    )

    assert offset == 102

    assert client.sent_messages == [
        {
            "chat_id": 500,
            "text": (
                "Investment Bot iniciado. "
                "Acesso autorizado."
            ),
        },
        {
            "chat_id": 500,
            "text": (
                "Investment Bot operacional."
            ),
        },
    ]

    assert [
        call["offset"]
        for call in client.get_updates_calls
    ] == [
        None,
        101,
        102,
    ]


def test_poller_does_not_reprocess_old_update():
    client = FakeTelegramClient(
        updates=[
            create_update(
                100,
                123,
                500,
                "/start",
            ),
            create_update(
                101,
                123,
                500,
                "/status",
            ),
        ]
    )

    offset = poll_until_idle(
        client=client,
        allowed_user_ids={123},
        offset=101,
    )

    assert offset == 102

    assert client.sent_messages == [
        {
            "chat_id": 500,
            "text": (
                "Investment Bot operacional."
            ),
        }
    ]


def test_poller_stops_when_queue_is_empty():
    client = FakeTelegramClient(
        updates=[]
    )

    offset = poll_until_idle(
        client=client,
        allowed_user_ids={123},
        offset=50,
    )

    assert offset == 50
    assert len(client.get_updates_calls) == 1
    assert client.sent_messages == []


def test_poller_advances_after_unauthorized_update():
    client = FakeTelegramClient(
        updates=[
            create_update(
                200,
                999,
                500,
                "/start",
            ),
        ]
    )

    offset = poll_until_idle(
        client=client,
        allowed_user_ids={123},
    )

    assert offset == 201
    assert client.sent_messages == []


def test_poller_respects_max_polls():
    client = FakeTelegramClient(
        updates=[
            create_update(
                300,
                123,
                500,
                "/status",
            ),
            create_update(
                301,
                123,
                500,
                "/status",
            ),
            create_update(
                302,
                123,
                500,
                "/status",
            ),
        ]
    )

    offset = poll_until_idle(
        client=client,
        allowed_user_ids={123},
        max_polls=2,
    )

    assert offset == 302

    assert len(
        client.sent_messages
    ) == 2


def test_poller_rejects_invalid_max_polls():
    client = FakeTelegramClient(
        updates=[]
    )

    with pytest.raises(
        ValueError,
        match="maior que zero",
    ):
        poll_until_idle(
            client=client,
            allowed_user_ids={123},
            max_polls=0,
        )