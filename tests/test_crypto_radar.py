from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.analysis import AnalysisMetric, AnalysisResult
from app.crypto.catalog import CryptoCatalog
from app.crypto.radar import CryptoRadarService
from app.market_data.models import Candle, CandleInterval, ProviderAsset, Quote

NOW = datetime(2026, 10, 26, 12, 1, tzinfo=UTC)
SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')

class Repository:
    def __init__(self): self.rows = []; self.writes = 0
    def create(self, **kw):
        self.writes += 1
        row = SimpleNamespace(id=uuid4(), is_active=True, **kw)
        self.rows.append(row)
        return row
    def get_by_code(self, code): return next((r for r in self.rows if r.code == code), None)
    def get_by_market_and_code(self, market_id, code): return next((r for r in self.rows if r.market_id == market_id and r.code == code), None)
    def get_by_identity(self, **kw): return next((r for r in self.rows if all(getattr(r, k) == v for k, v in kw.items())), None)
    def get_by_provider_and_symbol(self, provider, symbol): return next((r for r in self.rows if r.provider == provider and r.provider_symbol == symbol), None)


def catalog():
    repos = {name: Repository() for name in ['currencies', 'markets', 'exchanges', 'assets', 'mappings']}
    return CryptoCatalog(**repos), repos

def instruments():
    return [ProviderAsset('bybit', symbol, symbol, 'CRYPTO', 'USDT', 'BYBIT', 'CRYPTO') for symbol in SYMBOLS]

def test_catalog_defaults_to_a_plan_without_writes_and_apply_is_idempotent():
    service, repos = catalog()
    plan = service.bootstrap(instruments(), symbols=SYMBOLS)
    assert plan['actions'] and not any(r.writes for r in repos.values())
    first = service.bootstrap(instruments(), symbols=SYMBOLS, apply=True)
    writes = sum(r.writes for r in repos.values())
    second = service.bootstrap(instruments(), symbols=SYMBOLS, apply=True)
    assert len(first['assets']) == 3 and writes == 9
    assert [a.id for a in second['assets']] == [a.id for a in first['assets']]
    assert sum(r.writes for r in repos.values()) == writes

def test_catalog_rejects_missing_or_wrong_instruments_before_writing():
    service, repos = catalog()
    with pytest.raises(ValueError): service.bootstrap(instruments()[:1], symbols=SYMBOLS, apply=True)
    assert not any(r.writes for r in repos.values())

class Provider:
    name = 'bybit'
    stale = False
    wrong_identity = False
    def get_quote(self, request):
        return Quote(uuid4() if self.wrong_identity else request.asset_id, request.provider_symbol, Decimal('100'), 'USDT', NOW-timedelta(seconds=300 if self.stale else 1), NOW, 'bybit', None)
    def get_history(self, request):
        seconds = 900 if request.interval == CandleInterval.FIFTEEN_MINUTES else 3600
        end = NOW.replace(minute=0, second=0)
        return tuple(Candle(request.asset_id, request.provider_symbol, end-timedelta(seconds=seconds*(200-i)), Decimal('100'), Decimal('101'), Decimal('99'), Decimal('100'), Decimal('10'), request.interval, 'bybit', NOW, None) for i in range(200))
    def get_liquidity(self, symbol): return None

class Engine:
    def analyze(self, candles, **kw):
        return AnalysisResult(candles[0].asset_id, 'analysis-v2', (AnalysisMetric('CLOSE', candles[-1].close), AnalysisMetric('TREND_DIRECTION', Decimal('1'))))

class Store:
    def __init__(self): self.quotes=[]; self.analyses=[]
    def save_quote(self, quote): self.quotes.append(quote)
    def save_analysis(self, asset, interval, candles, analysis): self.analyses.append((asset, interval, candles, analysis))

def asset(): return SimpleNamespace(id=uuid4(), symbol='BTCUSDT', is_active=True, asset_type='CRYPTO')

def test_scan_does_not_persist_by_default_and_records_both_windows_when_enabled():
    store=Store(); service=CryptoRadarService(provider=Provider(), engine=Engine(), store=store, clock=lambda: NOW)
    report=service.scan([asset()])
    assert report['pairs'][0]['status']=='READY' and not store.quotes and not store.analyses
    report=service.scan([asset()], persist=True)
    assert len(store.quotes)==1 and len(store.analyses)==2
    assert report['costs_status']=='CUSTOS_NAO_CONFIGURADOS'
    assert set(report['pairs'][0]['windows'])=={'15m','1h'}

def test_stale_quote_and_wrong_identity_cannot_create_analysis():
    for stale,wrong in [(True,False),(False,True)]:
        provider=Provider(); provider.stale=stale; provider.wrong_identity=wrong
        store=Store(); report=CryptoRadarService(provider=provider, engine=Engine(), store=store, clock=lambda: NOW).scan([asset()], persist=True)
        assert report['pairs'][0]['status']!='READY'
        assert not store.analyses and not store.quotes

def test_optional_liquidity_failure_does_not_discard_valid_technical_analysis():
    from app.market_data.errors import ProviderResponseError
    class NoBook(Provider):
        def get_liquidity(self, symbol): raise ProviderResponseError('unavailable book')
    report=CryptoRadarService(provider=NoBook(), engine=Engine(), clock=lambda: NOW).scan([asset()])
    assert report['pairs'][0]['status']=='READY'
    assert 'LIQUIDITY_UNAVAILABLE' in report['pairs'][0]['reasons']


