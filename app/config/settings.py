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


def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(
            f"Variável obrigatória ausente: {name}"
        )

    return value.strip()


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
        environment = Environment(environment_raw)
    except ValueError as exc:
        raise ValueError(
            f"APP_ENV inválido: {environment_raw}"
        ) from exc

    try:
        log_level = LogLevel(log_level_raw)
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

    return Settings(
        environment=environment,
        log_level=log_level,
        supabase_url=supabase_url,
        supabase_secret_key=supabase_secret_key,
    )