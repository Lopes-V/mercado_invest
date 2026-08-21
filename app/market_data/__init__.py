from app.market_data.contracts import (
    AssetSearchRequest,
    HistoryRequest,
    MarketDataProvider,
    MarketStatusRequest,
    QuoteRequest,
)
from app.market_data.errors import (
    MarketDataError,
    MarketDataIngestionError,
    MarketDataQualityError,
    MarketDataValidationError,
    ProviderCapabilityError,
    ProviderError,
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderTransportError,
    QualityPolicyError,
)
from app.market_data.http import ProviderHttpClient, RetryPolicy
from app.market_data.models import (
    Candle,
    CandleInterval,
    DataQuality,
    MarketSessionStatus,
    MarketStatus,
    ProviderAsset,
    Quote,
)
from app.market_data.quality import (
    QualityAssessment,
    QualityEngine,
    QualityIssue,
    QualityIssueCode,
    QualityPolicy,
)
from app.market_data.providers import BrapiProvider


def __getattr__(name: str):
    """Avoid importing persistence-bound ingestion during core imports."""
    if name in {
        "HistoryIngestionResult",
        "MarketDataIngestionService",
        "QuoteIngestionResult",
    }:
        from app.market_data.ingestion import (
            HistoryIngestionResult,
            MarketDataIngestionService,
            QuoteIngestionResult,
        )

        return {
            "HistoryIngestionResult": HistoryIngestionResult,
            "MarketDataIngestionService": MarketDataIngestionService,
            "QuoteIngestionResult": QuoteIngestionResult,
        }[name]
    raise AttributeError(name)


__all__ = [
    "AssetSearchRequest",
    "BrapiProvider",
    "Candle",
    "CandleInterval",
    "DataQuality",
    "HistoryRequest",
    "HistoryIngestionResult",
    "MarketDataError",
    "MarketDataIngestionError",
    "MarketDataIngestionService",
    "MarketDataQualityError",
    "MarketDataProvider",
    "MarketDataValidationError",
    "MarketSessionStatus",
    "MarketStatus",
    "MarketStatusRequest",
    "ProviderAsset",
    "ProviderCapabilityError",
    "ProviderError",
    "ProviderHttpClient",
    "ProviderHttpError",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderTransportError",
    "QualityAssessment",
    "QualityEngine",
    "QualityIssue",
    "QualityIssueCode",
    "QualityPolicy",
    "QualityPolicyError",
    "Quote",
    "QuoteIngestionResult",
    "QuoteRequest",
    "RetryPolicy",
]
