from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.database.models import RepositoryDataError
from app.database.repositories.jobs import JobRunRepository
from app.database.repositories.market_data import ProviderSymbolRepository
from app.jobs.models import JobRunStatus, JobTrigger


MIGRATIONS_DIR = Path("supabase/migrations")
RUN_ID = UUID("11111111-1111-1111-1111-111111111111")
CORRELATION_ID = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


def job_runs_migration() -> Path:
    matches = sorted(MIGRATIONS_DIR.glob("*_create_job_runs.sql"))
    assert len(matches) == 1, "deve existir exatamente uma migration create_job_runs"
    return matches[0]


def sql() -> str:
    return " ".join(job_runs_migration().read_text(encoding="utf-8").lower().split())


def test_job_runs_migration_contract():
    migration = sql()
    assert "create table public.job_runs" in migration
    for field in ("job_name", "run_key", "trigger_type", "scheduled_for", "status", "correlation_id", "started_at", "finished_at", "error_code", "error_message"):
        assert field in migration
    assert "unique (run_key)" in migration
    assert "unique (correlation_id)" in migration
    assert "trigger_type in ('scheduled', 'manual')" in migration
    assert "status in ('running', 'succeeded', 'failed', 'skipped')" in migration
    assert "enable row level security" in migration
    assert "create policy" not in migration
    assert "job_runs_job_name_scheduled_for_idx" in migration
    assert "grant select, insert, update, delete on table public.job_runs to service_role" in migration
    for privilege in ("truncate", "trigger", "references", "maintain"):
        assert f"grant {privilege}" not in migration


class Response:
    def __init__(self, data): self.data = data


class Request:
    def __init__(self, response, error=None):
        self.response, self.error, self.operations = response, error, []
    def insert(self, value): self.operations.append(("insert", value)); return self
    def update(self, value): self.operations.append(("update", value)); return self
    def select(self, *value): self.operations.append(("select", value)); return self
    def eq(self, *value): self.operations.append(("eq", *value)); return self
    def order(self, *value, **kwargs): self.operations.append(("order", *value, kwargs)); return self
    def limit(self, value): self.operations.append(("limit", value)); return self
    def execute(self):
        self.operations.append(("execute",))
        if self.error: raise self.error
        return self.response


class Client:
    def __init__(self, response, error=None): self.response, self.error, self.requests = response, error, []
    def table(self, name):
        request = Request(self.response, self.error)
        self.requests.append((name, request))
        return request


def row(**changes):
    value = {
        "id": str(RUN_ID), "job_name": "test_job", "run_key": "test_job:2026-08-21T12:00:00+00:00",
        "trigger_type": "SCHEDULED", "scheduled_for": NOW.isoformat(), "status": "RUNNING",
        "correlation_id": str(CORRELATION_ID), "started_at": NOW.isoformat(), "finished_at": None,
        "error_code": None, "error_message": None, "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
    }
    value.update(changes)
    return value


def last(client): return client.requests[-1][1]


def test_repository_starts_finishes_and_reads_runs():
    client = Client(Response([row()]))
    repo = JobRunRepository(client)
    started = repo.start_run(job_name="test_job", run_key="key", trigger=JobTrigger.SCHEDULED, scheduled_for=NOW, correlation_id=CORRELATION_ID, started_at=NOW)
    assert started.status is JobRunStatus.RUNNING
    assert last(client).operations[0] == ("insert", {"job_name": "test_job", "run_key": "key", "trigger_type": "SCHEDULED", "scheduled_for": NOW.isoformat(), "status": "RUNNING", "correlation_id": str(CORRELATION_ID), "started_at": NOW.isoformat()})
    client.response = Response([row(status="SUCCEEDED", finished_at=NOW.isoformat())])
    finished = repo.finish_run(run_id=RUN_ID, terminal_status=JobRunStatus.SUCCEEDED, finished_at=NOW)
    assert finished.status is JobRunStatus.SUCCEEDED
    assert last(client).operations[0][0] == "update"
    client.response = Response([row(status="FAILED", finished_at=NOW.isoformat(), error_code="ValueError", error_message="failed")])
    assert repo.get_by_run_key("key").status is JobRunStatus.FAILED
    assert ("eq", "run_key", "key") in last(client).operations
    assert repo.get_latest("test_job") is not None
    assert any(operation[0] == "order" for operation in last(client).operations)


def test_repository_handles_empty_malformed_external_and_invalid_terminal_status():
    repo = JobRunRepository(Client(Response([])))
    assert repo.get_by_run_key("missing") is None
    with pytest.raises(ValueError):
        repo.finish_run(run_id=RUN_ID, terminal_status=JobRunStatus.RUNNING, finished_at=NOW)
    with pytest.raises(RepositoryDataError):
        JobRunRepository(Client(Response([{"id": str(RUN_ID)}]))).get_by_run_key("key")
    with pytest.raises(RuntimeError):
        JobRunRepository(Client(Response([]), RuntimeError("external"))).get_by_run_key("key")


def test_active_provider_symbols_are_filtered_and_ordered():
    symbol_row = {
        "id": str(RUN_ID), "asset_id": str(CORRELATION_ID), "provider": "fake",
        "provider_symbol": "AAA", "is_active": True,
        "created_at": NOW.isoformat(), "updated_at": NOW.isoformat(),
    }
    client = Client(Response([symbol_row]))
    records = ProviderSymbolRepository(client).list_active_by_provider("fake")
    assert records[0].provider_symbol == "AAA"
    operations = last(client).operations
    assert ("eq", "provider", "fake") in operations
    assert ("eq", "is_active", True) in operations
    assert any(operation[0] == "order" for operation in operations)
