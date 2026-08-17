from app.config.settings import Settings
from app.telegram.client import TelegramClient
from app.telegram.service import poll_once


def run_bot_once(
    settings: Settings,
    offset: int | None = None,
) -> int | None:
    if not settings.telegram_allowed_user_ids:
        raise RuntimeError(
            "Telegram bot não pode iniciar "
            "sem usuários autorizados."
        )

    client = TelegramClient(
        settings.telegram_bot_token
    )

    try:
        return poll_once(
            client=client,
            allowed_user_ids=(
                settings.telegram_allowed_user_ids
            ),
            offset=offset,
        )

    finally:
        client.close()