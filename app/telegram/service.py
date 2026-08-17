from app.telegram.client import TelegramClient
from app.telegram.handler import handle_update
from typing import AbstractSet

def poll_once(
    client: TelegramClient,
    allowed_user_ids: AbstractSet[int],
    offset: int | None = None,
    timeout: int = 30,
) -> int | None:
    updates = client.get_updates(
        offset=offset,
        timeout=timeout,
        limit=1,
    )

    if not updates:
        return offset

    update = updates[0]

    update_id = update.get(
        "update_id"
    )

    if not isinstance(
        update_id,
        int,
    ):
        raise ValueError(
            "Update do Telegram sem "
            "update_id válido."
        )

    outgoing = handle_update(
        update,
        allowed_user_ids,
    )

    if outgoing is not None:
        client.send_message(
            chat_id=outgoing.chat_id,
            text=outgoing.text,
        )

    return update_id + 1