from datetime import UTC,datetime
from decimal import Decimal
from uuid import uuid4
import pytest
from app.market_data.models import DataQuality
from app.portfolio import FxRate,PortfolioCalculator,PortfolioTransaction,PortfolioValuationService,TransactionType
from app.portfolio.core import Valuation,PortfolioError
NOW=datetime(2026,1,1,tzinfo=UTC); ASSET=uuid4()
class Source:
    def get_valuation(self,*_,**__):return Valuation(Decimal("100"),"JPY",DataQuality.VALID,NOW)
class Fx:
    def __init__(self,q):self.q=q
    def get_fx_rate(self,**_):return FxRate("JPY","CHF",Decimal("0.01"),self.q,NOW)
def test_arbitrary_currency_and_exchange_independent_fx():
    tx=PortfolioTransaction(ASSET,TransactionType.BUY,Decimal("1"),Decimal("1"),Decimal("0"),"EUR",NOW)
    position=PortfolioCalculator().calculate([tx]).positions
    assert PortfolioValuationService().value(position,source=Source(),base_currency_code="CHF",as_of=NOW,fx_source=Fx(DataQuality.VALID))[0].market_value==Decimal("1.00")
@pytest.mark.parametrize("quality",[None,DataQuality.STALE,DataQuality.INCOMPLETE,DataQuality.OUTLIER,DataQuality.INVALID])
def test_fx_non_valid_is_rejected(quality):
    tx=PortfolioTransaction(ASSET,TransactionType.BUY,Decimal("1"),Decimal("1"),Decimal("0"),"EUR",NOW);position=PortfolioCalculator().calculate([tx]).positions
    with pytest.raises((PortfolioError,AttributeError)):PortfolioValuationService().value(position,source=Source(),base_currency_code="CHF",as_of=NOW,fx_source=Fx(quality))
