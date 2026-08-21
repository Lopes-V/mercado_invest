import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import JobRunRepository
from app.jobs.models import JobRunStatus, JobTrigger


pytestmark = pytest.mark.integration


def client():
    if os.getenv("RUN_JOBS_DB_INTEGRATION") != "1":
        pytest.skip("integração jobs requer RUN_JOBS_DB_INTEGRATION=1")
    return create_supabase_client(get_settings())


def test_job_runs_real_persistence_and_exact_cleanup():
    supabase = client()
    repository = JobRunRepository(supabase)
    now = datetime.now(UTC)
    run_id: UUID | None = None
    try:
        run = repository.start_run(
            job_name="integration_job",
            run_key=f"integration_job:manual:{uuid4()}",
            trigger=JobTrigger.MANUAL,
            scheduled_for=now,
            correlation_id=uuid4(),
            started_at=now,
        )
        run_id = run.id
        assert run.status is JobRunStatus.RUNNING
        finished = repository.finish_run(
            run_id=run.id,
            terminal_status=JobRunStatus.SUCCEEDED,
            finished_at=now,
        )
        assert finished.status is JobRunStatus.SUCCEEDED
        assert repository.get_by_run_key(run.run_key) == finished
        assert repository.get_latest("integration_job") is not None
    finally:
        if run_id is not None:
            supabase.table("job_runs").delete().eq("id", str(run_id)).execute()
            assert supabase.table("job_runs").select("id").eq("id", str(run_id)).execute().data == []
