from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.market_data.contracts import AssetSearchRequest, HistoryRequest, QuoteRequest, MarketDataProvider
from app.market_data.errors import ProviderCapabilityError, ProviderResponseError
from app.market_data.http import ProviderHttpClient

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)
ASSET = uuid4()
META = {'altname':'XBTUSDT', 'wsname':'XBT/USDT', 'base':'XXBT', 'quote':'USDT', 'status':'online'}
TRADE = ['68000.123456789', '0.1', str(int(NOW.timestamp())-2)+'.123456', 'b', 'l', '', 1]

def row(at):return [int(at.timestamp()), '100', '103', '99', '102', '101', '2.5', 3]

def make(payloads=None, metadata=None, requests=None, metadata_key="XBTUSDT"):
    from app.market_data.providers.kraken import KrakenProvider
    def respond(req):
        if requests is not None:requests.append(req)
        value = {'error':[], 'result':{metadata_key:metadata or META}} if req.url.path.endswith('AssetPairs') else payloads[req.url.path.split('/')[-1]]
        return httpx.Response(200,json=value)
    client=ProviderHttpClient(base_url='https://api.kraken.com',transport=httpx.MockTransport(respond))
    return KrakenProvider(client,clock=lambda:NOW)

def history(start=None,end=NOW):
    from app.market_data.models import CandleInterval
    return HistoryRequest(ASSET,'BTCUSDT',CandleInterval.FIFTEEN_MINUTES,start or NOW-timedelta(hours=1),end)

def test_quote_uses_canonical_bitcoin_identity_and_actual_trade_price_time():
    requests=[]
    p=make({'Trades':{'error':[],'result':{'XBTUSDT':[TRADE],'last':'cursor'}}},requests=requests)
    q=p.get_quote(QuoteRequest(ASSET,'BTCUSDT'))
    assert isinstance(p,MarketDataProvider)
    assert q.price==Decimal('68000.123456789') and q.timestamp==NOW-timedelta(seconds=2)+timedelta(microseconds=123456)
    assert (q.provider,q.currency_code,q.provider_symbol,q.asset_id)==('kraken','USDT','BTCUSDT',ASSET)
    assert dict(requests[0].url.params)=={'pair':'XBTUSDT'}
    assert dict(requests[1].url.params)=={'pair':'XBTUSDT','count':'1'}
    assert not requests[1].headers.get('authorization')
    p.get_quote(QuoteRequest(ASSET,'BTCUSDT'))
    assert sum(r.url.path.endswith('AssetPairs') for r in requests)==1

@pytest.mark.parametrize('payload', [None,[],{}, {'error':['EQuery:Unknown asset pair'],'result':{}}, {'error':False,'result':{}}, {'error':[],'result':{'ETHUSDT':[TRADE],'last':'c'}}, {'error':[],'result':{'XBTUSDT':[]}}])
def test_quote_rejects_failed_or_wrong_market_responses(payload):
    with pytest.raises(ProviderResponseError):make({'Trades':payload}).get_quote(QuoteRequest(ASSET,'BTCUSDT'))

@pytest.mark.parametrize('field,value', [(0,'NaN'),(0,'0'),(0,123),(1,'-1'),(2,'Infinity'),(2,str(int(NOW.timestamp())+121))])
def test_quote_rejects_invalid_numbers_and_future_time(field,value):
    trade=deepcopy(TRADE);trade[field]=value
    with pytest.raises(ProviderResponseError):make({'Trades':{'error':[],'result':{'XBTUSDT':[trade]}}}).get_quote(QuoteRequest(ASSET,'BTCUSDT'))

@pytest.mark.parametrize('changes',[{'quote':'USD'},{'status':'cancel_only'},{'altname':'ETHUSDT'},{'wsname':'ETH/USDT'},{'base':''}])
def test_only_online_matching_usdt_instruments_are_accepted(changes):
    with pytest.raises(ProviderResponseError):make(metadata={**META,**changes}).get_assets(AssetSearchRequest(query='BTCUSDT'))

def test_catalog_metadata_has_separate_exchange_identity():
    assets=make().get_assets(AssetSearchRequest(query='BTCUSDT'))
    assert len(assets)==1
    assert (assets[0].provider,assets[0].exchange_code,assets[0].provider_symbol)==('kraken','KRAKEN','BTCUSDT')

def test_history_sorts_and_filters_open_candles_and_requested_end():
    rows=[row(NOW-timedelta(minutes=m)) for m in [0,15,30,45,60]]
    p=make({'OHLC':{'error':[],'result':{'XBTUSDT':rows,'last':int(NOW.timestamp())}}})
    candles=p.get_history(history(end=NOW-timedelta(minutes=15)))
    assert len(candles)==4
    assert [c.timestamp for c in candles]==sorted(c.timestamp for c in candles)
    assert candles[-1].timestamp==NOW-timedelta(minutes=15)
    assert all(c.provider=='kraken' and c.provider_symbol=='BTCUSDT' and c.volume==Decimal('2.5') for c in candles)

def test_history_rejects_duplicate_conflicts_and_invalid_ohlc():
    for values in [[row(NOW-timedelta(minutes=60)),row(NOW-timedelta(minutes=60))], [row(NOW-timedelta(minutes=60))]]:
        if len(values)==2:values[1][4]='101'
        else:values[0][2]='90'
        with pytest.raises(ProviderResponseError):make({'OHLC':{'error':[],'result':{'XBTUSDT':values}}}).get_history(history())

def test_history_identical_duplicates_are_deduplicated():
    values=[row(NOW-timedelta(minutes=60))]*2
    assert len(make({'OHLC':{'error':[],'result':{'XBTUSDT':values}}}).get_history(history()))==1

def test_history_refuses_kraken_retention_truncation():
    with pytest.raises(ProviderCapabilityError):make().get_history(history(start=NOW-timedelta(days=10)))
    with pytest.raises(ProviderResponseError):make({'OHLC':{'error':[],'result':{'XBTUSDT':[row(NOW-timedelta(minutes=30))]}}}).get_history(history())


def test_metadata_market_key_must_match_requested_pair():
    with pytest.raises(ProviderResponseError):
        make(metadata_key='ETHUSDT').get_assets(AssetSearchRequest(query='BTCUSDT'))
