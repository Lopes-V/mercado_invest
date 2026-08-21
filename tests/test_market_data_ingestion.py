from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.market_data.errors import MarketDataIngestionError, ProviderError
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import CandleInterval, Quote
from app.market_data.quality import QualityEngine, QualityPolicy


ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def engine():
    return QualityEngine(QualityPolicy(timedelta(minutes=10), timedelta(minutes=10), {interval: timedelta(days=2) for interval in CandleInterval}, timedelta(seconds=30)))


def quote():
    return Quote(ASSET_ID, "TEST", Decimal("10"), "TST", NOW - timedelta(minutes=1), NOW - timedelta(minutes=1), "fake", None)


class Provider:
    name = "fake"

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.request = None

    def get_quote(self, request):
        self.request = request
        if self.error:
            raise self.error
        return self.result

    def get_history(self, request):
        self.request = request
        if self.error:
            raise self.error
        return self.result


class Symbols:
    def __init__(self, mapping): self.mapping = mapping
    def get_by_asset_and_provider(self, asset_id, provider): return self.mapping


class Quotes:
    def __init__(self): self.saved = []
    def create_from_quote(self, value): self.saved.append(value); return SimpleNamespace(quality=value.quality)


class Candles:
    def __init__(self): self.saved = []
    def create_many(self, values): self.saved.append(tuple(values)); return tuple(SimpleNamespace(quality=value.quality) for value in values)


def service(provider, mapping=SimpleNamespace(provider="fake", provider_symbol="TEST")):
    return MarketDataIngestionService(provider=provider, quality_engine=engine(), provider_symbols=Symbols(mapping), quotes=Quotes(), candles=Candles())


def test_quote_ingestion_reassesses_and_persists_assessed_data():
    provider = Provider(quote())
    result = service(provider).ingest_quote(ASSET_ID, evaluated_at=NOW, reference_price=Decimal("10"))
    assert provider.request.provider_symbol == "TEST"
    assert result.assessment.data.quality is not None
    assert result.record.quality == result.assessment.quality


def test_ingestion_rejects_missing_or_wrong_provider_mapping():
    with pytest.raises(MarketDataIngestionError, match="não encontrado"):
        service(Provider(quote()), mapping=None).ingest_quote(ASSET_ID, evaluated_at=NOW)
    with pytest.raises(MarketDataIngestionError, match="diferente"):
        service(Provider(quote()), mapping=SimpleNamespace(provider="other", provider_symbol="TEST")).ingest_quote(ASSET_ID, evaluated_at=NOW)


def test_provider_error_propagates_without_persistence():
    with pytest.raises(ProviderError):
        service(Provider(error=ProviderError("failed"))).ingest_quote(ASSET_ID, evaluated_at=NOW)


def test_empty_history_is_explicit_and_not_persisted():
    provider = Provider([])
    result = service(provider).ingest_history(ASSET_ID, CandleInterval.ONE_DAY, NOW - timedelta(days=1), NOW, evaluated_at=NOW)
    assert result.assessments == ()
    assert result.records == ()
