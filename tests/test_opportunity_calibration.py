from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.backtesting.calibration import (
    CalibrationConfig,
    CalibrationObservation,
    ObservationPartitions,
    build_observation_partitions,
    calibrate_partitions,
)
from app.market_data.models import Candle, CandleInterval, DataQuality


NOW = datetime(2024, 1, 1, tzinfo=UTC)


def observation(index: int, *, positive: bool = True) -> CalibrationObservation:
    x = Decimal(index)
    return CalibrationObservation(
        asset_id=uuid4(),
        signal_at=NOW + timedelta(days=index),
        outcome_at=NOW + timedelta(days=index + 5),
        metrics=(
            ("RETURN", x / Decimal("100")),
            ("RSI", Decimal("40") + x * Decimal("5")),
        ),
        forward_return=Decimal("0.03") if positive and index >= 6 else Decimal("-0.02"),
    )


def partition(*, test_positive: bool) -> ObservationPartitions:
    train = tuple(observation(i, positive=True) for i in range(10))
    validation = tuple(
        CalibrationObservation(
            asset_id=item.asset_id,
            signal_at=item.signal_at + timedelta(days=20),
            outcome_at=item.outcome_at + timedelta(days=20),
            metrics=item.metrics,
            forward_return=item.forward_return,
        )
        for item in train
    )
    test = tuple(
        CalibrationObservation(
            asset_id=item.asset_id,
            signal_at=item.signal_at + timedelta(days=40),
            outcome_at=item.outcome_at + timedelta(days=40),
            metrics=item.metrics,
            forward_return=(
                item.forward_return
                if test_positive
                else (Decimal("-0.03") if item.forward_return > 0 else Decimal("0.01"))
            ),
        )
        for item in train
    )
    return ObservationPartitions(train, validation, test)


def test_holdout_allows_rules_only_when_unseen_test_also_passes():
    config = CalibrationConfig(min_signals=3)

    accepted = calibrate_partitions(partition(test_positive=True), config=config)
    assert accepted.selected is not None
    assert accepted.release_ready
    assert accepted.rules_json() is not None

    rejected = calibrate_partitions(partition(test_positive=False), config=config)
    assert rejected.selected is not None
    assert not rejected.release_ready
    assert rejected.rules_json() is None


def test_walk_forward_partitions_do_not_cross_future_outcomes():
    asset_id = uuid4()
    candles = tuple(
        Candle(
            asset_id=asset_id,
            provider_symbol="TEST3",
            timestamp=NOW + timedelta(days=index),
            open=Decimal("100") + index,
            high=Decimal("101") + index,
            low=Decimal("99") + index,
            close=Decimal("100") + index,
            volume=Decimal("1000"),
            interval=CandleInterval.ONE_DAY,
            provider="test",
            received_at=NOW + timedelta(days=200),
            quality=None,
        )
        for index in range(100)
    )
    config = CalibrationConfig(
        analysis_lookback_days=30,
        analysis_period=14,
        forward_horizon=5,
        min_signals=2,
    )
    parts = build_observation_partitions({asset_id: candles}, config=config)

    assert parts.train
    assert parts.validation
    assert parts.test
    assert max(item.outcome_at for item in parts.train) < min(
        item.signal_at for item in parts.validation
    )
    assert max(item.outcome_at for item in parts.validation) < min(
        item.signal_at for item in parts.test
    )


def test_historical_replay_rejects_zero_price():
    asset_id = uuid4()
    candles = (
        Candle(
            asset_id=asset_id,
            provider_symbol="ZERO3",
            timestamp=NOW,
            open=Decimal("0"),
            high=Decimal("1"),
            low=Decimal("0"),
            close=Decimal("1"),
            volume=Decimal("1"),
            interval=CandleInterval.ONE_DAY,
            provider="test",
            received_at=NOW,
            quality=DataQuality.VALID,
        ),
    )
    config = CalibrationConfig(min_signals=1)

    try:
        build_observation_partitions({asset_id: candles}, config=config)
    except ValueError as exc:
        assert "OHLC estritamente positivo" in str(exc)
    else:
        raise AssertionError("zero price deveria ser rejeitado")
