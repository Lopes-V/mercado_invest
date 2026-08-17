import logging

from app.config.settings import (
    Environment,
    LogLevel,
    Settings,
)
from app.monitoring.logger import (
    LOGGER_NAME,
    configure_logging,
)


def create_settings(
    log_level: LogLevel = LogLevel.INFO,
) -> Settings:
    return Settings(
        environment=Environment.TEST,
        log_level=log_level,
    )


def test_logger_uses_expected_name():
    logger = configure_logging(create_settings())

    assert logger.name == LOGGER_NAME


def test_logger_uses_configured_level():
    logger = configure_logging(
        create_settings(LogLevel.ERROR)
    )

    assert logger.level == logging.ERROR


def test_logger_does_not_propagate():
    logger = configure_logging(create_settings())

    assert logger.propagate is False


def test_logger_has_only_one_handler():
    logger = configure_logging(create_settings())

    configure_logging(create_settings())

    assert len(logger.handlers) == 1


def test_logger_outputs_message(capsys):
    logger = configure_logging(create_settings())

    logger.info("mercado atualizado")

    captured = capsys.readouterr()

    assert "INFO" in captured.out
    assert "mercado atualizado" in captured.out
    assert LOGGER_NAME in captured.out