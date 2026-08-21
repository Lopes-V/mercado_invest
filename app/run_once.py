"""One-shot scheduler entrypoint intended for GitHub Actions cron."""

from datetime import UTC, datetime

from app.bootstrap import build_application
from app.config.settings import get_settings
from app.monitoring.logger import configure_logging


def main() -> None:
    settings = get_settings()
    logger = configure_logging(settings)
    application = build_application(settings)
    try:
        result = application.scheduler.run_due(now=datetime.now(UTC))
        for failure in result.failures:
            logger.error(
                "Scheduled job failed [job=%s error=%s]",
                failure.job_name,
                failure.error.__class__.__name__,
            )
        if result.failures:
            raise SystemExit(1)
        logger.info(
            "Scheduled round completed [jobs=%d]",
            len(result.successes),
        )
    finally:
        application.close()


if __name__ == "__main__":
    main()
