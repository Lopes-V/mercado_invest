from typing import AbstractSet

from app.telegram.client import TelegramClient
from app.telegram.service import poll_once


def poll_until_idle(
    client: TelegramClient,
    allowed_user_ids: AbstractSet[int],
    offset: int | None = None,
    timeout: int = 0,
    max_polls: int = 100,
) -> int | None:
    if max_polls <= 0:
        raise ValueError(
            "max_polls deve ser maior que zero."
        )

    current_offset = offset

    for _ in range(max_polls):
        next_offset = poll_once(
            client=client,
            allowed_user_ids=allowed_user_ids,
            offset=current_offset,
            timeout=timeout,
        )

        if next_offset == current_offset:
            return current_offset

        current_offset = next_offset

    return current_offset