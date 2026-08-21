import os
from dataclasses import dataclass, field
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
    supabase_secret_key: str = field(repr=False)

    telegram_bot_token: str = field(repr=False)
    telegram_allowed_user_ids: frozenset[int]
    brapi_token: str | None = None
    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str | None = None
    twelve_data_api_key: str | None = field(default=None, repr=False)
    market_quotes_enabled: bool = False
    market_quotes_interval_seconds: int = 300
    market_history_enabled: bool = False
    market_history_interval_seconds: int = 86400
    market_history_lookback_days: int = 30
    market_history_candle_interval: str = "1d"


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(
            f"Variável obrigatória ausente: {name}"
        )

    return value.strip()


def get_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
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


def _optional_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip(): return default
    if value.strip().lower() in {"1", "true", "yes"}: return True
    if value.strip().lower() in {"0", "false", "no"}: return False
    raise ValueError(f"{name} deve ser booleano")


def _positive_int(name: str, default: int) -> int:
    raw=os.getenv(name)
    if raw is None or not raw.strip(): return default
    try: value=int(raw)
    except ValueError as exc: raise ValueError(f"{name} deve ser inteiro") from exc
    if value<=0: raise ValueError(f"{name} deve ser positivo")
    return value


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
        brapi_token=get_optional_env("BRAPI_TOKEN"),
        openai_api_key=get_optional_env("OPENAI_API_KEY"),
        openai_model=get_optional_env("OPENAI_MODEL"),
        twelve_data_api_key=get_optional_env("TWELVE_DATA_API_KEY"),
        market_quotes_enabled=_optional_bool("MARKET_QUOTES_ENABLED", False),
        market_quotes_interval_seconds=_positive_int("MARKET_QUOTES_INTERVAL_SECONDS", 300),
        market_history_enabled=_optional_bool("MARKET_HISTORY_ENABLED", False),
        market_history_interval_seconds=_positive_int("MARKET_HISTORY_INTERVAL_SECONDS", 86400),
        market_history_lookback_days=_positive_int("MARKET_HISTORY_LOOKBACK_DAYS", 30),
        market_history_candle_interval=get_optional_env("MARKET_HISTORY_CANDLE_INTERVAL") or "1d",
    )
