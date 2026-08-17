from app.config.settings import get_settings
from app.monitoring.logger import configure_logging


def main() -> None:
    settings = get_settings()

    logger = configure_logging(settings)

    logger.info(
        "Investment Bot iniciado [env=%s]",
        settings.environment.value,
    )


if __name__ == "__main__":
    main()