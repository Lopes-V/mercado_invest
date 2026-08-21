import logging
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.database.models import JobRunRecord
from app.database.repositories.jobs import JobRunRepository
from app.jobs.contracts import Job
from app.jobs.errors import JobRunnerError
from app.jobs.models import JobContext, JobResult, JobRunStatus, JobTrigger, ensure_job_name, ensure_utc_datetime
from app.monitoring.logger import get_logger


_BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s,;]+")
_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b(token|secret|api[_ -]?key)\s*=\s*[^\s,;]+"
)
_MAX_ERROR_MESSAGE_LENGTH = 1000


def build_scheduled_run_key(job_name: str, scheduled_for: datetime) -> str:
    ensure_job_name(job_name)
    slot = ensure_utc_datetime(scheduled_for, field="scheduled_for")
    return f"{job_name}:{slot.isoformat()}"


def sanitize_error_message(error: Exception) -> str:
    message = str(error)
    message = _BEARER_RE.sub(r"\1[REDACTED]", message)
    message = _ASSIGNMENT_SECRET_RE.sub(r"\1=[REDACTED]", message)
    return message[:_MAX_ERROR_MESSAGE_LENGTH] or error.__class__.__name__


@dataclass(frozen=True, slots=True)
class JobRunnerResult:
    run: JobRunRecord
    job_result: JobResult | None
    already_executed: bool


class JobRunner:
    def __init__(self, repository: JobRunRepository, *, logger: logging.Logger | None = None) -> None:
        self._repository = repository
        self._logger = logger or get_logger()

    def run(self, job: Job, *, trigger: JobTrigger, scheduled_for: datetime, started_at: datetime, correlation_id: UUID | None = None, manual_run_key: str | None = None) -> JobRunnerResult:
        if not isinstance(job, Job):
            raise JobRunnerError("job deve implementar Job")
        job_name = ensure_job_name(job.name)
        if not isinstance(trigger, JobTrigger):
            raise JobRunnerError("trigger deve ser JobTrigger")
        slot = ensure_utc_datetime(scheduled_for, field="scheduled_for")
        started = ensure_utc_datetime(started_at, field="started_at")
        correlation = correlation_id or uuid4()
        if not isinstance(correlation, UUID):
            raise JobRunnerError("correlation_id deve ser UUID")
        run_key = self._run_key(job_name, trigger, slot, correlation, manual_run_key)
        existing = self._repository.get_by_run_key(run_key)
        if existing is not None:
            self._logger.info("job_skipped_duplicate job_name=%s correlation_id=%s scheduled_for=%s run_id=%s", job_name, correlation, slot.isoformat(), existing.id)
            return JobRunnerResult(existing, None, True)
        try:
            run = self._repository.start_run(job_name=job_name, run_key=run_key, trigger=trigger, scheduled_for=slot, correlation_id=correlation, started_at=started)
        except Exception as exc:
            duplicate = self._duplicate_run(run_key, exc)
            if duplicate is not None:
                return duplicate
            raise
        self._logger.info("job_started job_name=%s correlation_id=%s scheduled_for=%s run_id=%s", job_name, correlation, slot.isoformat(), run.id)
        context = JobContext(correlation, trigger, slot, started)
        try:
            result = job.execute(context)
            if not isinstance(result, JobResult):
                raise JobRunnerError("job.execute deve retornar JobResult")
        except Exception as exc:
            self._finish_failed(run=run, job_name=job_name, correlation_id=correlation, scheduled_for=slot, finished_at=started, error=exc)
            raise
        finished = self._repository.finish_run(run_id=run.id, terminal_status=JobRunStatus.SUCCEEDED, finished_at=started)
        self._logger.info("job_succeeded job_name=%s correlation_id=%s scheduled_for=%s run_id=%s", job_name, correlation, slot.isoformat(), finished.id)
        return JobRunnerResult(finished, result, False)

    def _run_key(self, job_name: str, trigger: JobTrigger, scheduled_for: datetime, correlation_id: UUID, manual_run_key: str | None) -> str:
        if trigger is JobTrigger.SCHEDULED:
            if manual_run_key is not None:
                raise JobRunnerError("manual_run_key não se aplica a execução agendada")
            return build_scheduled_run_key(job_name, scheduled_for)
        if manual_run_key is not None:
            if not isinstance(manual_run_key, str) or not manual_run_key.strip():
                raise JobRunnerError("manual_run_key não pode ser vazio")
            return manual_run_key
        return f"{job_name}:manual:{correlation_id}"

    def _duplicate_run(self, run_key: str, error: Exception) -> JobRunnerResult | None:
        code = getattr(error, "code", None)
        constraint = getattr(error, "constraint", None)
        if code != "23505" or constraint != "job_runs_run_key_unique":
            return None
        existing = self._repository.get_by_run_key(run_key)
        if existing is None:
            raise JobRunnerError("duplicata de run_key sem registro recuperável") from error
        self._logger.info("job_skipped_duplicate job_name=%s correlation_id=%s scheduled_for=%s run_id=%s", existing.job_name, existing.correlation_id, existing.scheduled_for.isoformat(), existing.id)
        return JobRunnerResult(existing, None, True)

    def _finish_failed(self, *, run: JobRunRecord, job_name: str, correlation_id: UUID, scheduled_for: datetime, finished_at: datetime, error: Exception) -> None:
        message = sanitize_error_message(error)
        try:
            finished = self._repository.finish_run(run_id=run.id, terminal_status=JobRunStatus.FAILED, finished_at=finished_at, error_code=error.__class__.__name__, error_message=message)
        except Exception as finish_error:
            self._logger.error("job_failed job_name=%s correlation_id=%s scheduled_for=%s run_id=%s error_code=%s error_message=%s finish_error_code=%s", job_name, correlation_id, scheduled_for.isoformat(), run.id, error.__class__.__name__, message, finish_error.__class__.__name__)
            return
        self._logger.error("job_failed job_name=%s correlation_id=%s scheduled_for=%s run_id=%s error_code=%s error_message=%s", job_name, correlation_id, scheduled_for.isoformat(), finished.id, error.__class__.__name__, message)
