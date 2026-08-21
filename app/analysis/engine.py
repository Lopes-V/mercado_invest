"""Provider-independent technical calculations over validated candles only."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Iterable
from uuid import UUID
from datetime import datetime
from typing import Protocol

from app.market_data.models import Candle, DataQuality


ZERO = Decimal("0"); ONE = Decimal("1"); HUNDRED = Decimal("100")

class AnalysisError(ValueError): pass

@dataclass(frozen=True, slots=True)
class AnalysisMetric:
    name: str
    value: Decimal
    reference_period: int | None = None

@dataclass(frozen=True, slots=True)
class AnalysisResult:
    asset_id: UUID
    algorithm_version: str
    metrics: tuple[AnalysisMetric, ...]

class AnalysisEngine:
    """Uses simple return, population volatility, Wilder RSI, and max drawdown.

    Volatility is standard deviation of simple periodic returns and is not annualized.
    """
    def __init__(self, *, algorithm_version: str = "analysis-v1") -> None:
        if not isinstance(algorithm_version, str) or not algorithm_version.strip(): raise AnalysisError("algorithm_version não pode ser vazio")
        self.algorithm_version = algorithm_version

    def analyze(self, candles: Iterable[Candle], *, period: int = 14) -> AnalysisResult:
        values = tuple(sorted(candles, key=lambda candle: candle.timestamp))
        if not values: raise AnalysisError("análise requer candles")
        if period <= 0: raise AnalysisError("period deve ser positivo")
        asset_id = values[0].asset_id
        seen = set()
        for candle in values:
            if candle.asset_id != asset_id or candle.quality is not DataQuality.VALID: raise AnalysisError("todos candles devem ser VALID e do mesmo asset")
            if candle.timestamp in seen: raise AnalysisError("timestamps duplicados não são aceitos")
            seen.add(candle.timestamp)
        closes = tuple(item.close for item in values)
        returns = tuple((current - previous) / previous for previous, current in zip(closes, closes[1:]) if previous != ZERO)
        metrics = [AnalysisMetric("RETURN", (closes[-1] - closes[0]) / closes[0] if closes[0] else ZERO), AnalysisMetric("SMA", sum(closes[-period:]) / Decimal(min(period, len(closes))), min(period, len(closes))), AnalysisMetric("MOMENTUM", closes[-1] - closes[max(0, len(closes)-period)]), AnalysisMetric("AVERAGE_VOLUME", sum((item.volume or ZERO) for item in values[-period:]) / Decimal(min(period, len(values))), min(period, len(values))), AnalysisMetric("VOLATILITY", self._stddev(returns), min(period, len(returns))), AnalysisMetric("MAX_DRAWDOWN", self._max_drawdown(closes)), AnalysisMetric("RSI", self._rsi(closes, period), period)]
        return AnalysisResult(asset_id, self.algorithm_version, tuple(metrics))

    @staticmethod
    def _stddev(values: tuple[Decimal, ...]) -> Decimal:
        if not values: return ZERO
        mean = sum(values) / Decimal(len(values))
        with localcontext() as context:
            context.prec = 38
            return (sum((item - mean) ** 2 for item in values) / Decimal(len(values))).sqrt()

    @staticmethod
    def _max_drawdown(closes: tuple[Decimal, ...]) -> Decimal:
        peak = closes[0]; drawdown = ZERO
        for close in closes:
            peak = max(peak, close)
            if peak: drawdown = max(drawdown, (peak - close) / peak)
        return drawdown

    @staticmethod
    def _rsi(closes: tuple[Decimal, ...], period: int) -> Decimal:
        if len(closes) < 2: return Decimal("50")
        deltas = tuple(current - previous for previous, current in zip(closes, closes[1:]))
        segment = deltas[-period:]
        gains = sum((delta if delta > ZERO else ZERO) for delta in segment) / Decimal(len(segment))
        losses = sum((-delta if delta < ZERO else ZERO) for delta in segment) / Decimal(len(segment))
        if losses == ZERO: return HUNDRED if gains else Decimal("50")
        return HUNDRED - HUNDRED / (ONE + gains / losses)


class AnalysisRepository(Protocol):
    def create(self, *, asset_id: UUID, interval: str, reference_at: datetime, algorithm_version: str): ...

class AnalysisMetricRepository(Protocol):
    def create_many(self, *, analysis_id: UUID, metrics: tuple[AnalysisMetric, ...]): ...

class CandleSource(Protocol):
    def get_range(self, *, asset_id: UUID, provider: str, interval, start: datetime, end: datetime): ...

class AnalysisService:
    """Coordinates selection, deterministic calculation, and separately injected persistence."""
    def __init__(self, *, candles: CandleSource, engine: AnalysisEngine, analyses: AnalysisRepository, metrics: AnalysisMetricRepository) -> None:
        self._candles, self._engine, self._analyses, self._metrics = candles, engine, analyses, metrics

    def analyze(self, *, asset_id: UUID, provider: str, interval, start: datetime, end: datetime, period: int = 14) -> AnalysisResult:
        rows = self._candles.get_range(asset_id=asset_id, provider=provider, interval=interval, start=start, end=end)
        candles = tuple(Candle(asset_id=row.asset_id, provider_symbol=row.provider_symbol, timestamp=row.observed_at, open=row.open, high=row.high, low=row.low, close=row.close, volume=row.volume, interval=interval, provider=row.provider, received_at=row.received_at, quality=DataQuality(row.quality), adjusted_close=row.adjusted_close) for row in rows)
        result = self._engine.analyze(candles, period=period)
        record = self._analyses.create(asset_id=asset_id, interval=interval.value, reference_at=candles[-1].timestamp, algorithm_version=result.algorithm_version)
        self._metrics.create_many(analysis_id=record.id, metrics=result.metrics)
        return result
