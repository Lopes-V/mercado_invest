from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from app.backtesting import BacktestConfig, BacktestEngine
from app.market_data.models import Candle,CandleInterval,DataQuality
from app.opportunity import OpportunityAssessment,OpportunityLevel
from app.paper_trading import PaperAccount,PaperExecutionEngine,PaperOrder,PaperSide
ASSET=uuid4(); NOW=datetime(2026,1,1,tzinfo=UTC)
def candles():
    return tuple(Candle(ASSET,"T",NOW+timedelta(days=i),Decimal(str(10+i)),Decimal(str(10+i)),Decimal(str(10+i)),Decimal(str(10+i)),None,CandleInterval.ONE_DAY,"test",NOW,DataQuality.VALID) for i in range(5))
def test_backtest_signal_only_sees_history_and_forward_is_after_signal():
    seen=[]
    def signal(window): seen.append(window); return OpportunityAssessment(OpportunityLevel.INTERESTING,Decimal("50"),2,())
    events,summary=BacktestEngine().run(candles(),config=BacktestConfig(2,1,"v","p"),signal=signal)
    assert events and all(max(item.timestamp for item in window) <= event.signal_at for window,event in zip(seen,events)) and summary.signals==len(events)
def test_paper_fill_uses_next_open_and_blocks_cash_or_oversell():
    account=PaperAccount(uuid4(),Decimal("100")); order=PaperOrder(account.account_id,ASSET,PaperSide.BUY,Decimal("2"),NOW)
    updated,trade=PaperExecutionEngine(slippage=Decimal("0.1"),fee=Decimal("1")).execute(account,order,next_candle=candles()[1])
    assert trade.price==Decimal("12.1") and updated.cash==Decimal("74.8")
    with pytest.raises(ValueError): PaperExecutionEngine().execute(account,PaperOrder(account.account_id,ASSET,PaperSide.SELL,Decimal("1"),NOW),next_candle=candles()[1])
