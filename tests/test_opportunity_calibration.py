from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.backtesting.calibration import (
    CalibrationConfig,
    CalibrationObservation,
    ObservationPartitions,
    build_observation_partitions,
    calibrate_partitions,
)
from app.calibrate_opportunity import (
    CalibrationHistoryError,
    format_history_failure,
    history_window_candidates,
    load_brapi_history_with_fallback,
    partition_report,
)
from app.market_data.errors import ProviderHttpError
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
    assert rejected.selected.rules == accepted.selected.rules
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


def _candles(
    asset_id,
    *,
    count: int,
    start: datetime = NOW,
) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            asset_id=asset_id,
            provider_symbol="TEST3",
            timestamp=start + timedelta(days=index),
            open=Decimal("100") + Decimal(index),
            high=Decimal("101") + Decimal(index),
            low=Decimal("99") + Decimal(index),
            close=Decimal("100") + Decimal(index),
            volume=Decimal("1000"),
            interval=CandleInterval.ONE_DAY,
            provider="brapi",
            received_at=NOW,
            quality=None,
        )
        for index in range(count)
    )


def test_history_window_candidates_descend_without_weakening_requested_window():
    assert history_window_candidates(730) == (730, 365, 180, 90, 30)
    assert history_window_candidates(90) == (90, 30)


@pytest.mark.parametrize("limit_code", ["INVALID_RANGE", "DATE_WINDOW_EXCEEDED"])
def test_history_fallback_only_handles_explicit_brapi_window_limit(limit_code: str):
    asset_id = uuid4()

    class Provider:
        def __init__(self):
            self.windows: list[int] = []

        def get_history(self, request):
            window = (request.end - request.start).days
            self.windows.append(window)
            if window > 90:
                raise ProviderHttpError(
                    "generic HTTP failure",
                    status_code=400,
                    provider_code=limit_code,
                )
            return _candles(asset_id, count=80)

    provider = Provider()
    loaded = load_brapi_history_with_fallback(
        provider,
        asset_id=asset_id,
        provider_symbol="BBDC4",
        end=NOW + timedelta(days=730),
        history_days=730,
    )

    assert provider.windows == [730, 365, 180, 90]
    assert loaded.requested_days == 730
    assert loaded.loaded_window_days == 90
    assert loaded.fallback_code == limit_code
    assert len(loaded.candles) == 80


@pytest.mark.parametrize(
    ("status_code", "provider_code"),
    [
        (400, "BAD_REQUEST"),
        (401, "UNAUTHORIZED"),
        (403, "FORBIDDEN"),
        (429, "RATE_LIMIT_EXCEEDED"),
    ],
)
def test_history_fallback_never_masks_non_window_http_failures(
    status_code: int, provider_code: str
):
    asset_id = uuid4()

    class Provider:
        def __init__(self):
            self.windows: list[int] = []

        def get_history(self, request):
            self.windows.append((request.end - request.start).days)
            raise ProviderHttpError(
                "generic HTTP failure",
                status_code=status_code,
                provider_code=provider_code,
            )

    provider = Provider()

    with pytest.raises(ProviderHttpError) as raised:
        load_brapi_history_with_fallback(
            provider,
            asset_id=asset_id,
            provider_symbol="BBDC4",
            end=NOW + timedelta(days=730),
            history_days=730,
        )

    assert raised.value.status_code == status_code
    assert raised.value.provider_code == provider_code
    assert provider.windows == [730]


@pytest.mark.parametrize(
    ("status_code", "provider_code"),
    [
        (400, "BAD_REQUEST"),
        (401, "UNAUTHORIZED"),
        (403, "FORBIDDEN"),
        (429, "RATE_LIMIT_EXCEEDED"),
    ],
)
def test_history_failures_are_diagnostic_and_never_leak_tokens(
    status_code: int, provider_code: str
):
    error = ProviderHttpError(
        "Bearer token-that-must-not-appear",
        status_code=status_code,
        provider_code=provider_code,
    )
    diagnostic = format_history_failure("BBDC4", error)

    assert diagnostic == (
        f"SKIP BBDC4: status={status_code} type=ProviderHttpError "
        f"code={provider_code}"
    )
    assert "token-that-must-not-appear" not in diagnostic


