from datetime import timedelta

from app.database.repositories.market_data import ProviderSymbolRepository
from app.jobs.models import JobContext, JobResult, ensure_job_name
from app.market_data.contracts import MarketDataProvider
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import CandleInterval


class MarketQuoteCollectionJob:
    def __init__(self, *, provider: MarketDataProvider, ingestion: MarketDataIngestionService, provider_symbols: ProviderSymbolRepository) -> None:
        self._provider = provider
        self._ingestion = ingestion
        self._provider_symbols = provider_symbols
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return f"market_quotes:{self._provider.name}"

    def execute(self, context: JobContext) -> JobResult:
        mappings = self._provider_symbols.list_active_by_provider(self._provider.name)
        processed = 0
        for mapping in mappings:
            self._ingestion.ingest_quote(mapping.asset_id, evaluated_at=context.started_at)
            processed += 1
        return JobResult(processed)


class MarketHistoryCollectionJob:
    def __init__(self, *, provider: MarketDataProvider, ingestion: MarketDataIngestionService, provider_symbols: ProviderSymbolRepository, interval: CandleInterval, lookback: timedelta) -> None:
        if not isinstance(interval, CandleInterval):
            raise ValueError("interval deve ser CandleInterval")
        if not isinstance(lookback, timedelta) or lookback <= timedelta():
            raise ValueError("lookback deve ser timedelta positivo")
        self._provider = provider
        self._ingestion = ingestion
        self._provider_symbols = provider_symbols
        self._interval = interval
        self._lookback = lookback
        ensure_job_name(self.name)

    @property
    def name(self) -> str:
        return f"market_history:{self._provider.name}:{self._interval.value}"

    def execute(self, context: JobContext) -> JobResult:
        mappings = self._provider_symbols.list_active_by_provider(self._provider.name)
        start = context.scheduled_for - self._lookback
        processed = 0
        for mapping in mappings:
            self._ingestion.ingest_history(mapping.asset_id, self._interval, start, context.scheduled_for, evaluated_at=context.started_at)
            processed += 1
        return JobResult(processed)
