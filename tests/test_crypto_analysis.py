"""Independent numerical vectors and input contracts for analysis-v2."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from uuid import UUID

import pytest

from app.analysis.engine import AnalysisError, AnalysisResult
from app.market_data.models import Candle, CandleInterval, DataQuality


ASSET = UUID("fc89eeba-ed15-4a92-9b81-8fa141f98521")
START = datetime(2026, 1, 1, tzinfo=UTC)


def candles(closes=None, *, interval=CandleInterval.FIFTEEN_MINUTES):
    closes = closes if closes is not None else range(1, 52)
    step = timedelta(hours=1) if interval == CandleInterval.ONE_HOUR else timedelta(minutes=15)
    return [
        Candle(
            ASSET, "BTCUSDT", START + index * step,
            Decimal(str(close)), Decimal(str(close)), Decimal(str(close)),
            Decimal(str(close)), Decimal("10"), interval, "bybit",
            START + (index + 1) * step, DataQuality.VALID,
        )
        for index, close in enumerate(closes)
    ]


def analyze(values, **kwargs):
    from app.analysis.crypto import CryptoAnalysisEngine

    return CryptoAnalysisEngine().analyze(values, **kwargs)


def metrics(values, **kwargs):
    return {item.name: item.value for item in analyze(values, **kwargs).metrics}


def test_ema_sma_seed_and_update_and_versioned_result():
    result = analyze(candles())
    assert isinstance(result, AnalysisResult)
    assert result.asset_id == ASSET
    assert result.algorithm_version == "analysis-v2"
    values = {item.name: item.value for item in result.metrics}
    assert values["EMA20"] == Decimal("41.5")
    assert values["EMA50"] == Decimal("26.5")
    assert values["CLOSE"] == Decimal("51")
    assert values["RSI"] == Decimal("100")
    assert all(isinstance(value, Decimal) and value.is_finite() for value in values.values())
    periods = {item.name: item.reference_period for item in result.metrics}
    assert periods == {
        "CLOSE": 1, "RETURN": 14, "MOMENTUM_PCT": 14, "EMA20": 20,
        "EMA50": 50, "RSI": 14, "VOLATILITY": 14, "ATR": 14,
        "MAX_DRAWDOWN": 14, "AVERAGE_VOLUME": 14,
        "RELATIVE_VOLUME": 14, "TREND_DIRECTION": 50,
    }


def test_wilder_rsi_published_stockcharts_vector():
    # StockCharts RSI example (unrounded source closes). Appending flat closes
    # preserves RS while satisfying the independent EMA50 warm-up requirement.
    closes = [
        "44.34", "44.09", "44.15", "43.61", "44.33", "44.83", "45.10",
        "45.42", "45.84", "46.08", "45.89", "46.03", "45.61", "46.28",
        "46.28", "46.00", "46.03", "46.41", "46.22", "45.64", "46.21",
        "46.25", "45.71", "46.45", "45.78", "45.35", "44.03", "44.18",
        "44.22", "44.57", "43.42", "42.66", "43.13",
    ]
    actual = metrics(candles(closes + [closes[-1]] * 18))["RSI"]
    assert abs(actual - Decimal("37.7887719820578")) < Decimal("1e-12")


def test_period_return_percentage_volatility_and_drawdown_use_same_recent_window():
    # Last three returns are +0.1, -0.1, +0.1; the early 50% drawdown is outside it.
    values = candles([200, 100] + [100] * 46 + [110, 99, "108.9"])
    result = metrics(values, period=3)
    assert result["RETURN"] == Decimal("0.089")
    assert result["MOMENTUM_PCT"] == Decimal("8.9")
    assert result["MAX_DRAWDOWN"] == Decimal("0.1")
    assert abs(result["VOLATILITY"] - Decimal("0.094280904158206336586779")) < Decimal("1e-23")


def test_wilder_atr_smooths_true_ranges_and_uses_price_gaps():
    values = [replace(item, high=Decimal("102"), low=Decimal("98")) for item in candles([100] * 51)]
    values[-1] = replace(values[-1], open=Decimal("110"), high=Decimal("112"), low=Decimal("109"), close=Decimal("111"))
    # TR is 12 (112 - previous close100), not the latest intrabar range3.
    actual = metrics(values)["ATR"]
    assert abs(actual - Decimal("4.5714285714285714285714285714285714286")) < Decimal("1e-36")


def test_atr_uses_wilder_sma_seed_including_first_intrabar_range():
    values = [replace(item, high=Decimal("102"), low=Decimal("98")) for item in candles([100] * 51)]
    values[0] = replace(values[0], high=Decimal("114"), low=Decimal("86"))
    # period2: seed=(28+4)/2=16, then49 smoothing updates divide excess12 by2^49.
    actual = metrics(values, period=2)["ATR"]
    assert abs(actual - Decimal("4.0000000000000213162820728030055761337")) < Decimal("1e-36")


def test_volume_baseline_excludes_current_candle():
    values = candles()
    for index, volume in zip(range(47, 51), (10, 20, 30, 120)):
        values[index] = replace(values[index], volume=Decimal(volume))
    result = metrics(values, period=3)
    assert result["AVERAGE_VOLUME"] == Decimal("20")
    assert result["RELATIVE_VOLUME"] == Decimal("6")


@pytest.mark.parametrize("index", [36, 49])
def test_missing_baseline_volume_omits_average_and_relative_metrics(index):
    values = candles()
    values[index] = replace(values[index], volume=None)
    result = metrics(values)
    assert "AVERAGE_VOLUME" not in result
    assert "RELATIVE_VOLUME" not in result
    assert result["CLOSE"] == Decimal("51")


def test_missing_current_volume_preserves_observed_baseline():
    values = candles()
    values[-1] = replace(values[-1], volume=None)
    result = metrics(values)
    assert result["AVERAGE_VOLUME"] == Decimal("10")
    assert "RELATIVE_VOLUME" not in result


def test_missing_old_volume_does_not_invalidate_current_baseline():
    values = candles()
    values[0] = replace(values[0], volume=None)
    assert metrics(values)["RELATIVE_VOLUME"] == Decimal("1")


def test_zero_baseline_omits_undefined_relative_volume():
    values = [replace(item, volume=Decimal("0")) for item in candles()]
    values[-1] = replace(values[-1], volume=Decimal("2"))
    result = metrics(values)
    assert result["AVERAGE_VOLUME"] == Decimal("0")
    assert "RELATIVE_VOLUME" not in result


@pytest.mark.parametrize(("closes", "direction", "rsi"), [
    (list(range(1, 52)), "1", "100"),
    (list(range(51, 0, -1)), "-1", "0"),
    ([100] * 51, "0", "50"),
    (list(range(1, 51)) + [20], "0", None),
])
def test_direction_requires_price_and_both_emas_to_agree(closes, direction, rsi):
    result = metrics(candles(closes))
    assert result["TREND_DIRECTION"] == Decimal(direction)
    if rsi is not None:
        assert result["RSI"] == Decimal(rsi)


@pytest.mark.parametrize("interval", [CandleInterval.FIFTEEN_MINUTES, CandleInterval.ONE_HOUR])
def test_supported_intervals_sort_input_without_interpolation(interval):
    values = candles(interval=interval)
    assert analyze(iter(reversed(values))) == analyze(values)


@pytest.mark.parametrize("period", [True, False, 0, 1, -1, 201, 14.0, "14", None])
def test_rejects_period_outside_integer_2_to_200(period):
    with pytest.raises(AnalysisError, match="period"):
        analyze(candles(), period=period)


@pytest.mark.parametrize(("count", "period"), [(0, 14), (50, 14), (51, 51), (200, 200)])
def test_requires_both_ema_warmup_and_period_plus_one_closes(count, period):
    with pytest.raises(AnalysisError, match="history|histórico|candles"):
        analyze(candles(range(1, count + 1)), period=period)


@pytest.mark.parametrize(("count", "period"), [(51, 2), (201, 200)])
def test_accepts_minimum_history_at_period_boundaries(count, period):
    assert metrics(candles(range(1, count + 1)), period=period)["RSI"] == Decimal("100")


@pytest.mark.parametrize("change", [
    {"asset_id": UUID("cad3f299-2971-42ef-bb1a-6a4cc03b153e")},
    {"provider_symbol": "ETHUSDT"}, {"provider": "other"},
    {"interval": CandleInterval.ONE_HOUR},
])
def test_rejects_mixed_identity_and_interval(change):
    values = candles()
    values[-1] = replace(values[-1], **change)
    with pytest.raises(AnalysisError, match="same|mesmo|identity|identidade|interval"):
        analyze(values)


@pytest.mark.parametrize("quality", [None, DataQuality.STALE, DataQuality.INVALID, DataQuality.INCOMPLETE, DataQuality.OUTLIER])
def test_rejects_every_non_valid_quality(quality):
    values = candles()
    values[0] = replace(values[0], quality=quality)
    with pytest.raises(AnalysisError, match="VALID"):
        analyze(values)


@pytest.mark.parametrize("delta", [timedelta(0), timedelta(minutes=30), timedelta(minutes=14)])
def test_rejects_duplicate_gapped_or_irregular_timestamps(delta):
    values = candles()
    values[-1] = replace(values[-1], timestamp=values[-2].timestamp + delta)
    with pytest.raises(AnalysisError, match="timestamp|gap|lacuna"):
        analyze(values)


@pytest.mark.parametrize("interval", [CandleInterval.ONE_MINUTE, CandleInterval.ONE_DAY])
def test_rejects_unsupported_interval(interval):
    with pytest.raises(AnalysisError, match="interval"):
        analyze([replace(item, interval=interval) for item in candles()])


@pytest.mark.parametrize("zero", [
    {"low": Decimal("0")},
    {"low": Decimal("0"), "open": Decimal("0")},
    {"low": Decimal("0"), "close": Decimal("0")},
    dict.fromkeys(("open", "high", "low", "close"), Decimal("0")),
])
def test_rejects_zero_in_any_ohlc_field(zero):
    values = candles()
    values[-1] = replace(values[-1], **zero)
    with pytest.raises(AnalysisError, match="positive|positivo|OHLC"):
        analyze(values)


def test_decimal_calculations_do_not_inherit_low_caller_precision():
    with localcontext() as context:
        context.prec = 8
        result = metrics(candles())
    assert abs(result["RETURN"] - Decimal("0.37837837837837837837837837837837837838")) < Decimal("1e-36")
