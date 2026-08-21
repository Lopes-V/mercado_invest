from dataclasses import dataclass
from enum import StrEnum
from typing import Callable
class HealthStatus(StrEnum): OK="OK"; DEGRADED="DEGRADED"; FAILED="FAILED"
@dataclass(frozen=True,slots=True)
class HealthReport: status:HealthStatus; checks:tuple[str,...]
class HealthService:
    def __init__(self,*,config_check:Callable[[],None],supabase_check:Callable[[],None]|None=None): self._config=config_check; self._supabase=supabase_check
    def check(self)->HealthReport:
        try:self._config()
        except Exception:return HealthReport(HealthStatus.FAILED,("config_failed",))
        if self._supabase:
            try:self._supabase()
            except Exception:return HealthReport(HealthStatus.DEGRADED,("supabase_unreachable",))
        return HealthReport(HealthStatus.OK,("config_ok",))
