from datetime import UTC, datetime, timedelta
from decimal import Decimal
from app.alerts import AlertEngine,AlertPolicy
from app.backtesting import BacktestConfig,BacktestEngine
from app.market_data.models import DataQuality
from app.opportunity import EvidenceCategory,MetricOperator,MetricRule,OpportunityEngine,OpportunityLevel,OpportunityPolicy
NOW=datetime(2026,1,1,tzinfo=UTC)
def test_opportunity_requires_multiple_categories_and_alert_cooldown():
    policy=OpportunityPolicy("v1",(MetricRule("return",MetricOperator.GT,Decimal("0"),Decimal("80"),EvidenceCategory.TREND.value),MetricRule("volume",MetricOperator.GT,Decimal("0"),Decimal("20"),EvidenceCategory.VOLUME.value)))
    engine=OpportunityEngine(policy)
    assert engine.assess(metrics={"return":Decimal("1")},price_quality=DataQuality.VALID,reference_at=NOW,evaluated_at=NOW).level is OpportunityLevel.WATCH
    result=engine.assess(metrics={"return":Decimal("1"),"volume":Decimal("1")},price_quality=DataQuality.VALID,reference_at=NOW,evaluated_at=NOW)
    assert result.level is OpportunityLevel.HIGH_INTEREST
    assert not AlertEngine(AlertPolicy()).decide(level=result.level,quality=DataQuality.VALID,last_sent_at=NOW,decided_at=NOW,recipient_authorized=True).send


def test_opportunity_financial_result_is_independent_of_gemini_context():
    policy = OpportunityPolicy(
        "v1",
        (
            MetricRule("return", MetricOperator.GT, Decimal("0"), Decimal("40"), EvidenceCategory.TREND.value),
            MetricRule("volume", MetricOperator.GT, Decimal("0"), Decimal("20"), EvidenceCategory.VOLUME.value),
        ),
    )
    engine = OpportunityEngine(policy)
    kwargs = dict(
        metrics={"return": Decimal("1"), "volume": Decimal("0")},
        price_quality=DataQuality.VALID,
        reference_at=NOW,
        evaluated_at=NOW,
    )
    without_context = engine.assess(**kwargs)
    with_context = engine.assess(**kwargs)
    assert with_context == without_context
