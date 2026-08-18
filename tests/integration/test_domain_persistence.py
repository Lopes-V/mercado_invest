import os
from uuid import UUID, uuid4

import pytest
from dotenv import load_dotenv
from supabase import create_client

from app.database.repositories import (
    AssetRepository,
    CurrencyRepository,
    ExchangeRepository,
    MarketRepository,
)


pytestmark = pytest.mark.integration


def _integration_client():
    if os.getenv("RUN_SUPABASE_INTEGRATION") != "1":
        pytest.skip("integração Supabase requer RUN_SUPABASE_INTEGRATION=1")

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    secret_key = os.getenv("SUPABASE_SECRET_KEY")

    if not url or not secret_key:
        pytest.fail("credenciais de integração Supabase não configuradas")

    return create_client(url, secret_key)


def _cleanup_by_id(client, table: str, record_id: UUID | None) -> None:
    if record_id is not None:
        client.table(table).delete().eq("id", str(record_id)).execute()


def test_domain_persistence_with_service_role_and_database_constraints():
    client = _integration_client()
    currencies = CurrencyRepository(client)
    markets = MarketRepository(client)
    exchanges = ExchangeRepository(client)
    assets = AssetRepository(client)
    suffix = uuid4().hex.upper()

    currency_id: UUID | None = None
    market_id: UUID | None = None
    other_market_id: UUID | None = None
    exchange_id: UUID | None = None
    exchange_asset_id: UUID | None = None
    no_exchange_asset_id: UUID | None = None

    try:
        currency = currencies.create(
            code=f"T{suffix[:7]}",
            name=f"Temporary currency {suffix}",
            decimal_places=4,
        )
        currency_id = currency.id
        assert currencies.get_by_code(currency.code) == currency

        market = markets.create(
            code=f"M{suffix[:10]}",
            name=f"Temporary market {suffix}",
            default_currency_id=currency.id,
        )
        market_id = market.id
        assert markets.get_by_id(market.id) == market

        other_market = markets.create(
            code=f"N{suffix[:10]}",
            name=f"Temporary secondary market {suffix}",
        )
        other_market_id = other_market.id

        exchange = exchanges.create(
            market_id=market.id,
            code=f"E{suffix[:10]}",
            name=f"Temporary exchange {suffix}",
            timezone="UTC",
        )
        exchange_id = exchange.id
        assert (
            exchanges.get_by_market_and_code(market.id, exchange.code)
            == exchange
        )

        exchange_asset = assets.create(
            market_id=market.id,
            exchange_id=exchange.id,
            currency_id=currency.id,
            symbol=f"TEST_{suffix[:12]}",
            name=f"Temporary exchange asset {suffix}",
            asset_type="TEST",
        )
        exchange_asset_id = exchange_asset.id
        assert assets.get_by_id(exchange_asset.id) == exchange_asset
        assert (
            assets.get_by_identity(
                market_id=market.id,
                exchange_id=exchange.id,
                symbol=exchange_asset.symbol,
                currency_id=currency.id,
            )
            == exchange_asset
        )
        assert exchange_asset.market_id == market.id
        assert exchange_asset.exchange_id == exchange.id
        assert exchange_asset.currency_id == currency.id
        assert exchange_asset.isin is None

        no_exchange_asset = assets.create(
            market_id=market.id,
            exchange_id=None,
            currency_id=currency.id,
            symbol=exchange_asset.symbol,
            name=f"Temporary non-exchange asset {suffix}",
            asset_type="TEST",
        )
        no_exchange_asset_id = no_exchange_asset.id
        assert no_exchange_asset.exchange_id is None
        assert (
            assets.get_by_identity(
                market_id=market.id,
                exchange_id=None,
                symbol=no_exchange_asset.symbol,
                currency_id=currency.id,
            )
            == no_exchange_asset
        )

        with pytest.raises(Exception):
            assets.create(
                market_id=other_market.id,
                exchange_id=exchange.id,
                currency_id=currency.id,
                symbol=f"MISMATCH_{suffix[:10]}",
                name=f"Temporary mismatch asset {suffix}",
                asset_type="TEST",
            )

        with pytest.raises(Exception):
            assets.create(
                market_id=market.id,
                exchange_id=exchange.id,
                currency_id=currency.id,
                symbol=exchange_asset.symbol,
                name=f"Temporary duplicate exchange asset {suffix}",
                asset_type="TEST",
            )

        with pytest.raises(Exception):
            assets.create(
                market_id=market.id,
                exchange_id=None,
                currency_id=currency.id,
                symbol=no_exchange_asset.symbol,
                name=f"Temporary duplicate null asset {suffix}",
                asset_type="TEST",
            )
    finally:
        _cleanup_by_id(client, "assets", no_exchange_asset_id)
        _cleanup_by_id(client, "assets", exchange_asset_id)
        _cleanup_by_id(client, "exchanges", exchange_id)
        _cleanup_by_id(client, "markets", other_market_id)
        _cleanup_by_id(client, "markets", market_id)
        _cleanup_by_id(client, "currencies", currency_id)
