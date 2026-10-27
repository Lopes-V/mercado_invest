"""Idempotent catalog bootstrap; existing instruments are never overwritten."""
import re

DEFAULT_SYMBOLS = ('BTCUSDT', 'ETHUSDT', 'SOLUSDT')


def validate_symbols(symbols):
    values = tuple(symbols)
    if not values or len(values) > 20 or len(set(values)) != len(values):
        raise ValueError('Selecione entre 1 e 20 pares distintos.')
    if any(not isinstance(s, str) or not re.fullmatch(r'[A-Z0-9]{2,16}USDT', s) for s in values):
        raise ValueError('Somente pares spot USDT em maiúsculas são suportados.')
    return values


class CryptoCatalog:
    def __init__(self, *, currencies, markets, exchanges, assets, mappings):
        self.currencies, self.markets, self.exchanges = currencies, markets, exchanges
        self.assets, self.mappings = assets, mappings

    @classmethod
    def from_client(cls, client):
        from app.database.repositories import CurrencyRepository, MarketRepository, ExchangeRepository, AssetRepository, ProviderSymbolRepository
        return cls(currencies=CurrencyRepository(client), markets=MarketRepository(client), exchanges=ExchangeRepository(client), assets=AssetRepository(client), mappings=ProviderSymbolRepository(client))

    def bootstrap(self, instruments, *, symbols=DEFAULT_SYMBOLS, apply=False):
        symbols = validate_symbols(symbols)
        items = {i.provider_symbol: i for i in instruments}
        for symbol in symbols:
            item = items.get(symbol)
            if item is None or (item.provider, item.currency_code, item.exchange_code, item.market_code, item.asset_type) != ('bybit', 'USDT', 'BYBIT', 'CRYPTO', 'CRYPTO'):
                raise ValueError('Instrumento spot USDT não validado pela Bybit: ' + symbol)
        actions = []
        def ensure(existing, label, create):
            if existing is not None:
                if not getattr(existing, 'is_active', True):
                    raise ValueError('Registro desativado preservado: ' + label)
                return existing
            actions.append(label)
            return create() if apply else None
        currency = ensure(self.currencies.get_by_code('USDT'), 'create currency USDT', lambda: self.currencies.create(code='USDT', name='Tether USDT', symbol='USDT', decimal_places=8))
        market = ensure(self.markets.get_by_code('CRYPTO'), 'create market CRYPTO', lambda: self.markets.create(code='CRYPTO', name='Criptoativos', default_currency_id=currency.id))
        exchange = ensure(self.exchanges.get_by_market_and_code(market.id, 'BYBIT') if market else None, 'create exchange BYBIT', lambda: self.exchanges.create(market_id=market.id, code='BYBIT', name='Bybit Spot', timezone='UTC'))
        records = []
        for symbol in symbols:
            existing = self.assets.get_by_identity(market_id=market.id, exchange_id=exchange.id, currency_id=currency.id, symbol=symbol) if market and exchange and currency else None
            if existing and existing.asset_type != 'CRYPTO':
                raise ValueError('Identidade existente não é CRYPTO: ' + symbol)
            record = ensure(existing, 'create asset ' + symbol, lambda: self.assets.create(market_id=market.id, exchange_id=exchange.id, currency_id=currency.id, symbol=symbol, name=items[symbol].name, asset_type='CRYPTO'))
            mapping = self.mappings.get_by_provider_and_symbol('bybit', symbol)
            if mapping and (record is None or mapping.asset_id != record.id or not mapping.is_active):
                raise ValueError('Mapping existente incompatível preservado: ' + symbol)
            if mapping is None:
                actions.append('create mapping ' + symbol)
                if apply: self.mappings.create(asset_id=record.id, provider='bybit', provider_symbol=symbol)
            if record: records.append(record)
        return {'applied': apply, 'actions': actions, 'assets': records}
