from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from app.jobs.errors import JobValidationError


class JobTrigger(StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class JobRunStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def ensure_utc_datetime(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise JobValidationError(f"{field} deve ser datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise JobValidationError(f"{field} deve possuir timezone")
    return value.astimezone(UTC)


def ensure_job_name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JobValidationError("job_name não pode ser vazio")
    return value


@dataclass(frozen=True, slots=True)
class JobContext:
    correlation_id: UUID
    trigger: JobTrigger
    scheduled_for: datetime
    started_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.correlation_id, UUID):
            raise JobValidationError("correlation_id deve ser UUID")
        if not isinstance(self.trigger, JobTrigger):
            raise JobValidationError("trigger deve ser JobTrigger")
        object.__setattr__(
            self,
            "scheduled_for",
            ensure_utc_datetime(self.scheduled_for, field="scheduled_for"),
        )
        object.__setattr__(
            self,
            "started_at",
            ensure_utc_datetime(self.started_at, field="started_at"),
        )


@dataclass(frozen=True, slots=True)
class JobResult:
    processed_count: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.processed_count, bool)
            or not isinstance(self.processed_count, int)
            or self.processed_count < 0
        ):
            raise JobValidationError("processed_count deve ser inteiro não negativo")
