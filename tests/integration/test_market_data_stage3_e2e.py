import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import AssetRepository, CurrencyRepository, ExchangeRepository, MarketCandleRepository, MarketQuoteRepository, MarketRepository, ProviderSymbolRepository
from app.market_data.http import ProviderHttpClient
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import CandleInterval, DataQuality
from app.market_data.providers import BrapiProvider
from app.market_data.quality import QualityEngine, QualityPolicy


pytestmark = pytest.mark.integration


def client():
    if os.getenv("RUN_MARKET_DATA_E2E") != "1":
        pytest.skip("E2E Market Data requer RUN_MARKET_DATA_E2E=1")
    return create_supabase_client(get_settings())


def test_stage3_real_brapi_quality_persistence_and_cleanup():
    supabase = client()
    settings = get_settings()
    suffix = uuid4().hex.upper()
    ids: dict[str, list[UUID] | UUID | None] = {"candles": [], "quotes": [], "mapping": None, "asset": None, "exchange": None, "market": None, "currency": None}
    now = datetime.now(UTC)
    history_start = now - timedelta(days=30)
    try:
        currency = CurrencyRepository(supabase).create(code=f"T{suffix[:7]}", name=f"E2E currency {suffix}")
        ids["currency"] = currency.id
        market = MarketRepository(supabase).create(code=f"M{suffix[:10]}", name=f"E2E market {suffix}", default_currency_id=currency.id)
        ids["market"] = market.id
        exchange = ExchangeRepository(supabase).create(market_id=market.id, code=f"E{suffix[:10]}", name=f"E2E exchange {suffix}", timezone="UTC")
        ids["exchange"] = exchange.id
        asset = AssetRepository(supabase).create(market_id=market.id, exchange_id=exchange.id, currency_id=currency.id, symbol=f"E2E{suffix[:11]}", name=f"E2E asset {suffix}", asset_type="TEST")
        ids["asset"] = asset.id
        mapping = ProviderSymbolRepository(supabase).create(asset_id=asset.id, provider="brapi", provider_symbol="PETR4")
        ids["mapping"] = mapping.id
        policy = QualityPolicy(timedelta(days=30), timedelta(days=30), {interval: timedelta(days=400) for interval in CandleInterval}, timedelta(minutes=5))
        service = MarketDataIngestionService(provider=BrapiProvider(ProviderHttpClient(base_url="https://brapi.dev"), token=settings.brapi_token), quality_engine=QualityEngine(policy), provider_symbols=ProviderSymbolRepository(supabase), quotes=MarketQuoteRepository(supabase), candles=MarketCandleRepository(supabase))
        quote_result = service.ingest_quote(asset.id, evaluated_at=now)
        ids["quotes"].append(quote_result.record.id)
        assert quote_result.record.provider == "brapi" and quote_result.record.provider_symbol == "PETR4"
        assert isinstance(quote_result.record.price, Decimal)
        assert quote_result.assessment.quality in DataQuality and quote_result.assessment.data.quality == quote_result.assessment.quality
        history_result = service.ingest_history(asset.id, CandleInterval.ONE_DAY, history_start, now, evaluated_at=now)
        ids["candles"].extend(record.id for record in history_result.records)
        assert history_result.assessments and len(history_result.assessments) == len(history_result.records)
        assert all(item.data.quality is not None for item in history_result.assessments)
        assert MarketQuoteRepository(supabase).get_by_id(quote_result.record.id) is not None
        persisted_candles = MarketCandleRepository(supabase).get_range(
            asset_id=asset.id,
            provider="brapi",
            interval=CandleInterval.ONE_DAY,
            start=min(
                assessment.data.timestamp
                for assessment in history_result.assessments
            ),
            end=now,
        )
        assert len(persisted_candles) == len(history_result.records)
    finally:
        if ids["asset"] is not None:
            for table, key in (("market_candles", "candles"), ("market_quotes", "quotes")):
                if not ids[key]:
                    rows = (
                        supabase.table(table)
                        .select("id")
                        .eq("asset_id", str(ids["asset"]))
                        .eq("provider", "brapi")
                        .execute()
                        .data
                    )
                    ids[key].extend(UUID(row["id"]) for row in rows)
        for table, values in (("market_candles", ids["candles"]), ("market_quotes", ids["quotes"])):
            for record_id in values:
                supabase.table(table).delete().eq("id", str(record_id)).execute()
        for table, key in (("asset_provider_symbols", "mapping"), ("assets", "asset"), ("exchanges", "exchange"), ("markets", "market"), ("currencies", "currency")):
            record_id = ids[key]
            if record_id is not None:
                supabase.table(table).delete().eq("id", str(record_id)).execute()
        for table, values in (("market_candles", ids["candles"]), ("market_quotes", ids["quotes"])):
            for record_id in values:
                assert supabase.table(table).select("id").eq("id", str(record_id)).execute().data == []
        for table, key in (("asset_provider_symbols", "mapping"), ("assets", "asset"), ("exchanges", "exchange"), ("markets", "market"), ("currencies", "currency")):
            record_id = ids[key]
            if record_id is not None:
                assert supabase.table(table).select("id").eq("id", str(record_id)).execute().data == []
