from datetime import UTC,datetime,timedelta
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.config.settings import Settings,Environment,LogLevel
from app.health import HealthService,HealthStatus
from app.jobs.recovery import JobRecoveryService
from app.jobs.models import JobRunStatus
from app.security import sanitize_sensitive_text
from app.worker import run_worker

NOW=datetime(2026,1,1,tzinfo=UTC)
def test_sanitizer_and_settings_repr_are_safe():
    text=sanitize_sensitive_text("Bearer abc token=xyz 123456:abcdefghijklmnopqrst")
    assert "abc" not in text and "xyz" not in text
    settings=Settings(Environment.TEST,LogLevel.INFO,"url","supabase-secret","telegram-secret",frozenset())
    assert "supabase-secret" not in repr(settings) and "telegram-secret" not in repr(settings)
def test_health_states():
    assert HealthService(config_check=lambda:None).check().status is HealthStatus.OK
    assert HealthService(config_check=lambda:None,supabase_check=lambda:(_ for _ in ()).throw(RuntimeError())).check().status is HealthStatus.DEGRADED
    assert HealthService(config_check=lambda:(_ for _ in ()).throw(RuntimeError())).check().status is HealthStatus.FAILED
class Runs:
    def __init__(self,fail=False):self.fail=fail
    def list_stale_running(self,_):return (SimpleNamespace(id=uuid4()),)
    def finish_run(self,**kwargs):
        if self.fail:raise RuntimeError("db")
        return SimpleNamespace(**kwargs)
def test_recovery_marks_failed_and_propagates_persistence_error():
    assert JobRecoveryService(Runs()).recover_stale_runs(cutoff=NOW,finished_at=NOW)[0].terminal_status is JobRunStatus.FAILED
    with pytest.raises(RuntimeError):JobRecoveryService(Runs(True)).recover_stale_runs(cutoff=NOW,finished_at=NOW)
class Scheduler:
    def __init__(self):self.called=False
    def run_forever(self,**kwargs):self.called=True
def test_worker_stops_and_closes():
    scheduler=Scheduler();closed=[]
    run_worker(scheduler,stop_event=SimpleNamespace(is_set=lambda:True),close=lambda:closed.append(True))
    assert scheduler.called and closed
