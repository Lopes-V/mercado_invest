from datetime import datetime
from uuid import UUID

from supabase import Client

from app.database.models import JobRunRecord
from app.database.repositories._response import create_one, read_one_or_none
from app.jobs.models import JobRunStatus, JobTrigger, ensure_job_name, ensure_utc_datetime


def _non_blank(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} não pode ser vazio")
    return value


class JobRunRepository:
    def __init__(self, client: Client) -> None:
        self._client = client

    def start_run(self, *, job_name: str, run_key: str, trigger: JobTrigger, scheduled_for: datetime, correlation_id: UUID, started_at: datetime) -> JobRunRecord:
        ensure_job_name(job_name)
        _non_blank(run_key, field="run_key")
        if not isinstance(trigger, JobTrigger):
            raise ValueError("trigger deve ser JobTrigger")
        if not isinstance(correlation_id, UUID):
            raise ValueError("correlation_id deve ser UUID")
        scheduled = ensure_utc_datetime(scheduled_for, field="scheduled_for")
        started = ensure_utc_datetime(started_at, field="started_at")
        response = self._client.table("job_runs").insert({"job_name": job_name, "run_key": run_key, "trigger_type": trigger.value, "scheduled_for": scheduled.isoformat(), "status": JobRunStatus.RUNNING.value, "correlation_id": str(correlation_id), "started_at": started.isoformat()}).execute()
        return create_one(response, operation="start job run", parser=JobRunRecord.from_payload)

    def finish_run(self, *, run_id: UUID, terminal_status: JobRunStatus, finished_at: datetime, error_code: str | None = None, error_message: str | None = None) -> JobRunRecord:
        if not isinstance(run_id, UUID):
            raise ValueError("run_id deve ser UUID")
        if terminal_status not in {JobRunStatus.SUCCEEDED, JobRunStatus.FAILED, JobRunStatus.SKIPPED}:
            raise ValueError("terminal_status deve ser SUCCEEDED, FAILED ou SKIPPED")
        if error_code is not None:
            _non_blank(error_code, field="error_code")
        if error_message is not None:
            _non_blank(error_message, field="error_message")
        finished = ensure_utc_datetime(finished_at, field="finished_at")
        response = self._client.table("job_runs").update({"status": terminal_status.value, "finished_at": finished.isoformat(), "error_code": error_code, "error_message": error_message}).eq("id", str(run_id)).execute()
        return create_one(response, operation="finish job run", parser=JobRunRecord.from_payload)

    def get_by_id(self, run_id: UUID) -> JobRunRecord | None:
        if not isinstance(run_id, UUID):
            raise ValueError("run_id deve ser UUID")
        return read_one_or_none(self._client.table("job_runs").select("*").eq("id", str(run_id)), operation="get job run by id", parser=JobRunRecord.from_payload)

    def get_by_run_key(self, run_key: str) -> JobRunRecord | None:
        _non_blank(run_key, field="run_key")
        return read_one_or_none(self._client.table("job_runs").select("*").eq("run_key", run_key), operation="get job run by run key", parser=JobRunRecord.from_payload)

    def get_latest(self, job_name: str) -> JobRunRecord | None:
        ensure_job_name(job_name)
        query = self._client.table("job_runs").select("*").eq("job_name", job_name).order("scheduled_for", desc=True)
        return read_one_or_none(query, operation="get latest job run", parser=JobRunRecord.from_payload)
