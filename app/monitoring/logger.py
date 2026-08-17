import logging
import sys

from app.config.settings import LogLevel, Settings


LOGGER_NAME = "investment_bot"


def configure_logging(settings: Settings) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)

    logger.setLevel(
        getattr(logging, settings.log_level.value)
    )

    logger.propagate = False

    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)