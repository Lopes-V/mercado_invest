import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.market_data.contracts import HistoryRequest, QuoteRequest
from app.market_data.http import ProviderHttpClient
from app.market_data.models import CandleInterval
from app.market_data.providers import BrapiProvider


pytestmark = pytest.mark.integration


def _provider() -> BrapiProvider:
    if os.getenv("RUN_BRAPI_INTEGRATION") != "1":
        pytest.skip("integração BRAPI requer RUN_BRAPI_INTEGRATION=1")
    return BrapiProvider(ProviderHttpClient(base_url="https://brapi.dev"))


def test_brapi_live_quote_and_recent_history():
    provider = _provider()
    try:
        quote = provider.get_quote(QuoteRequest(uuid4(), "PETR4"))
        assert quote.provider == "brapi"
        assert quote.provider_symbol == "PETR4"
        assert isinstance(quote.price, Decimal)
        assert quote.timestamp.tzinfo is not None
        assert quote.quality is None

        end = datetime.now(UTC)
        candles = provider.get_history(
            HistoryRequest(
                asset_id=quote.asset_id,
                provider_symbol="PETR4",
                interval=CandleInterval.ONE_DAY,
                start=end - timedelta(days=30),
                end=end,
            )
        )
        assert candles
        assert all(candle.quality is None for candle in candles)
    finally:
        provider.close()
