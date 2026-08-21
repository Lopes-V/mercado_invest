import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.config.settings import get_settings
from app.database.client import create_supabase_client
from app.database.repositories import AssetRepository, CurrencyRepository, ExchangeRepository, MarketCandleRepository, MarketQuoteRepository, MarketRepository, ProviderSymbolRepository
from app.market_data.models import Candle, CandleInterval, DataQuality, Quote


pytestmark = pytest.mark.integration


def client():
    if os.getenv("RUN_MARKET_DATA_DB_INTEGRATION") != "1":
        pytest.skip("integração Market Data requer RUN_MARKET_DATA_DB_INTEGRATION=1")
    return create_supabase_client(get_settings())


def delete(client, table: str, record_id: UUID | None) -> None:
    if record_id is not None:
        client.table(table).delete().eq("id", str(record_id)).execute()


def delete_created_market_data(
    client,
    *,
    asset_id: UUID | None,
    provider: str,
    ids: dict[str, UUID | None],
) -> None:
    """Clean by exact record IDs, recovering IDs if an insert response fails."""
    if asset_id is not None:
        for table, key in (("market_candles", "candle"), ("market_quotes", "quote")):
            if ids[key] is None:
                rows = (
                    client.table(table)
                    .select("id")
                    .eq("asset_id", str(asset_id))
                    .eq("provider", provider)
                    .execute()
                    .data
                )
                for row in rows:
                    delete(client, table, UUID(row["id"]))
            else:
                delete(client, table, ids[key])


def test_market_data_repositories_with_real_supabase_and_exact_cleanup():
    supabase = client()
    currencies, markets, exchanges, assets = CurrencyRepository(supabase), MarketRepository(supabase), ExchangeRepository(supabase), AssetRepository(supabase)
    mappings, quotes, candles = ProviderSymbolRepository(supabase), MarketQuoteRepository(supabase), MarketCandleRepository(supabase)
    suffix = uuid4().hex.upper()
    ids: dict[str, UUID | None] = {key: None for key in ("currency", "market", "exchange", "asset", "mapping", "quote", "candle")}
    now = datetime.now(UTC)
    try:
        currency = currencies.create(code=f"T{suffix[:7]}", name=f"Market data currency {suffix}")
        ids["currency"] = currency.id
        market = markets.create(code=f"M{suffix[:10]}", name=f"Market data market {suffix}", default_currency_id=currency.id)
        ids["market"] = market.id
        exchange = exchanges.create(market_id=market.id, code=f"E{suffix[:10]}", name=f"Market data exchange {suffix}", timezone="UTC")
        ids["exchange"] = exchange.id
        asset = assets.create(market_id=market.id, exchange_id=exchange.id, currency_id=currency.id, symbol=f"MD{suffix[:12]}", name=f"Market data asset {suffix}", asset_type="TEST")
        ids["asset"] = asset.id
        mapping = mappings.create(asset_id=asset.id, provider="integration_test", provider_symbol=f"SYM{suffix[:12]}")
        ids["mapping"] = mapping.id
        assert mappings.get_by_asset_and_provider(asset.id, "integration_test") == mapping
        assert mappings.get_by_provider_and_symbol("integration_test", mapping.provider_symbol) == mapping
        quote = Quote(asset.id, mapping.provider_symbol, Decimal("123.456789012345678"), "TST", now, now, "integration_test", DataQuality.VALID)
        quote_record = quotes.create_from_quote(quote)
        ids["quote"] = quote_record.id
        read_quote = quotes.get_by_id(quote_record.id)
        assert read_quote is not None
        assert read_quote.asset_id == asset.id and read_quote.provider == "integration_test"
        assert read_quote.provider_symbol == mapping.provider_symbol and isinstance(read_quote.price, Decimal)
        assert read_quote.currency_code == "TST" and read_quote.quality == DataQuality.VALID.value
        candle = Candle(asset.id, mapping.provider_symbol, now, Decimal("100.10"), Decimal("110.20"), Decimal("99.90"), Decimal("105.30"), Decimal("1000"), CandleInterval.ONE_DAY, "integration_test", now, DataQuality.VALID)
        candle_record = candles.create_many((candle,))[0]
        ids["candle"] = candle_record.id
        read_candles = candles.get_range(asset_id=asset.id, provider="integration_test", interval=CandleInterval.ONE_DAY, start=now, end=now)
        assert len(read_candles) == 1 and read_candles[0].close == Decimal("105.30")
    finally:
        delete_created_market_data(
            supabase,
            asset_id=ids["asset"],
            provider="integration_test",
            ids=ids,
        )
        for table, key in (("asset_provider_symbols", "mapping"), ("assets", "asset"), ("exchanges", "exchange"), ("markets", "market"), ("currencies", "currency")):
            delete(supabase, table, ids[key])
        assert all(record_id is None or supabase.table(table).select("id").eq("id", str(record_id)).execute().data == [] for table, record_id in (("market_candles", ids["candle"]), ("market_quotes", ids["quote"]), ("asset_provider_symbols", ids["mapping"]), ("assets", ids["asset"]), ("exchanges", ids["exchange"]), ("markets", ids["market"]), ("currencies", ids["currency"])))
