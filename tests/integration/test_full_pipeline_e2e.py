"""Architectural E2E: deterministic fakes only, real local services, no network or secrets."""
import os
from datetime import UTC,datetime,timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.ai import AIAnalysisResponse,AIClassification,AIService,ValidatedAIContext
from app.alerts import AlertEngine,AlertPolicy,AlertService
from app.analysis import AnalysisEngine,AnalysisService
from app.backtesting import BacktestConfig,BacktestEngine,BacktestService
from app.market_data.ingestion import MarketDataIngestionService
from app.market_data.models import Candle,CandleInterval,DataQuality,Quote
from app.market_data.quality import QualityEngine,QualityPolicy
from app.opportunity import EvidenceCategory,MetricOperator,MetricRule,OpportunityEngine,OpportunityLevel,OpportunityPolicy,OpportunityService
from app.paper_trading import PaperAccount,PaperExecutionEngine,PaperSide,PaperTradingService

pytestmark=pytest.mark.integration
NOW=datetime(2026,8,21,tzinfo=UTC); ASSET=uuid4()
class Provider:
    name="deterministic"
    def get_quote(self,request):return Quote(request.asset_id,request.provider_symbol,Decimal("100"),"EUR",NOW,NOW,self.name,None)
    def get_history(self,request):return tuple(Candle(request.asset_id,request.provider_symbol,NOW-timedelta(days=4-i),Decimal(str(90+i*3)),Decimal(str(91+i*3)),Decimal(str(89+i*3)),Decimal(str(90+i*3)),Decimal("10"),request.interval,self.name,NOW,None) for i in range(5))
class Symbols:
    def get_by_asset_and_provider(self,*_):return SimpleNamespace(provider="deterministic",provider_symbol="ANY")
class Quotes:
    def create_from_quote(self,q):return SimpleNamespace(id=uuid4(),asset_id=q.asset_id,provider=q.provider,provider_symbol=q.provider_symbol,price=q.price,currency_code=q.currency_code,observed_at=q.timestamp,received_at=q.received_at,quality=q.quality.value)
class Candles:
    def __init__(self):self.rows=[]
    def create_many(self,items):
        self.rows=[SimpleNamespace(id=uuid4(),asset_id=x.asset_id,provider=x.provider,provider_symbol=x.provider_symbol,observed_at=x.timestamp,open=x.open,high=x.high,low=x.low,close=x.close,volume=x.volume,adjusted_close=x.adjusted_close,received_at=x.received_at,quality=x.quality.value) for x in items];return tuple(self.rows)
    def get_range(self,**_):return tuple(self.rows)
class Store:
    def create(self,**p):self.payload=p;return SimpleNamespace(id=uuid4(),**p)
    def create_many(self,**p):self.payload=p
class AI:
    def analyze(self,_):return AIAnalysisResponse(AIClassification.POSITIVE,Decimal("0.7"),("trend",),(),("model is interpretive",),"bounded facts")
class Alerts:
    def __init__(self):self.items={}
    def get_by_dedupe_key(self,k):return self.items.get(k)
    def get_latest_sent_for_asset(self,_):return None
    def create_pending(self,**p):x=SimpleNamespace(id=uuid4(),sent_at=None,**p);self.items[p["dedupe_key"]]=x;return x
    def mark_sent(self,*,alert_id,sent_at):return SimpleNamespace(id=alert_id,sent_at=sent_at)
    def mark_suppressed(self,*,alert_id,reason):return SimpleNamespace(id=alert_id,suppression_reason=reason)
    def mark_failed(self,**_):raise AssertionError
class Sender:
    def __init__(self):self.messages=[]
    def send_message(self,*args):self.messages.append(args)
class AccountStore:
    def __init__(self,account):self.account=account
    def get_by_id(self,_):return self.account
class OrderStore:
    def create(self,**_):return SimpleNamespace(id=uuid4())
    def mark_filled(self,**_):return None
class TradeStore:
    def create(self,**_):return None

