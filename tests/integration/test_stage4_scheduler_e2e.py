import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import AssetRepository, CurrencyRepository, ExchangeRepository, JobRunRepository, MarketCandleRepository, MarketQuoteRepository, MarketRepository, ProviderSymbolRepository
from app.jobs.market_data import MarketQuoteCollectionJob
from app.jobs.runner import JobRunner, build_scheduled_run_key
from app.jobs.schedule import IntervalSchedule, ScheduledJob, SchedulerService
from app.market_data.http import ProviderHttpClient
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import CandleInterval
from app.market_data.providers import BrapiProvider
from app.market_data.quality import QualityEngine, QualityPolicy


pytestmark = pytest.mark.integration


def client():
    if os.getenv("RUN_STAGE4_E2E") != "1":
        pytest.skip("E2E Stage 4 requer RUN_STAGE4_E2E=1")
    return create_supabase_client(get_settings())


def delete(client, table: str, record_ids: list[UUID]) -> None:
    for record_id in record_ids:
        client.table(table).delete().eq("id", str(record_id)).execute()
        assert client.table(table).select("id").eq("id", str(record_id)).execute().data == []


def test_stage4_scheduler_real_brapi_supabase_idempotency_and_cleanup():
    supabase = client()
    settings = get_settings()
    suffix = uuid4().hex.upper()
    ids: dict[str, UUID | None] = {key: None for key in ("currency", "market", "exchange", "asset", "mapping", "run")}
    quote_ids: list[UUID] = []
    now = datetime.now(UTC)
    try:
        currency = CurrencyRepository(supabase).create(code=f"T{suffix[:7]}", name=f"Stage 4 currency {suffix}")
        ids["currency"] = currency.id
        market = MarketRepository(supabase).create(code=f"M{suffix[:10]}", name=f"Stage 4 market {suffix}", default_currency_id=currency.id)
        ids["market"] = market.id
        exchange = ExchangeRepository(supabase).create(market_id=market.id, code=f"E{suffix[:10]}", name=f"Stage 4 exchange {suffix}", timezone="UTC")
        ids["exchange"] = exchange.id
        asset = AssetRepository(supabase).create(market_id=market.id, exchange_id=exchange.id, currency_id=currency.id, symbol=f"J{suffix[:13]}", name=f"Stage 4 asset {suffix}", asset_type="TEST")
        ids["asset"] = asset.id
        mapping = ProviderSymbolRepository(supabase).create(asset_id=asset.id, provider="brapi", provider_symbol="PETR4")
        ids["mapping"] = mapping.id
        provider = BrapiProvider(ProviderHttpClient(base_url="https://brapi.dev"), token=settings.brapi_token)
        policy = QualityPolicy(timedelta(days=30), timedelta(days=30), {interval: timedelta(days=400) for interval in CandleInterval}, timedelta(minutes=5))
        ingestion = MarketDataIngestionService(provider=provider, quality_engine=QualityEngine(policy), provider_symbols=ProviderSymbolRepository(supabase), quotes=MarketQuoteRepository(supabase), candles=MarketCandleRepository(supabase))
        job = MarketQuoteCollectionJob(provider=provider, ingestion=ingestion, provider_symbols=ProviderSymbolRepository(supabase))
        scheduler = SchedulerService(JobRunner(JobRunRepository(supabase)), (ScheduledJob(job, IntervalSchedule(timedelta(hours=1), now)),))
        first = scheduler.run_due(now=now)
        assert len(first.successes) == 1 and not first.failures
        ids["run"] = first.successes[0].run.id
        assert first.successes[0].job_result is not None
        second = scheduler.run_due(now=now)
        assert len(second.successes) == 1 and second.successes[0].already_executed is True
        run_key = build_scheduled_run_key(job.name, now)
        assert JobRunRepository(supabase).get_by_run_key(run_key).id == ids["run"]
        rows = supabase.table("market_quotes").select("id, price, provider, provider_symbol, quality").eq("asset_id", str(asset.id)).eq("provider", "brapi").execute().data
        assert len(rows) == 1 and rows[0]["provider_symbol"] == "PETR4"
        assert isinstance(Decimal(str(rows[0]["price"])), Decimal) and rows[0]["quality"] is not None
        quote_ids.extend(UUID(row["id"]) for row in rows)
    finally:
        delete(supabase, "market_quotes", quote_ids)
        for table, key in (("job_runs", "run"), ("asset_provider_symbols", "mapping"), ("assets", "asset"), ("exchanges", "exchange"), ("markets", "market"), ("currencies", "currency")):
            record_id = ids[key]
            if record_id is not None:
                delete(supabase, table, [record_id])
