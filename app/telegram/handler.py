from dataclasses import dataclass
from typing import AbstractSet


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: int
    text: str


def extract_command(text: str) -> str | None:
    if not text.startswith("/"):
        return None

    first_token = text.split(maxsplit=1)[0]
    command = first_token.split("@", maxsplit=1)[0]

    return command.lower()


def handle_update(
    update: dict,
    allowed_user_ids: AbstractSet[int],
) -> OutgoingMessage | None:
    message = update.get("message")

    if not isinstance(message, dict):
        return None

    sender = message.get("from")
    chat = message.get("chat")
    text = message.get("text")

    if not isinstance(sender, dict):
        return None

    if not isinstance(chat, dict):
        return None

    if not isinstance(text, str):
        return None

    user_id = sender.get("id")
    chat_id = chat.get("id")

    if not isinstance(user_id, int):
        return None

    if not isinstance(chat_id, int):
        return None

    if user_id not in allowed_user_ids:
        return None

    command = extract_command(text)

    if command == "/start":
        return OutgoingMessage(
            chat_id=chat_id,
            text=(
                "Investment Bot iniciado. "
                "Acesso autorizado."
            ),
        )

    if command == "/status":
        return OutgoingMessage(
            chat_id=chat_id,
            text="Investment Bot operacional.",
        )

    return None