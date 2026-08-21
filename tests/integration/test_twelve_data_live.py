"""Opt-in real HTTPS validation for the Twelve Data United States adapter."""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from app.market_data.contracts import (
    AssetSearchRequest,
    HistoryRequest,
    QuoteRequest,
)
from app.market_data.http import ProviderHttpClient
from app.market_data.models import CandleInterval
from app.market_data.providers.twelve_data import TwelveDataProvider


pytestmark = pytest.mark.integration


def _provider() -> tuple[TwelveDataProvider, ProviderHttpClient]:
    if os.getenv("RUN_TWELVE_DATA_INTEGRATION") != "1":
        pytest.skip("RUN_TWELVE_DATA_INTEGRATION=1 required")
    load_dotenv(".env")
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if not api_key:
        pytest.fail("TWELVE_DATA_API_KEY is required when integration is enabled")
    client = ProviderHttpClient(
        base_url="https://api.twelvedata.com",
        timeout_seconds=15,
    )
    return TwelveDataProvider(client, api_key=api_key), client


def test_twelve_data_live_us_quote_history_and_search() -> None:
    provider, client = _provider()
    try:
        quote = provider.get_quote(QuoteRequest(uuid4(), "AAPL"))
        end = datetime.now(UTC)
        candles = provider.get_history(
            HistoryRequest(
                asset_id=quote.asset_id,
                provider_symbol="AAPL",
                interval=CandleInterval.ONE_DAY,
                start=end - timedelta(days=10),
                end=end,
            )
        )
        assets = provider.get_assets(AssetSearchRequest(query="AAPL"))
    finally:
        client.close()

    assert quote.provider == "twelve_data"
    assert quote.provider_symbol == "AAPL"
    assert isinstance(quote.price, Decimal)
    assert quote.price > 0
    assert quote.currency_code
    assert quote.timestamp.tzinfo is not None
    assert quote.received_at.tzinfo is not None
    assert quote.quality is None

    assert candles
    assert tuple(candle.timestamp for candle in candles) == tuple(
        sorted(candle.timestamp for candle in candles)
    )
    for candle in candles:
        assert candle.provider == "twelve_data"
        assert candle.interval is CandleInterval.ONE_DAY
        assert candle.timestamp.tzinfo is not None
        assert candle.received_at.tzinfo is not None
        assert all(
            isinstance(value, Decimal)
            for value in (candle.open, candle.high, candle.low, candle.close)
        )
        assert candle.high >= candle.low
        assert candle.quality is None

    assert assets
    assert any(
        asset.provider == "twelve_data" and asset.provider_symbol == "AAPL"
        for asset in assets
    )