@pytest.mark.skipif(os.getenv("RUN_FULL_PIPELINE_E2E")!="1",reason="RUN_FULL_PIPELINE_E2E=1 required")
def test_full_local_pipeline():
    policy=QualityPolicy(timedelta(days=1),timedelta(days=1),{CandleInterval.ONE_DAY:timedelta(days=10)},timedelta(seconds=1))
    candles=Candles();ingestion=MarketDataIngestionService(provider=Provider(),quality_engine=QualityEngine(policy),provider_symbols=Symbols(),quotes=Quotes(),candles=candles)
    quote=ingestion.ingest_quote(ASSET,evaluated_at=NOW);history=ingestion.ingest_history(ASSET,CandleInterval.ONE_DAY,NOW-timedelta(days=5),NOW,evaluated_at=NOW)
    analysis_store=Store();metric_store=Store();analysis=AnalysisService(candles=candles,engine=AnalysisEngine(),analyses=analysis_store,metrics=metric_store).analyze(asset_id=ASSET,provider="deterministic",interval=CandleInterval.ONE_DAY,start=NOW-timedelta(days=5),end=NOW,period=3)
    ai=AIService(provider=AI(),repository=Store(),provider_name="fake",model="fake",prompt_version="v1").analyze(context=ValidatedAIContext("asset","market",quote.record.price,"EUR",tuple((m.name,m.value) for m in analysis.metrics),NOW,"analysis-v1"),asset_id=ASSET,started_at=NOW,finished_at=NOW)
    opportunity=OpportunityService(engine=OpportunityEngine(OpportunityPolicy("v1",(MetricRule("RETURN",MetricOperator.GT,Decimal("0"),Decimal("80"),EvidenceCategory.TREND.value),MetricRule("SMA",MetricOperator.GT,Decimal("0"),Decimal("20"),EvidenceCategory.VOLUME.value)))),repository=Store()).assess(asset_id=ASSET,analysis_id=analysis_store.payload and uuid4(),metrics={m.name:m.value for m in analysis.metrics},quote_quality=quote.assessment.quality,reference_at=NOW,evaluated_at=NOW,ai_positive=ai.classification is AIClassification.POSITIVE)
    sender=Sender(); alert=AlertService(engine=AlertEngine(AlertPolicy(minimum_level=OpportunityLevel.INTERESTING)),repository=Alerts(),sender=sender).send(asset_id=ASSET,opportunity_id=uuid4(),recipient_id=1,recipient_authorized=True,level=opportunity.level,quality=quote.assessment.quality,decided_at=NOW,asset="asset",timestamp=NOW,price=quote.record.price,score=opportunity.score,production_ready=True,automation_enabled=True)
    assert quote.assessment.data.quality is DataQuality.VALID and all(x.data.quality is DataQuality.VALID for x in history.assessments) and sender.messages and alert.sent_at==NOW

@pytest.mark.skipif(os.getenv("RUN_FULL_PIPELINE_E2E")!="1",reason="RUN_FULL_PIPELINE_E2E=1 required")
def test_backtest_opportunity_paper_pipeline_is_walk_forward_and_replayable():
    history=tuple(Candle(ASSET,"ANY",NOW+timedelta(days=index),Decimal(str(10+index)),Decimal(str(11+index)),Decimal(str(9+index)),Decimal(str(10+index)),Decimal("1"),CandleInterval.ONE_DAY,"deterministic",NOW,DataQuality.VALID) for index in range(6))
    seen=[]
    def signal(window):
        seen.append(tuple(item.timestamp for item in window));return SimpleNamespace(level=OpportunityLevel.INTERESTING,score=Decimal("50"))
    events,summary=BacktestEngine().run(history,config=BacktestConfig(2,1,"v","p"),signal=signal)
    assert events and all(max(window)<=event.signal_at for window,event in zip(seen,events))
    account=PaperAccount(uuid4(),Decimal("100"));service=PaperTradingService(engine=PaperExecutionEngine(),accounts=AccountStore(account),orders=OrderStore(),trades=TradeStore())
    updated,trade=service.execute_next_open(account_id=account.account_id,asset_id=ASSET,side=PaperSide.BUY,quantity=Decimal("2"),requested_at=history[0].timestamp,next_candle=history[1])
    assert trade.price==history[1].open and updated.cash==Decimal("78") and dict(updated.positions)[ASSET]==Decimal("2")
