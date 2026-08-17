from app.config.settings import get_settings
from app.telegram.client import TelegramClient


def main() -> None:
    client = None

    try:
        settings = get_settings()

        client = TelegramClient(
            settings.telegram_bot_token
        )

        bot = client.get_me()

    except Exception as exc:
        print(
            "Telegram connection: FAILED "
            f"[{type(exc).__name__}]"
        )

        raise SystemExit(1) from None

    finally:
        if client is not None:
            client.close()

    print(
        "Telegram connection: OK "
        f"[bot=@{bot['username']}]"
    )


if __name__ == "__main__":
    main()