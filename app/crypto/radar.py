"""Short-term descriptive reports, with fresh observations and explicit failure states."""
from datetime import UTC, datetime, timedelta

from app.analysis import AnalysisError
from app.market_data.contracts import HistoryRequest, QuoteRequest
from app.market_data.errors import ProviderError
from app.market_data.models import CandleInterval, DataQuality
from app.market_data.quality import QualityEngine, QualityPolicy

WINDOWS = {'15m': (CandleInterval.FIFTEEN_MINUTES, 900), '1h': (CandleInterval.ONE_HOUR, 3600)}


class CryptoRadarService:
    def __init__(self, *, provider, engine, store=None, clock=lambda: datetime.now(UTC)):
        self.provider, self.engine, self.store, self.clock = provider, engine, store, clock
        self.quality = QualityEngine(QualityPolicy(quote_max_age=timedelta(seconds=120), market_status_max_age=timedelta(seconds=120), candle_max_age={value[0]: timedelta(days=10) for value in WINDOWS.values()}, future_tolerance=timedelta(minutes=2)))

    def scan(self, assets, *, persist=False):
        if persist and self.store is None: raise ValueError('Persistência requer store explícito.')
        report = {'algorithm_version': 'analysis-v2', 'provider': self.provider.name, 'category': 'spot', 'quote_currency': 'USDT', 'evaluated_at': self.clock().isoformat(), 'costs_status': 'CUSTOS_NAO_CONFIGURADOS', 'pairs': []}
        for asset in assets:
            pair = {'symbol': asset.symbol, 'asset_id': str(asset.id), 'status': 'UNAVAILABLE', 'reasons': [], 'windows': {}}
            report['pairs'].append(pair)
            try:
                if not asset.is_active or asset.asset_type != 'CRYPTO': raise ValueError('INVALID_ASSET')
                quote = self.provider.get_quote(QuoteRequest(asset.id, asset.symbol))
                if (quote.asset_id, quote.provider_symbol, quote.provider, quote.currency_code) != (asset.id, asset.symbol, self.provider.name, 'USDT'):
                    raise ValueError('QUOTE_IDENTITY_MISMATCH')
                checked = self.quality.assess_quote(quote, evaluated_at=self.clock())
                if checked.data.quality is not DataQuality.VALID or quote.price <= 0:
                    raise ValueError('STALE_OR_INVALID_QUOTE')
                pair['quote'] = {'price': str(quote.price), 'currency': 'USDT', 'observed_at': quote.timestamp.isoformat()}
                if persist: self.store.save_quote(checked.data)
                for label, (interval, seconds) in WINDOWS.items():
                    window = {'status': 'UNAVAILABLE', 'reasons': []}
                    pair['windows'][label] = window
                    try:
                        now = self.clock()
                        end = now
                        start = datetime.fromtimestamp(int(now.timestamp()) // seconds * seconds, UTC) - timedelta(seconds=200*seconds)
                        rows = tuple(self.provider.get_history(HistoryRequest(asset.id, asset.symbol, interval, start, end)))
                        if not rows: raise ValueError('INSUFFICIENT_HISTORY')
                        # A request crossing a candle boundary can return 201 rows.
                        # Anchor the indicator seed to the latest 200 closed facts.
                        rows = tuple(sorted(rows, key=lambda row: row.timestamp)[-200:])
                        if any((row.asset_id, row.provider_symbol, row.provider, row.interval) != (asset.id, asset.symbol, self.provider.name, interval) for row in rows):
                            raise ValueError('CANDLE_IDENTITY_MISMATCH')
                        now = self.clock()
                        close_at = rows[-1].timestamp + timedelta(seconds=seconds)
                        if close_at > now or now-close_at > timedelta(seconds=seconds):
                            raise ValueError('STALE_OR_OPEN_HISTORY')
                        checked_rows = tuple(self.quality.assess_candle(row, evaluated_at=now).data for row in rows)
                        if any(row.quality is not DataQuality.VALID for row in checked_rows): raise ValueError('INVALID_HISTORY')
                        self._assert_fresh_quote(quote)
                        analysis = self.engine.analyze(checked_rows, period=14)
                        if analysis.asset_id != asset.id or analysis.algorithm_version != 'analysis-v2': raise ValueError('ANALYSIS_IDENTITY_MISMATCH')
                        self._assert_fresh_quote(quote)
                        if persist: self.store.save_analysis(asset, interval, checked_rows, analysis)
                        window.update(status='READY', reference_at=rows[-1].timestamp.isoformat(), candles=len(rows), metrics={m.name: str(m.value) for m in analysis.metrics})
                        if 'RELATIVE_VOLUME' not in window['metrics']: window['reasons'].append('VOLUME_UNAVAILABLE')
                    except (ProviderError, AnalysisError, ValueError) as exc:
                        window['reasons'].append(self._reason(exc))
                ready = sum(w['status']=='READY' for w in pair['windows'].values())
                pair['status'] = 'READY' if ready==2 else 'PARTIAL' if ready else 'UNAVAILABLE'
                directions = [w.get('metrics', {}).get('TREND_DIRECTION') for w in pair['windows'].values() if w['status']=='READY']
                pair['window_agreement'] = 'DIVERGENT' if len(set(directions)) > 1 else 'ALIGNED' if len(directions)==2 else 'UNAVAILABLE'
                try:
                    liquidity = self.provider.get_liquidity(asset.symbol)
                    if liquidity is None or self.clock()-liquidity.timestamp > timedelta(seconds=120) or liquidity.timestamp > self.clock()+timedelta(minutes=2):
                        pair['reasons'].append('LIQUIDITY_UNAVAILABLE')
                    else:
                        pair['liquidity'] = {'observed_at': liquidity.timestamp.isoformat(), 'bid': str(liquidity.bid), 'ask': str(liquidity.ask), 'spread_bps': str(liquidity.spread_bps) if liquidity.spread_bps is not None else None, 'volume24h': str(liquidity.volume24h), 'turnover24h': str(liquidity.turnover24h)}
                except ProviderError:
                    pair['reasons'].append('LIQUIDITY_UNAVAILABLE')
            except (ProviderError, AnalysisError, ValueError) as exc:
                pair['status'] = 'UNAVAILABLE'
                pair['reasons'].append(self._reason(exc))
        final_time = self.clock()
        report['evaluated_at'] = final_time.isoformat()
        for pair in report['pairs']:
            observed = pair.get('quote', {}).get('observed_at')
            if observed and final_time-datetime.fromisoformat(observed) > timedelta(seconds=120):
                pair['status'] = 'UNAVAILABLE'
                pair['window_agreement'] = 'UNAVAILABLE'
                pair['reasons'].append('STALE_OR_INVALID_QUOTE')
                for window in pair['windows'].values():
                    if window['status'] == 'READY':
                        window['status'] = 'UNAVAILABLE'
                        window['reasons'].append('STALE_OR_INVALID_QUOTE')
        return report

    def _assert_fresh_quote(self, quote):
        if self.quality.assess_quote(quote, evaluated_at=self.clock()).data.quality is not DataQuality.VALID:
            raise ValueError('STALE_OR_INVALID_QUOTE')

    @staticmethod
    def _reason(error):
        # Provider error text can contain untrusted bodies. Persist only controlled codes/classes.
        if isinstance(error, ProviderError): return type(error).__name__
        if isinstance(error, AnalysisError):
            for text, code in [('histórico insuficiente', 'INSUFFICIENT_HISTORY'), ('lacuna', 'HISTORY_GAP'), ('OHLC', 'INVALID_PRICE'), ('identidade', 'HISTORY_IDENTITY_MISMATCH')]:
                if text in str(error): return code
        text = str(error)
        return text if text and len(text)<80 and all(c.isupper() or c=='_' for c in text) else type(error).__name__
