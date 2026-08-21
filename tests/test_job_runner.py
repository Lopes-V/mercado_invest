import logging
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.database.models import JobRunRecord
from app.jobs.models import JobContext, JobResult, JobRunStatus, JobTrigger
from app.jobs.runner import JobRunner, build_scheduled_run_key


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
CORRELATION_ID = UUID("22222222-2222-2222-2222-222222222222")


def record(*, status=JobRunStatus.RUNNING, correlation_id=CORRELATION_ID, run_key="job:2026-08-21T12:00:00+00:00"):
    return JobRunRecord(RUN_ID, "job", run_key, JobTrigger.SCHEDULED, NOW, status, correlation_id, NOW, NOW if status is not JobRunStatus.RUNNING else None, None, None, NOW, NOW)


class Repository:
    def __init__(self, *, existing=None, start_error=None, finish_error=None):
        self.existing, self.start_error, self.finish_error = existing, start_error, finish_error
        self.started, self.finished = [], []
    def get_by_run_key(self, key): return self.existing
    def start_run(self, **kwargs):
        self.started.append(kwargs)
        if self.start_error: raise self.start_error
        return record(correlation_id=kwargs["correlation_id"], run_key=kwargs["run_key"])
    def finish_run(self, **kwargs):
        self.finished.append(kwargs)
        if self.finish_error: raise self.finish_error
        return record(status=kwargs["terminal_status"])


class DuplicateError(RuntimeError):
    code = "23505"
    constraint = "job_runs_run_key_unique"


class Job:
    name = "job"
    def __init__(self, *, error=None, result=JobResult(1)): self.error, self.result, self.contexts = error, result, []
    def execute(self, context):
        self.contexts.append(context)
        if self.error: raise self.error
        return self.result


def runner(repo):
    logger = logging.getLogger("jobs-test")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    return JobRunner(repo, logger=logger)


def test_scheduled_run_lifecycle_and_deterministic_key():
    repo, job = Repository(), Job()
    result = runner(repo).run(job, trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, started_at=NOW, correlation_id=CORRELATION_ID)
    assert build_scheduled_run_key("job", NOW) == "job:2026-08-21T12:00:00+00:00"
    assert result.run.status is JobRunStatus.SUCCEEDED and result.job_result == JobResult(1)
    assert result.already_executed is False
    assert repo.started[0]["correlation_id"] == CORRELATION_ID
    assert job.contexts[0] == JobContext(CORRELATION_ID, JobTrigger.SCHEDULED, NOW, NOW)
    assert repo.finished[0]["terminal_status"] is JobRunStatus.SUCCEEDED


def test_duplicate_scheduled_run_does_not_execute_job_or_insert():
    existing = record(status=JobRunStatus.SUCCEEDED)
    repo, job = Repository(existing=existing), Job()
    result = runner(repo).run(job, trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, started_at=NOW)
    assert result.already_executed is True and result.run is existing and result.job_result is None
    assert not job.contexts and not repo.started


def test_job_failure_is_recorded_sanitized_and_original_exception_propagates():
    error = RuntimeError("request failed Authorization: Bearer secret-token")
    repo, job = Repository(), Job(error=error)
    with pytest.raises(RuntimeError, match="secret-token"):
        runner(repo).run(job, trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, started_at=NOW)
    finished = repo.finished[0]
    assert finished["terminal_status"] is JobRunStatus.FAILED
    assert "secret-token" not in finished["error_message"]
    assert "Bearer [REDACTED]" in finished["error_message"]


def test_start_or_finish_repository_errors_are_not_hidden():
    with pytest.raises(RuntimeError, match="start"):
        runner(Repository(start_error=RuntimeError("start"))).run(Job(), trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, started_at=NOW)
    original = ValueError("job failed")
    with pytest.raises(ValueError, match="job failed"):
        runner(Repository(finish_error=RuntimeError("finish"))).run(Job(error=original), trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, started_at=NOW)


def test_manual_runs_use_explicit_or_generated_non_slot_run_key():
    repo = Repository()
    runner(repo).run(Job(), trigger=JobTrigger.MANUAL, scheduled_for=NOW, started_at=NOW, correlation_id=CORRELATION_ID, manual_run_key="manual-key")
    assert repo.started[0]["run_key"] == "manual-key"


def test_run_key_race_is_treated_as_duplicate_without_executing_job():
    existing = record(status=JobRunStatus.SUCCEEDED)
    repo, job = Repository(start_error=DuplicateError("duplicate")), Job()
    original_lookup = repo.get_by_run_key
    calls = 0
    def lookup(key):
        nonlocal calls
        calls += 1
        return None if calls == 1 else existing
    repo.get_by_run_key = lookup
    result = runner(repo).run(job, trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, started_at=NOW)
    assert result.already_executed is True and result.run is existing
    assert not job.contexts
