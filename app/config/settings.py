import os
from dataclasses import dataclass
from enum import StrEnum

from dotenv import load_dotenv


load_dotenv()


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class Settings:
    environment: Environment
    log_level: LogLevel

    supabase_url: str
    supabase_secret_key: str

    telegram_bot_token: str
    telegram_allowed_user_ids: frozenset[int]


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(
            f"Variável obrigatória ausente: {name}"
        )

    return value.strip()


def parse_telegram_allowed_user_ids(
    raw: str | None,
) -> frozenset[int]:
    if raw is None or not raw.strip():
        return frozenset()

    user_ids: set[int] = set()

    for item in raw.split(","):
        value = item.strip()

        try:
            user_id = int(value)
        except ValueError as exc:
            raise ValueError(
                "TELEGRAM_ALLOWED_USER_IDS contém "
                f"valor inválido: {value}"
            ) from exc

        if user_id <= 0:
            raise ValueError(
                "TELEGRAM_ALLOWED_USER_IDS deve "
                "conter apenas IDs positivos."
            )

        user_ids.add(user_id)

    return frozenset(user_ids)


def get_settings() -> Settings:
    environment_raw = os.getenv(
        "APP_ENV",
        "development",
    ).lower()

    log_level_raw = os.getenv(
        "LOG_LEVEL",
        "INFO",
    ).upper()

    try:
        environment = Environment(
            environment_raw
        )
    except ValueError as exc:
        raise ValueError(
            f"APP_ENV inválido: {environment_raw}"
        ) from exc

    try:
        log_level = LogLevel(
            log_level_raw
        )
    except ValueError as exc:
        raise ValueError(
            f"LOG_LEVEL inválido: {log_level_raw}"
        ) from exc

    supabase_url = get_required_env(
        "SUPABASE_URL"
    )

    supabase_secret_key = get_required_env(
        "SUPABASE_SECRET_KEY"
    )

    telegram_bot_token = get_required_env(
        "TELEGRAM_BOT_TOKEN"
    )

    telegram_allowed_user_ids = (
        parse_telegram_allowed_user_ids(
            os.getenv(
                "TELEGRAM_ALLOWED_USER_IDS",
                "",
            )
        )
    )

    return Settings(
        environment=environment,
        log_level=log_level,

        supabase_url=supabase_url,
        supabase_secret_key=supabase_secret_key,

        telegram_bot_token=telegram_bot_token,
        telegram_allowed_user_ids=(
            telegram_allowed_user_ids
        ),
    )