from types import SimpleNamespace

import app.run_once as command
from app.jobs.schedule import SchedulerRoundResult


class Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message, *args):
        self.infos.append((message, args))

    def error(self, message, *args):
        self.errors.append((message, args))


def test_run_once_returns_success_when_quote_duplicate_was_ignored(monkeypatch):
    logger = Logger()
    application = SimpleNamespace(
        scheduler=SimpleNamespace(
            run_due=lambda **_kwargs: SchedulerRoundResult(
                successes=(SimpleNamespace(job_name="market_quotes:brapi"),),
                failures=(),
            )
        ),
        close=lambda: None,
    )
    monkeypatch.setattr(command, "get_settings", lambda: object())
    monkeypatch.setattr(command, "configure_logging", lambda _settings: logger)
    monkeypatch.setattr(command, "build_application", lambda _settings: application)

    command.main()

    assert logger.errors == []
    assert logger.infos == [("Scheduled round completed [jobs=%d]", (1,))]
