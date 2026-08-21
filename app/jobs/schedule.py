from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from time import sleep as default_sleep
from typing import TYPE_CHECKING

from app.jobs.contracts import Job
from app.jobs.errors import JobScheduleError
from app.jobs.models import JobTrigger, ensure_job_name, ensure_utc_datetime

if TYPE_CHECKING:
    from app.jobs.runner import JobRunner, JobRunnerResult


@dataclass(frozen=True, slots=True)
class IntervalSchedule:
    every: timedelta
    anchor: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.every, timedelta) or self.every <= timedelta():
            raise JobScheduleError("every deve ser timedelta positivo")
        object.__setattr__(
            self, "anchor", ensure_utc_datetime(self.anchor, field="anchor")
        )

    def slot_at_or_before(self, now: datetime) -> datetime | None:
        normalized_now = ensure_utc_datetime(now, field="now")
        if normalized_now < self.anchor:
            return None
        elapsed = normalized_now - self.anchor
        slots = elapsed // self.every
        return self.anchor + slots * self.every


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    job: Job
    schedule: IntervalSchedule

    def __post_init__(self) -> None:
        if not isinstance(self.job, Job):
            raise JobScheduleError("job deve implementar Job")
        ensure_job_name(self.job.name)
        if not isinstance(self.schedule, IntervalSchedule):
            raise JobScheduleError("schedule deve ser IntervalSchedule")


@dataclass(frozen=True, slots=True)
class SchedulerFailure:
    job_name: str
    error: Exception


@dataclass(frozen=True, slots=True)
class SchedulerRoundResult:
    successes: tuple["JobRunnerResult", ...]
    failures: tuple[SchedulerFailure, ...]


class SchedulerService:
    """Single-process, latest-slot-only scheduler without hidden time."""

    def __init__(self, runner: "JobRunner", jobs: Sequence[ScheduledJob]) -> None:
        self._runner = runner
        self._jobs = tuple(jobs)
        if not all(isinstance(job, ScheduledJob) for job in self._jobs):
            raise JobScheduleError("jobs deve conter ScheduledJob")

    def run_due(self, *, now: datetime) -> SchedulerRoundResult:
        normalized_now = ensure_utc_datetime(now, field="now")
        successes: list[JobRunnerResult] = []
        failures: list[SchedulerFailure] = []
        for scheduled_job in self._jobs:
            slot = scheduled_job.schedule.slot_at_or_before(normalized_now)
            if slot is None:
                continue
            try:
                successes.append(
                    self._runner.run(
                        scheduled_job.job,
                        trigger=JobTrigger.SCHEDULED,
                        scheduled_for=slot,
                        started_at=normalized_now,
                    )
                )
            except Exception as exc:
                failures.append(SchedulerFailure(scheduled_job.job.name, exc))
        return SchedulerRoundResult(tuple(successes), tuple(failures))

    def run_forever(
        self,
        *,
        poll_interval_seconds: float,
        should_stop: Callable[[], bool],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], None] = default_sleep,
    ) -> tuple[SchedulerRoundResult, ...]:
        if (
            isinstance(poll_interval_seconds, bool)
            or not isinstance(poll_interval_seconds, (int, float))
            or not isfinite(poll_interval_seconds)
            or poll_interval_seconds <= 0
        ):
            raise JobScheduleError("poll_interval_seconds deve ser positivo")
        if not callable(should_stop) or not callable(clock) or not callable(sleep):
            raise JobScheduleError("should_stop, clock e sleep devem ser chamáveis")
        rounds: list[SchedulerRoundResult] = []
        while not should_stop():
            rounds.append(self.run_due(now=clock()))
            if should_stop():
                break
            sleep(float(poll_interval_seconds))
        return tuple(rounds)
