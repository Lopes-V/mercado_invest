from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.analysis import AnalysisMetric, AnalysisResult
from app.crypto.storage import CryptoStore
from app.market_data.models import Candle, CandleInterval, DataQuality


class Query:
    def __init__(self, client, name):self.client=client;self.name=name;self.filters={}
    def select(self, fields):return self
    def eq(self, key, value):self.filters[key]=value;return self
    def gte(self, *args):return self
    def lte(self, *args):return self
    def limit(self, *args):return self
    def execute(self):
        return SimpleNamespace(data=[r for r in self.client.rows[self.name] if all(r.get(k)==v for k,v in self.filters.items())])
class Client:
    def __init__(self):self.rows={name:[] for name in ['market_candles','analyses','analysis_metrics']}
    def table(self,name):return Query(self,name)

def setup(provider="bybit"):
    client=Client();store=CryptoStore(client,provider=provider);asset=SimpleNamespace(id=uuid4(),symbol="BTCUSDT")
    at=datetime(2026,10,26,tzinfo=UTC)
    candle=Candle(asset.id,'BTCUSDT',at,Decimal('100'),Decimal('101'),Decimal('99'),Decimal('100'),Decimal('5'),CandleInterval.FIFTEEN_MINUTES,provider,at,DataQuality.VALID)
    def save_candles(candles):
        for c in candles:client.rows['market_candles'].append({'asset_id':str(c.asset_id),'provider':c.provider,'interval':'15m','observed_at':c.timestamp.isoformat(),'provider_symbol':c.provider_symbol,**{name:str(getattr(c,name)) if getattr(c,name) is not None else None for name in ['open','high','low','close','volume','adjusted_close']}})
    def save_analysis(**kw):
        record={'id':str(uuid4()),**{k:v.isoformat() if isinstance(v,datetime) else str(v) for k,v in kw.items()}}
        client.rows['analyses'].append(record);return SimpleNamespace(id=record['id'])
    def save_metrics(analysis_id,metrics):
        for m in metrics:client.rows['analysis_metrics'].append({'analysis_id':str(analysis_id),'metric_name':m.name,'metric_value':str(m.value),'reference_period':m.reference_period})
    store.candles=SimpleNamespace(create_many=save_candles)
    store.analyses=SimpleNamespace(create=save_analysis)
    store.metrics=SimpleNamespace(create_many=save_metrics)
    result=AnalysisResult(asset.id,'analysis-v2',(AnalysisMetric('RSI',Decimal('50'),14),))
    return store,client,asset,candle,result

def test_identical_repeated_facts_do_not_duplicate_candles_analyses_or_metrics():
    store,c,a,candle,result=setup()
    first=store.save_analysis(a,candle.interval,(candle,),result)
    second=store.save_analysis(a,candle.interval,(candle,),result)
    assert str(first)==str(second)
    assert [len(rows) for rows in c.rows.values()]==[1,1,1]

def test_a_conflicting_candle_is_not_silently_overwritten():
    store,c,a,candle,result=setup()
    store.save_analysis(a,candle.interval,(candle,),result)
    c.rows['market_candles'][0]['close']='99'
    with pytest.raises(ValueError,match='IMMUTABLE_CANDLE_CONFLICT'):store.save_analysis(a,candle.interval,(candle,),result)
    assert c.rows['market_candles'][0]['close']=='99'

def test_a_conflicting_metric_is_not_silently_overwritten():
    store,c,a,candle,result=setup()
    store.save_analysis(a,candle.interval,(candle,),result)
    c.rows['analysis_metrics'][0]['metric_value']='42'
    with pytest.raises(ValueError,match='IMMUTABLE_METRIC_CONFLICT'):store.save_analysis(a,candle.interval,(candle,),result)
    assert c.rows['analysis_metrics'][0]['metric_value']=='42'

def test_numeric_database_scale_is_stable_on_repeated_analysis():
    store,c,a,candle,_=setup()
    result=AnalysisResult(a.id,'analysis-v2',(AnalysisMetric('RSI',Decimal('50.12345678901234567890123'),14),))
    # Model the real numeric(38,18) database representation, not an arbitrary float.
    def database_insert(analysis_id,metrics):
        for metric in metrics:
            c.rows['analysis_metrics'].append({'analysis_id':str(analysis_id),'metric_name':metric.name,'metric_value':str(metric.value.quantize(Decimal('1e-18'))),'reference_period':metric.reference_period})
    store.metrics=SimpleNamespace(create_many=database_insert)
    store.save_analysis(a,candle.interval,(candle,),result)
    store.save_analysis(a,candle.interval,(candle,),result)
    assert len(c.rows['analysis_metrics'])==1

def test_database_numeric_accepts_exact_schema_boundary_without_context_rounding():
    from app.crypto.storage import database_numeric
    value=Decimal('99999999999999999999.999999999999999999')
    assert database_numeric(value)==value


def test_kraken_candles_are_read_by_provider_and_remain_idempotent():
    store,c,a,candle,result=setup('kraken')
    first=store.save_analysis(a,candle.interval,(candle,),result)
    second=store.save_analysis(a,candle.interval,(candle,),result)
    assert str(first)==str(second)
    assert len(c.rows['market_candles'])==1
    assert c.rows['market_candles'][0]['provider']=='kraken'


def test_store_rejects_cross_provider_candles_before_inserting():
    from dataclasses import replace
    store,c,a,candle,result=setup('kraken')
    with pytest.raises(ValueError,match='IDENTITY'):
        store.save_analysis(a,candle.interval,(replace(candle,provider='bybit'),),result)
    assert not any(c.rows.values())
