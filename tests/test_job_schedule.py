from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.jobs.errors import JobScheduleError, JobValidationError
from app.jobs.schedule import IntervalSchedule


ANCHOR = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)


def test_interval_schedule_returns_deterministic_slots_without_drift():
    schedule = IntervalSchedule(timedelta(minutes=5), ANCHOR)
    assert schedule.slot_at_or_before(ANCHOR - timedelta(seconds=1)) is None
    assert schedule.slot_at_or_before(ANCHOR) == ANCHOR
    assert schedule.slot_at_or_before(ANCHOR + timedelta(minutes=14, seconds=59)) == ANCHOR + timedelta(minutes=10)
    assert schedule.slot_at_or_before(ANCHOR + timedelta(hours=10)) == ANCHOR + timedelta(hours=10)


def test_interval_schedule_normalizes_timezone_to_utc():
    schedule = IntervalSchedule(timedelta(hours=1), ANCHOR)
    local_now = (ANCHOR + timedelta(hours=2)).astimezone(timezone(timedelta(hours=-3)))
    assert schedule.slot_at_or_before(local_now) == ANCHOR + timedelta(hours=2)


@pytest.mark.parametrize("every", [timedelta(), timedelta(seconds=-1), "one"])
def test_interval_schedule_rejects_non_positive_interval(every):
    with pytest.raises(JobScheduleError):
        IntervalSchedule(every, ANCHOR)


def test_interval_schedule_rejects_naive_anchor_and_now():
    with pytest.raises(JobValidationError):
        IntervalSchedule(timedelta(minutes=1), datetime(2026, 8, 21, 10, 0))
    schedule = IntervalSchedule(timedelta(minutes=1), ANCHOR)
    with pytest.raises(JobValidationError):
        schedule.slot_at_or_before(datetime(2026, 8, 21, 10, 0))
