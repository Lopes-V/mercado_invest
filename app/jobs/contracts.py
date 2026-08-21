from typing import Protocol, runtime_checkable

from app.jobs.models import JobContext, JobResult


@runtime_checkable
class Job(Protocol):
    @property
    def name(self) -> str:
        """Stable, non-empty identifier for an executable job."""

    def execute(self, context: JobContext) -> JobResult:
        """Execute synchronously for the supplied explicit context."""
