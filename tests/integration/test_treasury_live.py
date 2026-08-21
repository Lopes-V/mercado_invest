import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.fixed_income.provider import BrapiTreasuryProvider
from app.market_data.http import ProviderHttpClient


pytestmark=pytest.mark.integration


@pytest.mark.skipif(os.getenv("RUN_TREASURY_INTEGRATION")!="1",reason="RUN_TREASURY_INTEGRATION=1 required")
def test_treasury_sandbox_live_snapshot_and_history():
    """Uses BRAPI's documented no-token sandbox symbol over real HTTPS."""
    symbol = "tesouro-selic-01032031"
    client = ProviderHttpClient(base_url="https://brapi.dev", timeout_seconds=15)
    provider = BrapiTreasuryProvider(client)
    try:
        snapshot = provider.get_snapshot(asset_id=uuid4(), symbol=symbol)
        history = provider.get_history(
            asset_id=uuid4(),
            symbol=symbol,
            start=date(2026, 5, 1),
            end=date(2026, 5, 15),
        )
    finally:
        client.close()
    assert snapshot.provider_symbol == symbol
    assert snapshot.received_at.tzinfo is not None
    assert any(isinstance(value, Decimal) for value in (snapshot.buy_rate, snapshot.sell_rate, snapshot.buy_price, snapshot.sell_price, snapshot.base_price) if value is not None)
    assert history
    assert history[0].reference_date >= date(2026, 5, 1)
