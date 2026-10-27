"""Strict public Kraken spot observations with canonical BTC/USDT identities."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re

from app.market_data.contracts import AssetSearchRequest
from app.market_data.errors import ProviderCapabilityError, ProviderResponseError
from app.market_data.models import Candle, CandleInterval, ProviderAsset, Quote, ensure_utc_datetime

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_INTERVALS = {CandleInterval.FIFTEEN_MINUTES: 15, CandleInterval.ONE_HOUR: 60}
_DEFAULTS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')


class KrakenProvider:
    name = 'kraken'

    def __init__(self, http_client, *, clock=lambda: datetime.now(UTC)):
        self._http, self._clock = http_client, clock
        self._instruments = {}

    def _now(self):
        return ensure_utc_datetime(self._clock(), field='clock')

    @staticmethod
    def _api_symbol(symbol):
        if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9]{2,16}USDT', symbol):
            raise ProviderCapabilityError('Kraken requer símbolo spot USDT uppercase')
        return 'XBTUSDT' if symbol == 'BTCUSDT' else symbol

    def _get(self, endpoint, **params):
        payload = self._http.get_json('/0/public/' + endpoint, params=params)
        if not isinstance(payload, dict) or payload.get('error') != [] or not isinstance(payload.get('result'), dict):
            raise ProviderResponseError('Kraken recusou operação ou retornou objeto inválido')
        return payload['result']

    def _instrument(self, symbol):
        api = self._api_symbol(symbol)
        if symbol not in self._instruments:
            rows = self._get('AssetPairs', pair=api)
            if len(rows) != 1:
                raise ProviderResponseError('Kraken requer instrumento único')
            key, row = next(iter(rows.items()))
            if not isinstance(row, dict) or row.get('altname') != api or row.get('wsname') != api[:-4] + '/USDT' or row.get('quote') != 'USDT' or row.get('status') != 'online' or not isinstance(row.get('base'), str) or not row['base']:
                raise ProviderResponseError('Kraken requer instrumento correspondente online USDT')
            asset = ProviderAsset(self.name, symbol, row['wsname'], 'CRYPTO', 'USDT', 'KRAKEN', 'CRYPTO')
            self._instruments[symbol] = (key, api, asset)
        return self._instruments[symbol]

    @staticmethod
    def _series(result, key):
        if set(result) - {'last'} != {key} or not isinstance(result.get(key), list):
            raise ProviderResponseError('Mercado Kraken não corresponde ao instrumento')
        return result[key]

    @staticmethod
    def _decimal(value, *, positive=False):
        if not isinstance(value, str) or not value.strip():
            raise ProviderResponseError('Kraken requer texto decimal')
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ProviderResponseError('Decimal Kraken inválido') from exc
        if not number.is_finite() or number < 0 or (positive and number == 0):
            raise ProviderResponseError('Decimal Kraken inválido')
        return number

    @staticmethod
    def _timestamp(value, received):
        if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
            raise ProviderResponseError('Timestamp Kraken inválido')
        try:
            seconds = Decimal(value)
            if not seconds.is_finite() or seconds <= 0:
                raise ValueError('timestamp')
            timestamp = _EPOCH + timedelta(microseconds=int(seconds * 1_000_000))
        except (InvalidOperation, ValueError, OverflowError) as exc:
            raise ProviderResponseError('Timestamp Kraken inválido') from exc
        if timestamp > received + timedelta(minutes=2):
            raise ProviderResponseError('Timestamp Kraken futuro')
        return timestamp

    def get_quote(self, request):
        key, api, _ = self._instrument(request.provider_symbol)
        rows = self._series(self._get('Trades', pair=api, count=1), key)
        if not rows:
            raise ProviderResponseError('Kraken sem negócios')
        received = self._now()
        trades = []
        for row in rows:
            if not isinstance(row, list) or len(row) not in (6, 7):
                raise ProviderResponseError('Negócio Kraken malformado')
            price = self._decimal(row[0], positive=True)
            self._decimal(row[1], positive=True)
            trades.append((self._timestamp(row[2], received), price))
        timestamp, price = max(trades, key=lambda item: item[0])
        return Quote(request.asset_id, request.provider_symbol, price, 'USDT', timestamp, received, self.name, None)

    def get_history(self, request):
        if request.interval not in _INTERVALS or request.start is None or request.end is None:
            raise ProviderCapabilityError('Kraken requer range explícito e intervalo 15m/1h')
        minutes = _INTERVALS[request.interval]
        duration = timedelta(minutes=minutes)
        received = self._now()
        if received - request.start > 720 * duration:
            raise ProviderCapabilityError('Range excede retenção pública Kraken de 720 candles')
        key, api, _ = self._instrument(request.provider_symbol)
        rows = self._series(self._get('OHLC', pair=api, interval=minutes, since=int(request.start.timestamp())), key)
        received = self._now()
        facts = {}
        for row in rows:
            if not isinstance(row, list) or len(row) != 8:
                raise ProviderResponseError('Candle Kraken malformado')
            timestamp = self._timestamp(row[0], received)
            if (timestamp - _EPOCH) % duration != timedelta(0):
                raise ProviderResponseError('Candle Kraken desalinhado')
            values = tuple(self._decimal(v, positive=i < 4) for i, v in enumerate(row[1:7]))
            opening, high, low, close, _, _ = values
            if high < max(opening, close) or low > min(opening, close) or high < low or type(row[7]) is not int or row[7] < 0:
                raise ProviderResponseError('OHLC Kraken inválido')
            if timestamp in facts and facts[timestamp] != values:
                raise ProviderResponseError('Candles Kraken duplicados conflitantes')
            facts[timestamp] = values
        first_expected = _EPOCH + ((request.start - _EPOCH + duration - timedelta(microseconds=1)) // duration) * duration
        if facts and min(facts) > first_expected and first_expected + duration <= min(received, request.end):
            raise ProviderResponseError('Histórico Kraken truncado')
        return tuple(Candle(request.asset_id, request.provider_symbol, at, values[0], values[1], values[2], values[3], values[5], request.interval, self.name, received, None)
                     for at, values in sorted(facts.items()) if request.start <= at <= request.end and at + duration <= received)

    def get_assets(self, request):
        if request.market_code not in (None, 'CRYPTO') or request.exchange_code not in (None, 'KRAKEN'):
            raise ProviderCapabilityError('Kraken suporta somente CRYPTO/KRAKEN spot')
        symbols = (request.query,) if request.query else _DEFAULTS
        return tuple(self._instrument(symbol)[2] for symbol in symbols)

    def get_market_status(self, request):
        raise ProviderCapabilityError('Market status Kraken não implementado')

    def get_liquidity(self, symbol):
        raise ProviderCapabilityError('Snapshot de liquidez Kraken indisponível nesta versão')
