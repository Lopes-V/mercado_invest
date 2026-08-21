class MarketDataError(Exception):
    """Base error for the provider-independent Market Data core."""


class MarketDataValidationError(MarketDataError, ValueError):
    """Raised when a normalized model or request violates its contract."""


class MarketDataQualityError(MarketDataError, ValueError):
    """Raised when the Quality Engine receives an invalid input."""


class QualityPolicyError(MarketDataQualityError):
    """Raised when a QualityPolicy is invalid or incomplete."""


class ProviderError(MarketDataError):
    """Raised by a future provider adapter when its operation fails."""


class ProviderCapabilityError(ProviderError):
    """Raised when a provider does not support a requested operation."""


class ProviderTransportError(ProviderError):
    """Raised when a provider transport operation cannot complete."""


class ProviderHttpError(ProviderError):
    """Raised when a provider returns an unsuccessful HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        provider_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_code = provider_code


class ProviderRateLimitError(ProviderHttpError):
    """Raised when a provider exhausts retries after rate limiting."""


class ProviderResponseError(ProviderError):
    """Raised when a provider response violates the expected contract."""


class MarketDataIngestionError(MarketDataError):
    """Raised when the ingestion orchestration contract is violated."""
