"""Throwaway probe: no production imports, credentials or database writes."""
import json
import os
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProbeError(Exception):
    pass


def request(endpoint, **params):
    url = 'https://api.kraken.com/0/public/' + endpoint
    if params:
        url += '?' + urlencode(params)
    try:
        with urlopen(Request(url, headers={'User-Agent': 'public-market-api-smoke/1'}), timeout=15) as response:
            payload = json.load(response, parse_float=Decimal)
    except HTTPError as error:
        raise ProbeError('HTTP_' + str(error.code)) from None
    except (URLError, TimeoutError):
        raise ProbeError('NETWORK_ERROR') from None
    except (ValueError, UnicodeError):
        raise ProbeError('INVALID_JSON') from None
    if not isinstance(payload, dict) or payload.get('error') != []:
        raise ProbeError('API_ERROR')
    if not isinstance(payload.get('result'), dict):
        raise ProbeError('INVALID_RESULT')
    return payload['result']


def positive(value, allow_zero=False):
    number = Decimal(str(value))
    if not number.is_finite() or (number < 0 if allow_zero else number <= 0):
        raise ProbeError('INVALID_NUMBER')
    return number


def sole_series(result):
    entries = [value for key, value in result.items() if key != 'last']
    if len(entries) != 1:
        raise ProbeError('AMBIGUOUS_PAIR')
    return entries[0]


report = {'provider': 'kraken', 'checked_at': datetime.now(UTC).isoformat(), 'pairs': []}
summary = []
try:
    server_time = request('Time')['unixtime']
    if abs(time.time() - int(server_time)) > 120:
        raise ProbeError('SERVER_TIME_SKEW')
    report['time'] = 'PASS'
    summary.append('time=PASS')
except (ProbeError, ValueError, KeyError, TypeError) as error:
    report['time'] = str(error) if isinstance(error, ProbeError) else type(error).__name__
    summary.append('time=' + report['time'])

for display, pair in [('BTCUSDT', 'XBTUSDT'), ('ETHUSDT', 'ETHUSDT'), ('SOLUSDT', 'SOLUSDT')]:
    result = {'symbol': display, 'api_pair': pair, 'checks': {}, 'status': 'FAIL'}
    report['pairs'].append(result)
    checks = result['checks']
    for operation in ['metadata', 'ticker', 'trades', '15m', '1h']:
        try:
            if operation == 'metadata':
                metadata = sole_series(request('AssetPairs', pair=pair))
                if metadata.get('altname') != pair or metadata.get('quote') != 'USDT' or metadata.get('status') != 'online':
                    raise ProbeError('PAIR_NOT_ONLINE_USDT')
                result['base'] = metadata['base']
                result['quote_currency'] = metadata['quote']
            elif operation == 'ticker':
                ticker = sole_series(request('Ticker', pair=pair))
                result['price'] = str(positive(ticker['c'][0]))
                result['bid'] = str(positive(ticker['b'][0]))
                result['ask'] = str(positive(ticker['a'][0]))
                result['volume_24h'] = str(positive(ticker['v'][1], allow_zero=True))
                if Decimal(result['bid']) > Decimal(result['ask']):
                    raise ProbeError('CROSSED_BOOK')
                result['ticker_received_at'] = datetime.now(UTC).isoformat()
            elif operation == 'trades':
                trades = sole_series(request('Trades', pair=pair, count=1))
                if not isinstance(trades, list) or not trades:
                    raise ProbeError('NO_TRADES')
                latest = max(Decimal(str(row[2])) for row in trades)
                age = Decimal(str(time.time())) - latest
                result['latest_trade_at'] = datetime.fromtimestamp(float(latest), UTC).isoformat()
                result['trade_age_seconds'] = str(age.quantize(Decimal('0.1')))
                if age < -120 or age > 120:
                    raise ProbeError('TRADE_NOT_FRESH_120S')
            else:
                minutes = 15 if operation == '15m' else 60
                seconds = minutes * 60
                rows = sole_series(request('OHLC', pair=pair, interval=minutes))
                now = int(time.time())
                closed = [row for row in rows if int(row[0]) + seconds <= now]
                if len(closed) < 51:
                    raise ProbeError('LESS_THAN_51_CLOSED_CANDLES')
                for row in closed:
                    opening, high, low, close = [positive(value) for value in row[1:5]]
                    positive(row[6], allow_zero=True)
                    if high < max(opening, close) or low > min(opening, close) or high < low:
                        raise ProbeError('INVALID_OHLC')
                timestamps = [int(row[0]) for row in closed]
                if any(b - a != seconds for a, b in zip(timestamps, timestamps[1:])):
                    raise ProbeError('CANDLE_GAP')
                if now - (timestamps[-1] + seconds) > seconds:
                    raise ProbeError('STALE_LAST_CLOSED_CANDLE')
                result[operation] = {'closed_candles': len(closed), 'latest_candle_start': datetime.fromtimestamp(timestamps[-1], UTC).isoformat()}
            checks[operation] = 'PASS'
        except (ProbeError, ValueError, KeyError, TypeError, IndexError) as error:
            checks[operation] = str(error) if isinstance(error, ProbeError) else type(error).__name__
    failed = [key + ':' + value for key, value in checks.items() if value != 'PASS']
    if not failed:
        result['status'] = 'PASS'
        summary.append(display + '=PASS(15m:' + str(result['15m']['closed_candles']) + ',1h:' + str(result['1h']['closed_candles']) + ',tradeAge:' + result['trade_age_seconds'] + 's)')
    else:
        summary.append(display + '=FAIL(' + ','.join(failed) + ')')

report['passed'] = report['time'] == 'PASS' and all(pair['status'] == 'PASS' for pair in report['pairs'])
report['completed_at'] = datetime.now(UTC).isoformat()
serialized = json.dumps(report, indent=2, ensure_ascii=False)
Path(os.environ['RUNNER_TEMP'], 'kraken-public-api-test.json').write_text(serialized + '\n')
print(serialized)
with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
    output.write('summary=Kraken ' + '; '.join(summary) + '\n')
with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as output:
    output.write('Public API only. No Supabase writes or trading calls.\n\n```json\n' + serialized + '\n```\n')
