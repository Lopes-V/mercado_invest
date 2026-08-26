from datetime import UTC, datetime
from decimal import Decimal

from app.market_data.models import DataQuality
from app.opportunity import EvidenceCategory, MetricOperator, MetricRule, OpportunityEngine, OpportunityPolicy
from app.opportunity.pipeline import OpportunityPreFilter


NOW = datetime(2026, 8, 21, tzinfo=UTC)


def _filter():
    return OpportunityPreFilter(
        OpportunityEngine(
            OpportunityPolicy(
                "candidate-v1",
                (
                    MetricRule("RETURN", MetricOperator.GT, Decimal("0.03"), Decimal("20"), EvidenceCategory.TREND.value),
                    MetricRule("VOLATILITY", MetricOperator.LT, Decimal("0.01"), Decimal("20"), EvidenceCategory.RISK.value),
                ),
            )
        )
    )


def test_prefilter_rank_is_presentation_only_and_deterministic():
    near = _filter().assess(
        symbol="AAA3", metrics={"RETURN": Decimal("0.029"), "VOLATILITY": Decimal("0.011")},
        quote_quality=DataQuality.VALID, reference_at=NOW, evaluated_at=NOW,
    )
    far = _filter().assess(
        symbol="BBB3", metrics={"RETURN": Decimal("0"), "VOLATILITY": Decimal("0.02")},
        quote_quality=DataQuality.VALID, reference_at=NOW, evaluated_at=NOW,
    )
    assert near.assessment.level.value == "NONE"
    assert near.assessment.score == Decimal("0")
    assert near.presentation_rank[2] > far.presentation_rank[2]


def test_prefilter_keeps_matched_criteria_without_recalculating_score():
    result = _filter().assess(
        symbol="AAA3", metrics={"RETURN": Decimal("0.05"), "VOLATILITY": Decimal("0.005")},
        quote_quality=DataQuality.VALID, reference_at=NOW, evaluated_at=NOW,
    )
    assert result.assessment.score == Decimal("40")
    assert result.matched_rules == ("RETURN", "VOLATILITY")
