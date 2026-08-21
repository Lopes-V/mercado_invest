"""Long-running worker entrypoint for Docker or another persistent host."""

import signal
from threading import Event
from typing import Callable

from app.bootstrap import build_application
from app.config.settings import get_settings
from app.jobs.schedule import SchedulerService
from app.monitoring.logger import configure_logging


def run_worker(
    scheduler: SchedulerService,
    *,
    stop_event: Event | None = None,
    poll_interval_seconds: float = 30.0,
    close: Callable[[], None] | None = None,
) -> None:
    stop = stop_event or Event()
    previous = {
        sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)
    }

    def request_stop(_signum, _frame):
        stop.set()

    try:
        for sig in previous:
            signal.signal(sig, request_stop)
        scheduler.run_forever(
            poll_interval_seconds=poll_interval_seconds,
            should_stop=stop.is_set,
        )
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        if close is not None:
            close()


def main() -> None:
    settings = get_settings()
    logger = configure_logging(settings)
    application = build_application(settings)
    logger.info(
        "Investment worker iniciado [env=%s]",
        settings.environment.value,
    )
    run_worker(application.scheduler, close=application.close)


if __name__ == "__main__":
    main()
