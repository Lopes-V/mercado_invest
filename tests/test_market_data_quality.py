from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
from uuid import UUID

import pytest

from app.market_data.errors import (
    MarketDataQualityError,
    QualityPolicyError,
)
from app.market_data.models import (
    Candle,
    CandleInterval,
    DataQuality,
    MarketSessionStatus,
    MarketStatus,
    Quote,
)
from app.market_data.quality import (
    QualityAssessment,
    QualityEngine,
    QualityIssueCode,
    QualityPolicy,
)


ASSET_ID = UUID("11111111-1111-1111-1111-111111111111")
MARKET_ID = UUID("22222222-2222-2222-2222-222222222222")
EVALUATED_AT = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def policy_kwargs(**changes):
    values = {
        "quote_max_age": timedelta(minutes=10),
        "market_status_max_age": timedelta(minutes=15),
        "candle_max_age": {
            interval: timedelta(days=1) for interval in CandleInterval
        },
        "future_tolerance": timedelta(seconds=30),
    }
    values.update(changes)
    return values


def build_policy(**changes):
    return QualityPolicy(**policy_kwargs(**changes))


def quote_kwargs(**changes):
    values = {
        "asset_id": ASSET_ID,
        "provider_symbol": "TEST.SYM",
        "price": Decimal("100"),
        "currency_code": "TST",
        "timestamp": EVALUATED_AT - timedelta(minutes=5),
        "received_at": EVALUATED_AT - timedelta(minutes=5),
        "provider": "test-provider",
        "quality": None,
    }
    values.update(changes)
    return values


def candle_kwargs(**changes):
    values = {
        "asset_id": ASSET_ID,
        "provider_symbol": "TEST.SYM",
        "timestamp": EVALUATED_AT - timedelta(minutes=5),
        "open": Decimal("100"),
        "high": Decimal("105"),
        "low": Decimal("95"),
        "close": Decimal("100"),
        "volume": Decimal("10"),
        "interval": CandleInterval.ONE_DAY,
        "provider": "test-provider",
        "received_at": EVALUATED_AT - timedelta(minutes=5),
        "quality": None,
        "adjusted_close": Decimal("100"),
    }
    values.update(changes)
    return values


def status_kwargs(**changes):
    values = {
        "market_id": MARKET_ID,
        "exchange_id": None,
        "status": MarketSessionStatus.OPEN,
        "timestamp": EVALUATED_AT - timedelta(minutes=5),
        "received_at": EVALUATED_AT - timedelta(minutes=5),
        "provider": "test-provider",
        "quality": None,
    }
    values.update(changes)
    return values


def issue_codes(assessment):
    return {issue.code for issue in assessment.issues}


def test_policy_is_valid_and_freezes_candle_max_age():
    policy = build_policy()

    assert policy.quote_max_age == timedelta(minutes=10)
    assert isinstance(policy.candle_max_age, MappingProxyType)
    with pytest.raises(TypeError):
        policy.candle_max_age[CandleInterval.ONE_DAY] = timedelta(days=2)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quote_max_age", timedelta(microseconds=-1)),
        ("market_status_max_age", timedelta(microseconds=-1)),
        ("future_tolerance", timedelta(microseconds=-1)),
    ],
)
def test_policy_rejects_negative_temporal_limits(field, value):
    with pytest.raises(QualityPolicyError, match=field):
        build_policy(**{field: value})


def test_policy_rejects_negative_candle_max_age():
    with pytest.raises(QualityPolicyError, match="candle_max_age"):
        build_policy(
            candle_max_age={CandleInterval.ONE_DAY: timedelta(microseconds=-1)}
        )


@pytest.mark.parametrize(
    "threshold",
    [
        Decimal("-0.01"),
        0.10,
        Decimal("NaN"),
        Decimal("Infinity"),
    ],
)
def test_policy_rejects_invalid_outlier_threshold(threshold):
    with pytest.raises(QualityPolicyError, match="max_relative_price_deviation"):
        build_policy(max_relative_price_deviation=threshold)


def test_candle_requires_an_explicit_interval_policy():
    engine = QualityEngine(build_policy(candle_max_age={}))

    with pytest.raises(QualityPolicyError, match="1d"):
        engine.assess_candle(Candle(**candle_kwargs()), evaluated_at=EVALUATED_AT)


def test_quote_within_age_is_valid_and_keeps_input_unassessed():
    quote = Quote(**quote_kwargs())
    assessment = QualityEngine(build_policy()).assess_quote(
        quote, evaluated_at=EVALUATED_AT
    )

    assert assessment.quality is DataQuality.VALID
    assert assessment.data.quality is DataQuality.VALID
    assert assessment.issues == ()
    assert quote.quality is None
    assert assessment.data is not quote


