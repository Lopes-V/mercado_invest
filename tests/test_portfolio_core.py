from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.market_data.models import DataQuality
from app.portfolio import CurrencyConversionRequired, PortfolioCalculator, PortfolioError, PortfolioTransaction, PortfolioValuationService, TransactionType
from app.portfolio.core import Valuation


NOW = datetime(2026, 8, 21, tzinfo=UTC)
ASSET = uuid4()

def tx(kind, q, p, fees=Decimal("0")):
    return PortfolioTransaction(ASSET, kind, Decimal(q), Decimal(p), fees, "USD", NOW)

def test_weighted_average_fees_and_partial_sell():
    result = PortfolioCalculator().calculate([tx(TransactionType.BUY, "2", "10", Decimal("1")), tx(TransactionType.BUY, "2", "20"), tx(TransactionType.SELL, "1", "30")])
    position = result.positions[0]
    assert position.quantity == Decimal("3")
    assert position.cost_basis == Decimal("45.75")
    assert position.average_cost == Decimal("15.25")
    assert result.realized_pnl == Decimal("14.75")

def test_total_sell_and_oversell():
    result = PortfolioCalculator().calculate([tx(TransactionType.BUY, "1", "10"), tx(TransactionType.SELL, "1", "11")])
    assert result.positions[0].cost_basis == 0
    with pytest.raises(PortfolioError):
        PortfolioCalculator().calculate([tx(TransactionType.SELL, "1", "10")])

class Source:
    def __init__(self, quality=DataQuality.VALID, currency="USD"): self.value = Valuation(Decimal("12"), currency, quality, NOW)
    def get_valuation(self, asset_id, *, as_of): return self.value

def test_valuation_requires_valid_same_currency():
    position = PortfolioCalculator().calculate([tx(TransactionType.BUY, "1", "10")]).positions
    assert PortfolioValuationService().value(position, source=Source(), base_currency_code="USD", as_of=NOW)[0].unrealized_pnl == Decimal("2")
    with pytest.raises(PortfolioError): PortfolioValuationService().value(position, source=Source(DataQuality.STALE), base_currency_code="USD", as_of=NOW)
    with pytest.raises(CurrencyConversionRequired): PortfolioValuationService().value(position, source=Source(currency="EUR"), base_currency_code="USD", as_of=NOW)
