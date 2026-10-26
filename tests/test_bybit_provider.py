from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from app.market_data.contracts import AssetSearchRequest, HistoryRequest, MarketDataProvider, MarketStatusRequest, QuoteRequest
from app.market_data.errors import ProviderCapabilityError, ProviderResponseError, ProviderTransportError
from app.market_data.http import ProviderHttpClient
from app.market_data.models import CandleInterval
from app.market_data.providers.bybit import BybitProvider

ASSET = UUID('11111111-1111-1111-1111-111111111111')
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
START = NOW - timedelta(hours=2)


def ms(value):
    return int(value.timestamp() * 1000)


def envelope(rows, **changes):
    result = {'category': 'spot', 'list': rows}
    result.update(changes)
    return {'retCode': 0, 'result': result, 'time': ms(NOW)}


def instrument(**changes):
    row = {'symbol': 'BTCUSDT', 'baseCoin': 'BTC', 'quoteCoin': 'USDT', 'status': 'Trading'}
    row.update(changes)
    return row


def trade(**changes):
    row = {'symbol': 'BTCUSDT', 'price': '68000.123456789', 'time': str(ms(NOW) - 1234)}
    row.update(changes)
    return row


def kline(timestamp, **changes):
    row = [str(ms(timestamp)), '100', '103', '99', '102.123456789', '1.25', '127.5']
    for key, value in changes.items():
        row[int(key)] = value
    return row


def provider_for(payloads=None, *, instruments=None, requests=None, handler=None):
    payloads = payloads or {}
    def respond(request):
        if requests is not None:
            requests.append(request)
        if handler is not None:
            response = handler(request)
            if response is not None:
                return response
        if request.url.path.endswith('instruments-info'):
            return httpx.Response(200, json=envelope([instrument()] if instruments is None else instruments))
        return httpx.Response(200, json=payloads[request.url.path])
    return BybitProvider(ProviderHttpClient(base_url='https://api.bybit.com', transport=httpx.MockTransport(respond), sleep=lambda _: None), clock=lambda: NOW)


def quote_request():
    return QuoteRequest(ASSET, 'BTCUSDT')


def history_request(start=START, end=NOW, interval=CandleInterval.FIFTEEN_MINUTES):
    return HistoryRequest(ASSET, 'BTCUSDT', interval, start, end)


def test_quote_uses_recent_trade_time_decimal_and_exact_public_spot_parameters():
    requests = []
    provider = provider_for({'/v5/market/recent-trade': envelope([trade()])}, requests=requests)
    quote = provider.get_quote(quote_request())
    assert isinstance(provider, MarketDataProvider)
    assert quote.price == Decimal('68000.123456789')
    assert quote.timestamp == NOW - timedelta(milliseconds=1234)
    assert quote.received_at == NOW
    assert (quote.provider, quote.currency_code, quote.quality) == ('bybit', 'USDT', None)
    assert quote.asset_id == ASSET
    assert dict(requests[0].url.params) == {'category': 'spot', 'symbol': 'BTCUSDT'}
    assert requests[1].url.path == '/v5/market/recent-trade'
    assert dict(requests[1].url.params) == {'category': 'spot', 'symbol': 'BTCUSDT', 'limit': '1'}
    assert not requests[1].headers.get('authorization')
    provider.get_quote(quote_request())
    assert sum(r.url.path.endswith('instruments-info') for r in requests) == 1


@pytest.mark.parametrize('payload', [None, [], {}, {'retCode': 10001}, {'retCode': False}, envelope([], category='linear'), envelope([]), envelope([trade(), trade()]), envelope([trade(symbol='ETHUSDT')]), envelope([trade(price='NaN')]), envelope([trade(price='Infinity')]), envelope([trade(price='0')]), envelope([trade(price=100)]), envelope([trade(time='invalid')]), envelope([trade(time=str(ms(NOW + timedelta(minutes=3))))])])
def test_quote_rejects_invalid_payloads(payload):
    with pytest.raises(ProviderResponseError):
        provider_for({'/v5/market/recent-trade': payload}).get_quote(quote_request())


@pytest.mark.parametrize('changes', [{'symbol': 'ETHUSDT'}, {'quoteCoin': 'USDC'}, {'baseCoin': 'ETH'}, {'status': 'Settled'}, {'baseCoin': ''}])
def test_quote_requires_matching_trading_usdt_instrument(changes):
    with pytest.raises(ProviderResponseError):
        provider_for(instruments=[instrument(**changes)]).get_quote(quote_request())