def test_quote_stale_only_after_strict_age_boundary():
    engine = QualityEngine(build_policy())
    boundary = Quote(
        **quote_kwargs(timestamp=EVALUATED_AT - timedelta(minutes=10))
    )
    stale = Quote(
        **quote_kwargs(timestamp=EVALUATED_AT - timedelta(minutes=10, seconds=1))
    )

    assert engine.assess_quote(
        boundary, evaluated_at=EVALUATED_AT
    ).quality is DataQuality.VALID
    assessment = engine.assess_quote(stale, evaluated_at=EVALUATED_AT)
    assert assessment.quality is DataQuality.STALE
    assert issue_codes(assessment) == {QualityIssueCode.STALE}


def test_quote_future_timestamp_is_invalid():
    quote = Quote(
        **quote_kwargs(timestamp=EVALUATED_AT + timedelta(seconds=31))
    )
    assessment = QualityEngine(build_policy()).assess_quote(
        quote, evaluated_at=EVALUATED_AT
    )

    assert assessment.quality is DataQuality.INVALID
    assert QualityIssueCode.FUTURE_TIMESTAMP in issue_codes(assessment)


def test_candle_future_received_at_is_invalid():
    candle = Candle(
        **candle_kwargs(received_at=EVALUATED_AT + timedelta(seconds=31))
    )
    assessment = QualityEngine(build_policy()).assess_candle(
        candle, evaluated_at=EVALUATED_AT
    )

    assert assessment.quality is DataQuality.INVALID
    assert QualityIssueCode.FUTURE_RECEIVED_AT in issue_codes(assessment)


def test_market_status_timestamp_after_received_at_is_invalid():
    status = MarketStatus(
        **status_kwargs(
            timestamp=EVALUATED_AT,
            received_at=EVALUATED_AT - timedelta(seconds=31),
        )
    )
    assessment = QualityEngine(build_policy()).assess_market_status(
        status, evaluated_at=EVALUATED_AT
    )

    assert assessment.quality is DataQuality.INVALID
    assert QualityIssueCode.TIMESTAMP_AFTER_RECEIVED_AT in issue_codes(
        assessment
    )


def test_quote_outlier_uses_decimal_and_strict_threshold():
    engine = QualityEngine(
        build_policy(max_relative_price_deviation=Decimal("0.10"))
    )
    outlier = Quote(**quote_kwargs(price=Decimal("120")))
    boundary = Quote(**quote_kwargs(price=Decimal("110")))

    assessment = engine.assess_quote(
        outlier,
        evaluated_at=EVALUATED_AT,
        reference_price=Decimal("100"),
    )
    assert assessment.quality is DataQuality.OUTLIER
    assert QualityIssueCode.PRICE_OUTLIER in issue_codes(assessment)
    assert engine.assess_quote(
        boundary,
        evaluated_at=EVALUATED_AT,
        reference_price=Decimal("100"),
    ).quality is DataQuality.VALID


def test_outlier_is_not_evaluated_without_explicit_reference_price():
    engine = QualityEngine(
        build_policy(max_relative_price_deviation=Decimal("0.10"))
    )
    assessment = engine.assess_quote(
        Quote(**quote_kwargs(price=Decimal("120"))),
        evaluated_at=EVALUATED_AT,
    )

    assert assessment.quality is DataQuality.VALID
    assert QualityIssueCode.PRICE_OUTLIER not in issue_codes(assessment)


