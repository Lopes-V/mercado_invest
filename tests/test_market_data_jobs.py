import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.jobs.market_data import MarketHistoryCollectionJob, MarketQuoteCollectionJob
from app.jobs.models import JobContext, JobTrigger
from app.market_data.models import CandleInterval


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
CONTEXT = JobContext(UUID("11111111-1111-1111-1111-111111111111"), JobTrigger.SCHEDULED, NOW, NOW)


class Provider:
    name = "fake"


class Symbols:
    def __init__(self, mappings): self.mappings, self.providers = mappings, []
    def list_active_by_provider(self, provider): self.providers.append(provider); return self.mappings


class Ingestion:
    def __init__(self, error_at=None, *, quote_created=True): self.error_at, self.quote_created, self.quotes, self.histories = error_at, quote_created, [], []
    def ingest_quote(self, asset_id, *, evaluated_at):
        self.quotes.append((asset_id, evaluated_at))
        if asset_id == self.error_at: raise RuntimeError("quote failure")
        return SimpleNamespace(
            created=self.quote_created,
            record=SimpleNamespace(
                asset_id=asset_id,
                provider="fake",
                observed_at=NOW,
            ),
        )
    def ingest_history(self, asset_id, interval, start, end, *, evaluated_at):
        self.histories.append((asset_id, interval, start, end, evaluated_at))
        if asset_id == self.error_at: raise RuntimeError("history failure")


MAPPINGS = (SimpleNamespace(asset_id=UUID("11111111-1111-1111-1111-111111111111")), SimpleNamespace(asset_id=UUID("22222222-2222-2222-2222-222222222222")))


def test_quote_collection_processes_active_mappings_and_empty_set():
    ingestion, symbols = Ingestion(), Symbols(MAPPINGS)
    job = MarketQuoteCollectionJob(provider=Provider(), ingestion=ingestion, provider_symbols=symbols)
    assert job.name == "market_quotes:fake"
    assert job.execute(CONTEXT).processed_count == 2
    assert symbols.providers == ["fake"]
    assert all(value[1] == NOW for value in ingestion.quotes)
    assert MarketQuoteCollectionJob(provider=Provider(), ingestion=Ingestion(), provider_symbols=Symbols(())).execute(CONTEXT).processed_count == 0


def test_quote_collection_fails_fast():
    ingestion = Ingestion(error_at=MAPPINGS[0].asset_id)
    with pytest.raises(RuntimeError, match="quote failure"):
        MarketQuoteCollectionJob(provider=Provider(), ingestion=ingestion, provider_symbols=Symbols(MAPPINGS)).execute(CONTEXT)
    assert len(ingestion.quotes) == 1


def test_quote_collection_ignores_persisted_duplicate_without_failing(caplog):
    ingestion = Ingestion(quote_created=False)
    job = MarketQuoteCollectionJob(
        provider=Provider(), ingestion=ingestion, provider_symbols=Symbols(MAPPINGS[:1])
    )
    with caplog.at_level(logging.INFO, logger="investment_bot"):
        assert job.execute(CONTEXT).processed_count == 1
    assert "market_quote_duplicate_ignored job_name=market_quotes:fake" in caplog.text


def test_history_collection_uses_explicit_window_interval_and_fails_fast():
    ingestion = Ingestion()
    job = MarketHistoryCollectionJob(provider=Provider(), ingestion=ingestion, provider_symbols=Symbols(MAPPINGS), interval=CandleInterval.ONE_DAY, lookback=timedelta(days=7))
    assert job.name == "market_history:fake:1d"
    assert job.execute(CONTEXT).processed_count == 2
    assert all(item[1:] == (CandleInterval.ONE_DAY, NOW - timedelta(days=7), NOW, NOW) for item in ingestion.histories)
    failing = Ingestion(error_at=MAPPINGS[0].asset_id)
    with pytest.raises(RuntimeError, match="history failure"):
        MarketHistoryCollectionJob(provider=Provider(), ingestion=failing, provider_symbols=Symbols(MAPPINGS), interval=CandleInterval.ONE_DAY, lookback=timedelta(days=1)).execute(CONTEXT)
    assert len(failing.histories) == 1


@pytest.mark.parametrize("lookback", [timedelta(), timedelta(days=-1)])
def test_history_collection_requires_positive_explicit_lookback(lookback):
    with pytest.raises(ValueError):
        MarketHistoryCollectionJob(provider=Provider(), ingestion=Ingestion(), provider_symbols=Symbols(()), interval=CandleInterval.ONE_DAY, lookback=lookback)
