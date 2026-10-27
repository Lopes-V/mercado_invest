"""Persist immutable crypto facts using existing tables and batched reads."""
from datetime import datetime
from dataclasses import replace
from decimal import Decimal, localcontext, ROUND_HALF_UP
from uuid import UUID

from app.database.repositories import MarketQuoteRepository, MarketCandleRepository, AnalysisRepository, AnalysisMetricRepository


def database_numeric(value):
    if not isinstance(value, Decimal) or not value.is_finite() or value.copy_abs() >= Decimal('1e20'):
        raise ValueError('DECIMAL_OUT_OF_RANGE')
    with localcontext() as context:
        context.prec = 60
        result = value.quantize(Decimal('1e-18'), rounding=ROUND_HALF_UP)
    if result.copy_abs() >= Decimal('1e20'): raise ValueError('DECIMAL_OUT_OF_RANGE')
    return result


class CryptoStore:
    def __init__(self, client):
        self.client = client
        self.quotes = MarketQuoteRepository(client)
        self.candles = MarketCandleRepository(client)
        self.analyses = AnalysisRepository(client)
        self.metrics = AnalysisMetricRepository(client)

    def save_quote(self, quote):
        if database_numeric(quote.price) != quote.price: raise ValueError('QUOTE_SCALE_UNSUPPORTED')
        return self.quotes.create_from_quote(quote)

    def save_analysis(self, asset, interval, candles, analysis):
        if not candles or analysis.algorithm_version != 'analysis-v2' or analysis.asset_id != asset.id:
            raise ValueError('ANALYSIS_IDENTITY_MISMATCH')
        normalized_metrics = tuple(replace(metric, value=database_numeric(metric.value)) for metric in analysis.metrics)
        for candle in candles:
            for name in ['open', 'high', 'low', 'close', 'volume', 'adjusted_close']:
                value = getattr(candle, name)
                if value is not None and database_numeric(value) != value: raise ValueError('CANDLE_SCALE_UNSUPPORTED')
        fields = 'observed_at,provider_symbol,open::text,high::text,low::text,close::text,volume::text,adjusted_close::text'
        result = self.client.table('market_candles').select(fields).eq('asset_id', str(asset.id)).eq('provider', 'bybit').eq('interval', interval.value).gte('observed_at', candles[0].timestamp.isoformat()).lte('observed_at', candles[-1].timestamp.isoformat()).limit(1000).execute()
        if not isinstance(result.data, list): raise ValueError('INVALID_CANDLE_RESPONSE')
        existing = {datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00')): row for row in result.data}
        missing = []
        for candle in candles:
            previous = existing.get(candle.timestamp)
            if previous is None:
                missing.append(candle)
                continue
            for name in ['open', 'high', 'low', 'close', 'volume', 'adjusted_close']:
                raw = previous.get(name)
                value = Decimal(raw) if raw is not None else None
                if value != getattr(candle, name): raise ValueError('IMMUTABLE_CANDLE_CONFLICT')
            if previous['provider_symbol'] != candle.provider_symbol: raise ValueError('IMMUTABLE_CANDLE_CONFLICT')
        if missing: self.candles.create_many(tuple(missing))
        query = self.client.table('analyses').select('id').eq('asset_id', str(asset.id)).eq('interval', interval.value).eq('algorithm_version', 'analysis-v2').eq('reference_at', candles[-1].timestamp.isoformat()).limit(2).execute()
        if not isinstance(query.data, list) or len(query.data)>1: raise ValueError('AMBIGUOUS_ANALYSIS')
        analysis_id = UUID(query.data[0]['id']) if query.data else self.analyses.create(asset_id=asset.id, interval=interval.value, reference_at=candles[-1].timestamp, algorithm_version='analysis-v2').id
        previous = self.client.table('analysis_metrics').select('metric_name,metric_value::text,reference_period').eq('analysis_id', str(analysis_id)).execute()
        if not isinstance(previous.data, list): raise ValueError('INVALID_METRIC_RESPONSE')
        known = {(row['metric_name'], row['reference_period']): Decimal(row['metric_value']) for row in previous.data}
        additions = []
        for metric in normalized_metrics:
            identity = (metric.name, metric.reference_period)
            if identity in known:
                if known[identity] != metric.value: raise ValueError('IMMUTABLE_METRIC_CONFLICT')
            else: additions.append(metric)
        if additions: self.metrics.create_many(analysis_id=analysis_id, metrics=tuple(additions))
        return analysis_id