@pytest.mark.parametrize(
    "reference_price",
    [0.10, Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")],
)
def test_reference_price_must_be_positive_finite_decimal(reference_price):
    with pytest.raises(MarketDataQualityError, match="reference_price"):
        QualityEngine(build_policy()).assess_quote(
            Quote(**quote_kwargs()),
            evaluated_at=EVALUATED_AT,
            reference_price=reference_price,
        )


def test_candle_completeness_follows_policy_flags():
    incomplete_candle = Candle(
        **candle_kwargs(volume=None, adjusted_close=None)
    )
    required = QualityEngine(
        build_policy(require_candle_volume=True, require_adjusted_close=True)
    ).assess_candle(incomplete_candle, evaluated_at=EVALUATED_AT)
    optional = QualityEngine(build_policy()).assess_candle(
        incomplete_candle, evaluated_at=EVALUATED_AT
    )

    assert required.quality is DataQuality.INCOMPLETE
    assert issue_codes(required) == {
        QualityIssueCode.MISSING_VOLUME,
        QualityIssueCode.MISSING_ADJUSTED_CLOSE,
    }
    assert optional.quality is DataQuality.VALID


def test_candle_staleness_uses_interval_policy():
    candle = Candle(
        **candle_kwargs(timestamp=EVALUATED_AT - timedelta(days=1, seconds=1))
    )
    assessment = QualityEngine(build_policy()).assess_candle(
        candle, evaluated_at=EVALUATED_AT
    )

    assert assessment.quality is DataQuality.STALE
    assert issue_codes(assessment) == {QualityIssueCode.STALE}


def test_market_status_unknown_follows_policy():
    status = MarketStatus(
        **status_kwargs(status=MarketSessionStatus.UNKNOWN)
    )
    incomplete = QualityEngine(build_policy()).assess_market_status(
        status, evaluated_at=EVALUATED_AT
    )
    valid = QualityEngine(
        build_policy(unknown_market_status_is_incomplete=False)
    ).assess_market_status(status, evaluated_at=EVALUATED_AT)

    assert incomplete.quality is DataQuality.INCOMPLETE
    assert QualityIssueCode.UNKNOWN_MARKET_STATUS in issue_codes(incomplete)
    assert valid.quality is DataQuality.VALID


def test_market_status_open_can_be_valid_or_stale():
    engine = QualityEngine(build_policy())
    valid = engine.assess_market_status(
        MarketStatus(**status_kwargs()), evaluated_at=EVALUATED_AT
    )
    stale = engine.assess_market_status(
        MarketStatus(
            **status_kwargs(
                timestamp=EVALUATED_AT - timedelta(minutes=15, seconds=1)
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert valid.quality is DataQuality.VALID
    assert stale.quality is DataQuality.STALE


def test_precedence_keeps_stale_and_outlier_issues():
    engine = QualityEngine(
        build_policy(max_relative_price_deviation=Decimal("0.10"))
    )
    assessment = engine.assess_quote(
        Quote(
            **quote_kwargs(
                price=Decimal("120"),
                timestamp=EVALUATED_AT - timedelta(minutes=10, seconds=1),
            )
        ),
        evaluated_at=EVALUATED_AT,
        reference_price=Decimal("100"),
    )

    assert assessment.quality is DataQuality.OUTLIER
    assert issue_codes(assessment) == {
        QualityIssueCode.STALE,
        QualityIssueCode.PRICE_OUTLIER,
    }


def test_precedence_keeps_unknown_status_and_stale_issues():
    assessment = QualityEngine(build_policy()).assess_market_status(
        MarketStatus(
            **status_kwargs(
                status=MarketSessionStatus.UNKNOWN,
                timestamp=EVALUATED_AT - timedelta(minutes=15, seconds=1),
            )
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert assessment.quality is DataQuality.INCOMPLETE
    assert issue_codes(assessment) == {
        QualityIssueCode.STALE,
        QualityIssueCode.UNKNOWN_MARKET_STATUS,
    }


def test_reassessment_recomputes_quality_without_mutating_original():
    quote = Quote(
        **quote_kwargs(
            quality=DataQuality.VALID,
            timestamp=EVALUATED_AT - timedelta(minutes=10, seconds=1),
        )
    )
    assessment = QualityEngine(build_policy()).assess_quote(
        quote, evaluated_at=EVALUATED_AT
    )

    assert assessment.quality is DataQuality.STALE
    assert assessment.data.quality is DataQuality.STALE
    assert quote.quality is DataQuality.VALID


def test_engine_rejects_naive_evaluated_at_and_normalizes_offset_datetime():
    engine = QualityEngine(build_policy())
    quote = Quote(**quote_kwargs())

    with pytest.raises(MarketDataQualityError, match="timezone"):
        engine.assess_quote(
            quote, evaluated_at=datetime(2026, 8, 18, 12, 0)
        )

    assessment = engine.assess_quote(
        quote,
        evaluated_at=datetime(
            2026,
            8,
            18,
            9,
            0,
            tzinfo=timezone(timedelta(hours=-3)),
        ),
    )
    assert assessment.evaluated_at == EVALUATED_AT


def test_engine_rejects_wrong_normalized_model_type():
    with pytest.raises(MarketDataQualityError, match="quote deve ser Quote"):
        QualityEngine(build_policy()).assess_quote(
            Candle(**candle_kwargs()), evaluated_at=EVALUATED_AT
        )


def test_assessment_requires_consistent_immutable_result():
    quote = Quote(**quote_kwargs(quality=None))

    with pytest.raises(MarketDataQualityError, match="corresponder"):
        QualityAssessment(
            data=quote,
            quality=DataQuality.VALID,
            evaluated_at=EVALUATED_AT,
            issues=(),
        )
