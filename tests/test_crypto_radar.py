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
