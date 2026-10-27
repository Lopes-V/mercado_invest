"""Deterministic analysis-v2 for a single stream of closed crypto candles.

Callers establish candle closure and freshness; this pure engine checks quality,
positive prices, stream identity and interval continuity. It never fills gaps.

RETURN is close/latest-window-start - 1 over ``period`` returns, MOMENTUM_PCT
is 100 * RETURN, VOLATILITY is their population standard deviation (unannualized),
and MAX_DRAWDOWN is the largest peak-to-trough loss ratio in those period+1
closes. EMA20/EMA50 seed with the first 20/50 closes' SMA, then apply alpha
2/(length+1) to every subsequent close. RSI seeds average gains/losses over the
first ``period`` changes, then uses Wilder smoothing (old*(period-1)+new)/period.
Flat RSI is 50; gain-only is 100 and loss-only is 0.

ATR uses the same Wilder smoothing, seeded by the first ``period`` true ranges.
TR is max(high-low, abs(high-previous_close), abs(low-previous_close)); the first
TR is high-low. ATR is in quote currency. All smoothing consumes full history.
AVERAGE_VOLUME uses previous ``period`` candles, excluding current; relative
volume divides current by that baseline. Missing inputs omit only dependent
volume metrics; a zero baseline omits the undefined ratio. Volume is base-asset
quantity. TREND_DIRECTION is 1 when close>EMA20>EMA50, -1 for close<EMA20<EMA50,
otherwise 0. Each metric records its window; results identify algorithm version.
"""

from datetime import timedelta
from decimal import Decimal, localcontext
from typing import Iterable

from app.analysis.engine import AnalysisError, AnalysisMetric, AnalysisResult
from app.market_data.models import Candle, CandleInterval, DataQuality


ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
INTERVAL_STEPS = {
    CandleInterval.FIFTEEN_MINUTES: timedelta(minutes=15),
    CandleInterval.ONE_HOUR: timedelta(hours=1),
}


class CryptoAnalysisEngine:
    """Independent v2 engine; analysis-v1 and its consumers remain unchanged."""

    algorithm_version = "analysis-v2"

    def analyze(self, candles: Iterable[Candle], *, period: int = 14) -> AnalysisResult:
        if isinstance(period, bool) or not isinstance(period, int) or not 2 <= period <= 200:
            raise AnalysisError("period deve ser inteiro entre 2 e 200")
        values = tuple(sorted(candles, key=lambda item: item.timestamp))
        minimum = max(51, period + 1)
        if len(values) < minimum:
            raise AnalysisError(f"histórico insuficiente: requer {minimum} candles")
        self._validate(values)

        # Every operation, including intermediate returns, ignores caller precision.
        with localcontext() as context:
            context.prec = max(38, context.prec)
            closes = tuple(item.close for item in values)
            window = closes[-period - 1:]
            returns = tuple(current / previous - ONE for previous, current in zip(window, window[1:]))
            total_return = window[-1] / window[0] - ONE
            ema20 = self._ema(closes, 20)
            ema50 = self._ema(closes, 50)
            direction = ONE if closes[-1] > ema20 > ema50 else (
                -ONE if closes[-1] < ema20 < ema50 else ZERO
            )
            true_ranges = (values[0].high - values[0].low,) + tuple(
                max(current.high - current.low,
                    abs(current.high - previous.close),
                    abs(current.low - previous.close))
                for previous, current in zip(values, values[1:])
            )
            metrics = [
                AnalysisMetric("CLOSE", closes[-1], 1),
                AnalysisMetric("RETURN", total_return, period),
                AnalysisMetric("MOMENTUM_PCT", HUNDRED * total_return, period),
                AnalysisMetric("EMA20", ema20, 20),
                AnalysisMetric("EMA50", ema50, 50),
                AnalysisMetric("RSI", self._rsi(closes, period), period),
                AnalysisMetric("VOLATILITY", self._stddev(returns), period),
                AnalysisMetric("ATR", self._wilder(true_ranges, period), period),
                AnalysisMetric("MAX_DRAWDOWN", self._max_drawdown(window), period),
                AnalysisMetric("TREND_DIRECTION", direction, 50),
            ]
            baseline = tuple(item.volume for item in values[-period - 1:-1])
            if all(volume is not None for volume in baseline):
                average = sum(baseline, ZERO) / Decimal(period)
                metrics.append(AnalysisMetric("AVERAGE_VOLUME", average, period))
                if average > ZERO and values[-1].volume is not None:
                    metrics.append(AnalysisMetric("RELATIVE_VOLUME", values[-1].volume / average, period))
            return AnalysisResult(values[0].asset_id, self.algorithm_version, tuple(metrics))

    @staticmethod
    def _validate(values: tuple[Candle, ...]) -> None:
        first = values[0]
        if first.interval not in INTERVAL_STEPS:
            raise AnalysisError("interval suportado: 15m ou 1h")
        identity = (first.asset_id, first.provider, first.provider_symbol, first.interval)
        previous_timestamp = None
        for candle in values:
            if (candle.asset_id, candle.provider, candle.provider_symbol, candle.interval) != identity:
                raise AnalysisError("candles devem possuir a mesma identidade e interval")
            if candle.quality is not DataQuality.VALID:
                raise AnalysisError("todos candles devem ser VALID")
            if any(price <= ZERO for price in (candle.open, candle.high, candle.low, candle.close)):
                raise AnalysisError("OHLC deve ser estritamente positivo")
            if previous_timestamp is not None and candle.timestamp - previous_timestamp != INTERVAL_STEPS[first.interval]:
                raise AnalysisError("timestamps duplicados ou lacuna no histórico")
            previous_timestamp = candle.timestamp

    @staticmethod
    def _ema(closes: tuple[Decimal, ...], length: int) -> Decimal:
        average = sum(closes[:length], ZERO) / Decimal(length)
        alpha = Decimal(2) / Decimal(length + 1)
        for close in closes[length:]:
            average += alpha * (close - average)
        return average

    @staticmethod
    def _wilder(values: tuple[Decimal, ...], period: int) -> Decimal:
        average = sum(values[:period], ZERO) / Decimal(period)
        for value in values[period:]:
            average = (average * Decimal(period - 1) + value) / Decimal(period)
        return average

    @classmethod
    def _rsi(cls, closes: tuple[Decimal, ...], period: int) -> Decimal:
        changes = tuple(current - previous for previous, current in zip(closes, closes[1:]))
        gains = cls._wilder(tuple(max(change, ZERO) for change in changes), period)
        losses = cls._wilder(tuple(max(-change, ZERO) for change in changes), period)
        if losses == ZERO:
            return HUNDRED if gains > ZERO else Decimal("50")
        return HUNDRED - HUNDRED / (ONE + gains / losses)

    @staticmethod
    def _stddev(values: tuple[Decimal, ...]) -> Decimal:
        mean = sum(values, ZERO) / Decimal(len(values))
        return (sum(((value - mean) ** 2 for value in values), ZERO) / Decimal(len(values))).sqrt()

    @staticmethod
    def _max_drawdown(closes: tuple[Decimal, ...]) -> Decimal:
        peak = closes[0]
        drawdown = ZERO
        for close in closes:
            peak = max(peak, close)
            drawdown = max(drawdown, (peak - close) / peak)
        return drawdown
