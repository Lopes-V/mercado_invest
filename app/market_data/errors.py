class MarketDataError(Exception):
    """Base error for the provider-independent Market Data core."""


class MarketDataValidationError(MarketDataError, ValueError):
    """Raised when a normalized model or request violates its contract."""


class ProviderError(MarketDataError):
    """Raised by a future provider adapter when its operation fails."""


class ProviderCapabilityError(ProviderError):
    """Raised when a provider does not support a requested operation."""