def test_assets_filters_to_trading_usdt_and_caches_metadata():
    requests = []
    provider = provider_for({'/v5/market/recent-trade': envelope([trade()])}, instruments=[instrument(), instrument(symbol='ETHUSDT', baseCoin='ETH'), instrument(symbol='BTCUSDC', quoteCoin='USDC'), instrument(symbol='SOLUSDT', baseCoin='SOL', status='Settled')], requests=requests)
    assets = provider.get_assets(AssetSearchRequest(market_code='CRYPTO', exchange_code='BYBIT'))
    assert [a.provider_symbol for a in assets] == ['BTCUSDT', 'ETHUSDT']
    assert [(a.provider, a.asset_type, a.currency_code, a.exchange_code, a.market_code) for a in assets] == [('bybit', 'CRYPTO', 'USDT', 'BYBIT', 'CRYPTO')] * 2
    assert [a.provider_symbol for a in provider.get_assets(AssetSearchRequest(query='BTCUSDT'))] == ['BTCUSDT']
    provider.get_quote(quote_request())
    assert sum(r.url.path.endswith('instruments-info') for r in requests) == 1


def test_assets_rejects_malformed_rows_instead_of_skipping_them():
    with pytest.raises(ProviderResponseError):
        provider_for(instruments=[instrument(), {}]).get_assets(AssetSearchRequest())


def test_assets_does_not_claim_other_markets():
    with pytest.raises(ProviderCapabilityError):
        provider_for().get_assets(AssetSearchRequest(exchange_code='B3'))


def test_history_sorts_reversed_rows_filters_open_candle_and_preserves_base_volume():
    requests = []
    rows = [kline(NOW), kline(START + timedelta(minutes=15)), kline(START)]
    candles = provider_for({'/v5/market/kline': envelope(rows, symbol='BTCUSDT')}, requests=requests).get_history(history_request())
    assert [c.timestamp for c in candles] == [START, START + timedelta(minutes=15)]
    assert candles[0].volume == Decimal('1.25')
    assert candles[0].close == Decimal('102.123456789')
    assert candles[0].quality is None
    assert candles[0].received_at == NOW
    assert dict(requests[-1].url.params) == {'category': 'spot', 'symbol': 'BTCUSDT', 'interval': '15', 'start': str(ms(START)), 'end': str(ms(NOW)), 'limit': '1000'}


def test_history_paginates_backwards_and_deduplicates_identical_overlaps():
    start = NOW - timedelta(minutes=1002)
    rows = [kline(start + timedelta(minutes=i)) for i in range(1, 1001)]
    pages = [list(reversed(rows)), [rows[0], kline(start)]]
    requests = []
    def handler(request):
        if request.url.path.endswith('/kline'):
            return httpx.Response(200, json=envelope(pages.pop(0), symbol='BTCUSDT'))
    candles = provider_for(requests=requests, handler=handler).get_history(history_request(start, NOW, CandleInterval.ONE_MINUTE))
    assert len(candles) == 1001
    assert candles[0].timestamp == start
    assert candles[-1].timestamp == start + timedelta(minutes=1000)
    history_calls = [r for r in requests if r.url.path.endswith('/kline')]
    assert len(history_calls) == 2
    assert int(history_calls[1].url.params['end']) == ms(start + timedelta(minutes=1)) - 1


def test_history_rejects_conflicting_duplicate_even_if_turnover_differs():
    first = kline(START)
    other = deepcopy(first)
    other[6] = '999'
    with pytest.raises(ProviderResponseError, match='conflit'):
        provider_for({'/v5/market/kline': envelope([first, other], symbol='BTCUSDT')}).get_history(history_request())


@pytest.mark.parametrize('payload', [envelope([], symbol='ETHUSDT'), envelope([], symbol='BTCUSDT', category='linear'), envelope([[]], symbol='BTCUSDT'), envelope([kline(START, **{'1': 'NaN'})], symbol='BTCUSDT'), envelope([kline(START, **{'2': '98'})], symbol='BTCUSDT'), envelope([kline(START, **{'5': None})], symbol='BTCUSDT'), envelope([kline(START, **{'5': '-1'})], symbol='BTCUSDT'), envelope([kline(START - timedelta(minutes=15))], symbol='BTCUSDT'), envelope([kline(NOW + timedelta(minutes=15))], symbol='BTCUSDT')])
def test_history_rejects_invalid_identity_rows_ohlcv_and_range(payload):
    with pytest.raises(ProviderResponseError):
        provider_for({'/v5/market/kline': payload}).get_history(history_request())


def test_history_empty_range_returns_no_fabricated_candles():
    assert provider_for({'/v5/market/kline': envelope([], symbol='BTCUSDT')}).get_history(history_request()) == ()


