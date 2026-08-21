from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.jobs.errors import JobScheduleError
from app.jobs.schedule import IntervalSchedule, ScheduledJob, SchedulerService


ANCHOR = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


class Job:
    def __init__(self, name): self._name = name
    @property
    def name(self): return self._name
    def execute(self, context): raise AssertionError("runner owns execution")


class Runner:
    def __init__(self, failures=()): self.calls, self.failures = [], set(failures)
    def run(self, job, **kwargs):
        self.calls.append((job.name, kwargs))
        if job.name in self.failures: raise RuntimeError(job.name)
        return SimpleNamespace(run=SimpleNamespace(id=job.name), already_executed=False)


def scheduled(name, *, anchor=ANCHOR):
    return ScheduledJob(Job(name), IntervalSchedule(timedelta(minutes=5), anchor))


def test_scheduler_runs_due_jobs_in_registration_order_and_latest_slot_only():
    runner = Runner()
    service = SchedulerService(runner, (scheduled("first"), scheduled("second")))
    result = service.run_due(now=ANCHOR + timedelta(minutes=16))
    assert [call[0] for call in runner.calls] == ["first", "second"]
    assert all(call[1]["scheduled_for"] == ANCHOR + timedelta(minutes=15) for call in runner.calls)
    assert len(result.successes) == 2 and not result.failures


def test_scheduler_ignores_not_due_and_collects_failure_without_stopping():
    runner = Runner(failures=("broken",))
    service = SchedulerService(runner, (scheduled("future", anchor=ANCHOR + timedelta(hours=1)), scheduled("broken"), scheduled("after")))
    result = service.run_due(now=ANCHOR)
    assert [call[0] for call in runner.calls] == ["broken", "after"]
    assert len(result.failures) == 1 and result.failures[0].job_name == "broken"


def test_scheduler_delegates_same_slot_idempotency_to_runner():
    runner = Runner()
    service = SchedulerService(runner, (scheduled("one"),))
    service.run_due(now=ANCHOR)
    service.run_due(now=ANCHOR)
    assert len(runner.calls) == 2
    assert runner.calls[0][1]["scheduled_for"] == runner.calls[1][1]["scheduled_for"] == ANCHOR


def test_run_forever_uses_injected_clock_sleep_and_safe_stop():
    runner, sleeps, states = Runner(), [], iter((False, True))
    service = SchedulerService(runner, (scheduled("one"),))
    rounds = service.run_forever(poll_interval_seconds=1, should_stop=lambda: next(states), clock=lambda: ANCHOR, sleep=sleeps.append)
    assert len(rounds) == 1 and sleeps == []


def test_run_forever_calls_injected_sleep_between_rounds():
    runner, sleeps = Runner(), []
    stop_checks = iter((False, False, False, True))
    service = SchedulerService(runner, (scheduled("one"),))
    rounds = service.run_forever(poll_interval_seconds=2, should_stop=lambda: next(stop_checks), clock=lambda: ANCHOR, sleep=sleeps.append)
    assert len(rounds) == 2 and sleeps == [2.0]


@pytest.mark.parametrize("interval", [0, -1, float("inf")])
def test_run_forever_rejects_invalid_poll_interval(interval):
    with pytest.raises(JobScheduleError):
        SchedulerService(Runner(), ()).run_forever(poll_interval_seconds=interval, should_stop=lambda: True)
