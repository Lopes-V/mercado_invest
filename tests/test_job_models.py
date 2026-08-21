from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.jobs.errors import JobValidationError
from app.jobs.models import JobContext, JobResult, JobRunStatus, JobTrigger


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
CORRELATION_ID = UUID("11111111-1111-1111-1111-111111111111")


def test_job_context_normalizes_aware_timestamps_to_utc():
    context = JobContext(
        CORRELATION_ID,
        JobTrigger.SCHEDULED,
        NOW.astimezone(timezone(timedelta(hours=-3))),
        NOW,
    )
    assert context.scheduled_for == NOW
    assert context.started_at == NOW


@pytest.mark.parametrize("value", [datetime(2026, 8, 21, 12, 0), "now"])
def test_job_context_rejects_naive_or_invalid_timestamp(value):
    with pytest.raises(JobValidationError):
        JobContext(CORRELATION_ID, JobTrigger.MANUAL, value, NOW)


def test_job_result_and_enums():
    assert JobResult().processed_count == 0
    assert JobResult(2).processed_count == 2
    assert JobTrigger.SCHEDULED.value == "SCHEDULED"
    assert {item.value for item in JobRunStatus} == {
        "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED"
    }


@pytest.mark.parametrize("count", [-1, 1.0, True])
def test_job_result_rejects_invalid_processed_count(count):
    with pytest.raises(JobValidationError):
        JobResult(count)