def test_empty_history_is_rejected_instead_of_becoming_a_fake_sample():
    class Provider:
        def get_history(self, request):
            return ()

    with pytest.raises(CalibrationHistoryError, match="EMPTY_HISTORY"):
        load_brapi_history_with_fallback(
            Provider(),
            asset_id=uuid4(),
            provider_symbol="BBDC4",
            end=NOW,
            history_days=90,
        )


def test_global_partitions_prevent_cross_asset_temporal_overlap():
    long_asset_id = uuid4()
    short_asset_id = uuid4()
    config = CalibrationConfig(
        analysis_lookback_days=30,
        analysis_period=14,
        forward_horizon=5,
        min_signals=8,
    )
    parts = build_observation_partitions(
        {
            long_asset_id: _candles(long_asset_id, count=200),
            short_asset_id: _candles(
                short_asset_id,
                count=50,
                start=NOW + timedelta(days=150),
            ),
        },
        config=config,
    )

    assert parts.global_train_end is not None
    assert parts.global_validation_end is not None
    assert parts.train and parts.validation and parts.test
    assert all(
        item.signal_at <= parts.global_train_end
        and item.outcome_at <= parts.global_train_end
        for item in parts.train
    )
    assert all(
        parts.global_train_end < item.signal_at <= parts.global_validation_end
        and item.outcome_at <= parts.global_validation_end
        for item in parts.validation
    )
    assert all(item.signal_at > parts.global_validation_end for item in parts.test)
    assert max(item.outcome_at for item in parts.train) < min(
        item.signal_at for item in parts.validation
    )
    assert max(item.outcome_at for item in parts.validation) < min(
        item.signal_at for item in parts.test
    )

    assert short_asset_id not in {item.asset_id for item in parts.train}
    assert short_asset_id not in {item.asset_id for item in parts.validation}
    assert short_asset_id in {item.asset_id for item in parts.test}


def test_partition_report_exposes_global_boundaries_and_asset_contributions():
    long_asset_id = uuid4()
    short_asset_id = uuid4()
    parts = build_observation_partitions(
        {
            long_asset_id: _candles(long_asset_id, count=200),
            short_asset_id: _candles(
                short_asset_id,
                count=50,
                start=NOW + timedelta(days=150),
            ),
        },
        config=CalibrationConfig(min_signals=8),
    )

    report = partition_report(
        parts,
        symbols_by_asset={long_asset_id: "LONG3", short_asset_id: "SHORT3"},
    )

    assert report["global_train_end"] is not None
    assert report["global_validation_end"] is not None
    assert report["train"]["contributing_assets"] == 1
    assert report["test"]["observations_by_asset"]["SHORT3"] > 0


def test_holdout_remains_rejected_when_only_three_signals_are_available():
    config = CalibrationConfig(min_signals=8)
    train = tuple(observation(index, positive=True) for index in range(30))
    validation = tuple(
        CalibrationObservation(
            asset_id=item.asset_id,
            signal_at=item.signal_at + timedelta(days=40),
            outcome_at=item.outcome_at + timedelta(days=40),
            metrics=item.metrics,
            forward_return=item.forward_return,
        )
        for item in train
    )
    original_test = tuple(
        CalibrationObservation(
            asset_id=item.asset_id,
            signal_at=item.signal_at + timedelta(days=80),
            outcome_at=item.outcome_at + timedelta(days=80),
            metrics=item.metrics,
            forward_return=item.forward_return,
        )
        for item in train
    )
    reduced_holdout = ObservationPartitions(
        train=train,
        validation=validation,
        test=original_test[-3:],
    )

    result = calibrate_partitions(reduced_holdout, config=config)

    assert result.test is not None
    assert result.test.signals == 3
    assert not result.release_ready
    assert result.rules_json() is None