@pytest.mark.parametrize('history', [history_request(start=None), history_request(end=None), history_request(interval=CandleInterval.ONE_MONTH)])
def test_history_requires_explicit_range_and_supported_fixed_interval(history):
    with pytest.raises(ProviderCapabilityError):
        provider_for().get_history(history)


def test_liquidity_has_separate_snapshot_time_and_midpoint_spread_bps():
    requests = []
    ticker = {'symbol': 'BTCUSDT', 'bid1Price': '99', 'ask1Price': '101', 'volume24h': '4.123456789', 'turnover24h': '412.3456789'}
    payload = envelope([ticker])
    payload['time'] = ms(NOW) - 800
    liquidity = provider_for({'/v5/market/tickers': payload}, requests=requests).get_liquidity('BTCUSDT')
    assert liquidity.symbol == 'BTCUSDT'
    assert (liquidity.bid, liquidity.ask) == (Decimal('99'), Decimal('101'))
    assert liquidity.volume24h == Decimal('4.123456789')
    assert liquidity.turnover24h == Decimal('412.3456789')
    assert liquidity.timestamp == NOW - timedelta(milliseconds=800)
    assert liquidity.spread_bps == Decimal('200')
    assert dict(requests[-1].url.params) == {'category': 'spot', 'symbol': 'BTCUSDT'}


@pytest.mark.parametrize('changes', [{'symbol': 'ETHUSDT'}, {'bid1Price': '102'}, {'bid1Price': '0'}, {'ask1Price': 'NaN'}, {'volume24h': None}, {'turnover24h': '-1'}])
def test_liquidity_rejects_invalid_snapshot(changes):
    row = {'symbol': 'BTCUSDT', 'bid1Price': '99', 'ask1Price': '101', 'volume24h': '4', 'turnover24h': '400'}
    row.update(changes)
    with pytest.raises(ProviderResponseError):
        provider_for({'/v5/market/tickers': envelope([row])}).get_liquidity('BTCUSDT')


def test_market_status_is_explicitly_unsupported():
    with pytest.raises(ProviderCapabilityError):
        provider_for().get_market_status(MarketStatusRequest(market_id=ASSET, provider_market_code='CRYPTO'))


def test_transport_errors_remain_provider_errors():
    def handler(request):
        raise httpx.ConnectError('temporary', request=request)
    with pytest.raises(ProviderTransportError):
        provider_for(handler=handler).get_quote(quote_request())


@pytest.mark.parametrize('timestamp', [START + timedelta(seconds=1), START + timedelta(milliseconds=1)])
def test_history_rejects_candles_misaligned_with_requested_interval(timestamp):
    with pytest.raises(ProviderResponseError, match='alinh'):
        provider_for({'/v5/market/kline': envelope([kline(timestamp)], symbol='BTCUSDT')}).get_history(history_request())


def test_history_rejects_conflicting_overlapping_pages():
    start = NOW - timedelta(minutes=1002)
    rows = [kline(start + timedelta(minutes=i)) for i in range(1, 1001)]
    conflicting = deepcopy(rows[0])
    conflicting[4] = '101'
    pages = [list(reversed(rows)), [conflicting, kline(start)]]
    def handler(request):
        if request.url.path.endswith('/kline'):
            return httpx.Response(200, json=envelope(pages.pop(0), symbol='BTCUSDT'))
    with pytest.raises(ProviderResponseError, match='conflit'):
        provider_for(handler=handler).get_history(history_request(start, NOW, CandleInterval.ONE_MINUTE))


@pytest.mark.parametrize('time', [None, '', True, '-1', 10**30])
def test_liquidity_requires_real_valid_snapshot_timestamp(time):
    row = {'symbol': 'BTCUSDT', 'bid1Price': '99', 'ask1Price': '101', 'volume24h': '4', 'turnover24h': '400'}
    payload = envelope([row])
    payload['time'] = time
    with pytest.raises(ProviderResponseError):
        provider_for({'/v5/market/tickers': payload}).get_liquidity('BTCUSDT')


@pytest.mark.parametrize('symbol', ['btcusdt', 'BTCUSD', 'BTC/USDT', 'BTCUSDT?category=linear'])
def test_symbol_validation_prevents_unsupported_or_ambiguous_identity(symbol):
    with pytest.raises(ProviderCapabilityError):
        provider_for().get_quote(QuoteRequest(ASSET, symbol))


def test_retryable_http_failure_uses_shared_transport_retries():
    count = 0
    def handler(request):
        nonlocal count
        if request.url.path.endswith('/recent-trade'):
            count += 1
            if count == 1:
                return httpx.Response(503)
            return httpx.Response(200, json=envelope([trade()]))
    quote = provider_for(handler=handler).get_quote(quote_request())
    assert quote.price == Decimal('68000.123456789')
    assert count == 2
