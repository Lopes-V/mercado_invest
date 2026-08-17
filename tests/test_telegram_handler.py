from app.telegram.handler import (
    OutgoingMessage,
    extract_command,
    handle_update,
)


def create_update(
    user_id: int = 123,
    chat_id: int = 456,
    text: str = "/start",
) -> dict:
    return {
        "update_id": 1,
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


def test_extract_start_command():
    assert extract_command("/start") == "/start"


def test_extract_command_ignores_arguments():
    assert (
        extract_command("/start qualquer")
        == "/start"
    )


def test_extract_command_accepts_bot_suffix():
    assert (
        extract_command(
            "/start@investment_bot"
        )
        == "/start"
    )


def test_plain_text_is_not_command():
    assert extract_command("oi") is None


def test_authorized_start_returns_message():
    update = create_update(
        user_id=123,
        chat_id=456,
    )

    result = handle_update(
        update,
        allowed_user_ids={123},
    )

    assert result == OutgoingMessage(
        chat_id=456,
        text=(
            "Investment Bot iniciado. "
            "Acesso autorizado."
        ),
    )


def test_unauthorized_user_is_ignored():
    update = create_update(
        user_id=999,
    )

    result = handle_update(
        update,
        allowed_user_ids={123},
    )

    assert result is None


def test_unknown_command_is_ignored():
    update = create_update(
        text="/qualquer",
    )

    result = handle_update(
        update,
        allowed_user_ids={123},
    )

    assert result is None


def test_update_without_message_is_ignored():
    result = handle_update(
        {"update_id": 1},
        allowed_user_ids={123},
    )

    assert result is None


def test_message_without_text_is_ignored():
    update = {
        "update_id": 1,
        "message": {
            "from": {
                "id": 123,
            },
            "chat": {
                "id": 456,
            },
        },
    }

    result = handle_update(
        update,
        allowed_user_ids={123},
    )

    assert result is None