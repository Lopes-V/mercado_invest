class JobError(Exception):
    """Base error for the synchronous jobs subsystem."""


class JobValidationError(JobError):
    """Raised when a job model or scheduling input is invalid."""


class JobScheduleError(JobError):
    """Raised for invalid schedule or scheduler configuration."""


class JobRunnerError(JobError):
    """Raised when the runner cannot establish a run lifecycle."""
