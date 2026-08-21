from dataclasses import dataclass
from datetime import datetime
from app.database.models import JobRunRecord
from app.database.repositories.jobs import JobRunRepository
from app.jobs.models import JobRunStatus, ensure_utc_datetime

@dataclass(frozen=True,slots=True)
class JobRecoveryService:
    repository: JobRunRepository
    def recover_stale_runs(self, *, cutoff: datetime, finished_at: datetime) -> tuple[JobRunRecord,...]:
        cutoff=ensure_utc_datetime(cutoff,field="cutoff"); finished=ensure_utc_datetime(finished_at,field="finished_at")
        return tuple(self.repository.finish_run(run_id=run.id,terminal_status=JobRunStatus.FAILED,finished_at=finished,error_code="STALE_RUN_RECOVERED",error_message="Execução RUNNING recuperada após exceder o cutoff operacional.") for run in self.repository.list_stale_running(cutoff))
