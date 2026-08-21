"""Composition root for the synchronous worker; domain services never construct infrastructure."""
from dataclasses import dataclass
from datetime import UTC,datetime,timedelta
from app.config.settings import Settings
from app.database.client import create_supabase_client
from app.database.repositories import MarketCandleRepository,MarketQuoteRepository,ProviderSymbolRepository,JobRunRepository
from app.market_data.http import ProviderHttpClient
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.providers.brapi import BrapiProvider
from app.market_data.quality import QualityEngine,QualityPolicy
from app.market_data.models import CandleInterval
from app.jobs.market_data import MarketHistoryCollectionJob,MarketQuoteCollectionJob
from app.jobs.runner import JobRunner
from app.jobs.schedule import IntervalSchedule,ScheduledJob,SchedulerService

@dataclass(slots=True)
class Application:
    http:ProviderHttpClient
    provider:BrapiProvider
    ingestion:MarketDataIngestionService
    job_runs:JobRunRepository
    scheduler:SchedulerService
    def close(self)->None:self.http.close()

def build_application(settings:Settings, *, quality_policy:QualityPolicy)->Application:
    client=create_supabase_client(settings); http=ProviderHttpClient(base_url="https://brapi.dev")
    provider=BrapiProvider(http,token=settings.brapi_token)
    symbols=ProviderSymbolRepository(client); quotes=MarketQuoteRepository(client); candles=MarketCandleRepository(client)
    ingestion=MarketDataIngestionService(provider=provider,quality_engine=QualityEngine(quality_policy),provider_symbols=symbols,quotes=quotes,candles=candles)
    job_runs=JobRunRepository(client); runner=JobRunner(job_runs); jobs=[]; anchor=datetime(1970,1,1,tzinfo=UTC)
    if settings.market_quotes_enabled: jobs.append(ScheduledJob(MarketQuoteCollectionJob(provider=provider,ingestion=ingestion,provider_symbols=symbols),IntervalSchedule(timedelta(seconds=settings.market_quotes_interval_seconds),anchor)))
    if settings.market_history_enabled:
        try: interval=CandleInterval(settings.market_history_candle_interval)
        except ValueError as exc: raise ValueError("MARKET_HISTORY_CANDLE_INTERVAL inválido") from exc
        jobs.append(ScheduledJob(MarketHistoryCollectionJob(provider=provider,ingestion=ingestion,provider_symbols=symbols,interval=interval,lookback=timedelta(days=settings.market_history_lookback_days)),IntervalSchedule(timedelta(seconds=settings.market_history_interval_seconds),anchor)))
    return Application(http,provider,ingestion,job_runs,SchedulerService(runner,jobs))
