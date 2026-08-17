import os
from dataclasses import dataclass
from enum import StrEnum


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


def get_settings() -> Settings:
    environment_raw = os.getenv("APP_ENV", "development").lower()
    log_level_raw = os.getenv("LOG_LEVEL", "INFO").upper()

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

    return Settings(
        environment=environment,
        log_level=log_level,
    )