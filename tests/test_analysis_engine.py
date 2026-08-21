from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from app.analysis import AnalysisEngine, AnalysisError
from app.market_data.models import Candle, CandleInterval, DataQuality

def candle(offset, close, quality=DataQuality.VALID):
    now = datetime(2026,1,1,tzinfo=UTC)+timedelta(days=offset); value=Decimal(close)
    return Candle(uuid4() if offset == 99 else ASSET,"X",now,value,value,value,value,None,CandleInterval.ONE_DAY,"test",now,quality)
ASSET=uuid4()
def make(close):
    now=datetime(2026,1,1,tzinfo=UTC); return [Candle(ASSET,"X",now+timedelta(days=i),Decimal(value),Decimal(value),Decimal(value),Decimal(value),Decimal("1"),CandleInterval.ONE_DAY,"test",now,DataQuality.VALID) for i,value in enumerate(close)]
def test_metrics_decimal_and_wilder_rsi():
    result=AnalysisEngine().analyze(make(["10","11","12","11","12"]),period=3)
    metrics={item.name:item.value for item in result.metrics}
    assert metrics["RETURN"] == Decimal("0.2") and metrics["RSI"] > 0 and metrics["VOLATILITY"] >= 0
def test_rejects_non_valid_and_duplicate_timestamps():
    values=make(["10","11"]); values[1]=Candle(ASSET,"X",values[0].timestamp,Decimal("11"),Decimal("11"),Decimal("11"),Decimal("11"),None,CandleInterval.ONE_DAY,"test",values[0].received_at,DataQuality.VALID)
    with pytest.raises(AnalysisError): AnalysisEngine().analyze(values)
    bad=make(["10"]); bad[0]=Candle(ASSET,"X",bad[0].timestamp,Decimal("10"),Decimal("10"),Decimal("10"),Decimal("10"),None,CandleInterval.ONE_DAY,"test",bad[0].received_at,DataQuality.STALE)
    with pytest.raises(AnalysisError): AnalysisEngine().analyze(bad)