def test_history_with_missing_candles_cannot_be_presented_as_ready():
    class Gap(Provider):
        def get_history(self, request):
            rows=super().get_history(request)
            return rows[:100]+rows[101:]
    from app.analysis.crypto import CryptoAnalysisEngine
    report=CryptoRadarService(provider=Gap(), engine=CryptoAnalysisEngine(), clock=lambda: NOW).scan([asset()])
    assert report['pairs'][0]['status']=='UNAVAILABLE'
    assert all(w['status']=='UNAVAILABLE' for w in report['pairs'][0]['windows'].values())

def test_quote_expiring_during_history_fetch_cannot_persist_analysis():
    time=[NOW]
    class Slow(Provider):
        def get_history(self, request):
            time[0]+=timedelta(seconds=121)
            return super().get_history(request)
    store=Store()
    report=CryptoRadarService(provider=Slow(),engine=Engine(),store=store,clock=lambda:time[0]).scan([asset()],persist=True)
    assert not store.analyses
    assert report['pairs'][0]['status']=='UNAVAILABLE'


def test_report_rechecks_quote_after_optional_snapshot_request():
    time=[NOW]
    class SlowBook(Provider):
        def get_liquidity(self, symbol):
            time[0]+=timedelta(seconds=121)
            return None
    report=CryptoRadarService(provider=SlowBook(),engine=Engine(),clock=lambda:time[0]).scan([asset()])
    assert report['pairs'][0]['status']=='UNAVAILABLE'
    assert 'STALE_OR_INVALID_QUOTE' in report['pairs'][0]['reasons']


def test_kraken_catalog_has_independent_assets_and_mappings():
    old,repos=catalog()
    old.bootstrap(instruments(),apply=True)
    service=CryptoCatalog(**repos,provider='kraken')
    items=[ProviderAsset('kraken',s,s,'CRYPTO','USDT','KRAKEN','CRYPTO') for s in SYMBOLS]
    report=service.bootstrap(items,apply=True)
    assert len(repos['assets'].rows)==6
    assert all(r.exchange_id==repos['exchanges'].rows[1].id for r in report['assets'])
    assert {r.provider for r in repos['mappings'].rows}=={'bybit','kraken'}
    before=sum(r.writes for r in repos.values())
    service.bootstrap(items,apply=True)
    assert sum(r.writes for r in repos.values())==before


def test_radar_kraken_identity_is_accepted_but_bybit_quote_is_rejected():
    from dataclasses import replace
    class Kraken(Provider):
        name='kraken'
        def get_quote(self,request):return replace(super().get_quote(request),provider='kraken')
        def get_history(self,request):return tuple(replace(r,provider='kraken') for r in super().get_history(request))
    report=CryptoRadarService(provider=Kraken(),engine=Engine(),clock=lambda:NOW).scan([asset()])
    assert report['provider']=='kraken' and report['pairs'][0]['status']=='READY'
    p=Kraken();p.get_quote=Provider().get_quote
    report=CryptoRadarService(provider=p,engine=Engine(),clock=lambda:NOW).scan([asset()])
    assert report['pairs'][0]['status']=='UNAVAILABLE'
    assert 'QUOTE_IDENTITY_MISMATCH' in report['pairs'][0]['reasons']


def test_kraken_boundary_crossing_uses_same_200_candle_window_on_repeat():
    import httpx
    from app.analysis.crypto import CryptoAnalysisEngine
    from app.market_data.http import ProviderHttpClient
    from app.market_data.providers.kraken import KrakenProvider
    time=[NOW.replace(minute=14,second=59)]
    crossed=[False]
    def respond(request):
        endpoint=request.url.path.split('/')[-1]
        if endpoint=='AssetPairs':
            result={'XBTUSDT':{'altname':'XBTUSDT','wsname':'XBT/USDT','base':'XXBT','quote':'USDT','status':'online'}}
        elif endpoint=='Trades':
            result={'XBTUSDT':[['100','1',str(int(time[0].timestamp())-1),'b','l','',1]],'last':'cursor'}
        else:
            seconds=int(request.url.params['interval'])*60
            if seconds==900 and not crossed[0]:
                time[0]+=timedelta(seconds=2);crossed[0]=True
            start=int(request.url.params['since'])
            end=int(time[0].timestamp())//seconds*seconds
            rows=[]
            for at in range(start,end+1,seconds):
                value=100+(at//seconds)%17
                rows.append([at,str(value),str(value+3),str(value-2),str(value+1),str(value),'10',1])
            result={'XBTUSDT':rows,'last':end}
        return httpx.Response(200,json={'error':[],'result':result})
    transport=ProviderHttpClient(base_url='https://api.kraken.com',transport=httpx.MockTransport(respond))
    provider=KrakenProvider(transport,clock=lambda:time[0])
    store=Store();record=asset()
    service=CryptoRadarService(provider=provider,engine=CryptoAnalysisEngine(),store=store,clock=lambda:time[0])
    for _ in range(2):
        report=service.scan([record],persist=True)
        assert report['pairs'][0]['status']=='READY'
    analyses=[entry for entry in store.analyses if entry[1]==CandleInterval.FIFTEEN_MINUTES]
    assert [len(entry[2]) for entry in analyses]==[200,200]
    assert analyses[0][2][-1].timestamp==analyses[1][2][-1].timestamp
    assert analyses[0][3].metrics==analyses[1][3].metrics
