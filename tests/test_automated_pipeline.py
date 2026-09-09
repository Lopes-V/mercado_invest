from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
import pytest

from app.ai import AIAnalysisResponse, AIClassification
from app.analysis import AnalysisMetric
from app.jobs.investment_pipeline import AutomatedInvestmentPipelineJob
from app.jobs.models import JobContext, JobTrigger
from app.market_data.models import CandleInterval
from app.opportunity import EvidenceCategory, MetricOperator, MetricRule, OpportunityAssessment, OpportunityEngine, OpportunityLevel, OpportunityPolicy, OpportunityPreFilter, OpportunityService as DomainOpportunityService


NOW = datetime(2026, 8, 21, 18, 0, tzinfo=UTC)
ASSET = uuid4()
MARKET = uuid4()
ANALYSIS = uuid4()
AI_RUN = uuid4()
OPPORTUNITY = uuid4()


class Symbols:
    def list_active_by_provider(self, provider):
        assert provider == "brapi"
        return (SimpleNamespace(asset_id=ASSET),)


class Quotes:
    def __init__(self, quality="VALID"):
        self.quality = quality

    def get_latest(self, asset_id, provider):
        return SimpleNamespace(
            asset_id=asset_id,
            provider=provider,
            price=Decimal("100"),
            currency_code="BRL",
            observed_at=NOW - timedelta(minutes=1),
            quality=self.quality,
        )


class Candles:
    def __init__(self, quality="VALID"):
        self.rows = tuple(
            SimpleNamespace(
                observed_at=NOW - timedelta(days=3 - index),
                quality=quality,
            )
            for index in range(4)
        )

    def get_range(self, **_kwargs):
        return self.rows


class Assets:
    def get_by_id(self, asset_id):
        return SimpleNamespace(
            id=asset_id,
            is_active=True,
            symbol="PETR4",
            market_id=MARKET,
        )


class Markets:
    def get_by_id(self, market_id):
        assert market_id == MARKET
        return SimpleNamespace(id=MARKET, is_active=True, code="BR")


class AnalysisService:
    def __init__(self):
        self.calls = 0

    def analyze_persisted(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            result=SimpleNamespace(
                algorithm_version="analysis-v1",
                metrics=(
                    AnalysisMetric("RETURN", Decimal("0.05")),
                    AnalysisMetric("RSI", Decimal("55"), 14),
                ),
            ),
            record=SimpleNamespace(id=ANALYSIS, reference_at=NOW),
        )


class AIService:
    def __init__(self):
        self.calls = 0
        self.analysis_ids = []

    def analyze_live_persisted(self, **kwargs):
        self.calls += 1
        self.analysis_ids.append(kwargs["analysis_id"])
        return SimpleNamespace(
            response=AIAnalysisResponse(
                AIClassification.POSITIVE,
                Decimal("0.7"),
                ("trend",),
                (),
                ("volatility",),
                "bounded",
            ),
            record=SimpleNamespace(id=AI_RUN),
        )


class OpportunityService:
    def __init__(self):
        self.record_payloads = []

    def evaluate(self, **_kwargs):
        return OpportunityAssessment(
            OpportunityLevel.INTERESTING,
            Decimal("60"),
            2,
            ("RETURN", "RSI"),
        )

    def record(self, **kwargs):
        self.record_payloads.append(kwargs)
        return SimpleNamespace(id=OPPORTUNITY, evaluated_at=kwargs["evaluated_at"])


class Alerts:
    def __init__(self):
        self.calls = []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(status="SENT")


def context():
    return JobContext(
        correlation_id=uuid4(),
        trigger=JobTrigger.SCHEDULED,
        scheduled_for=NOW,
        started_at=NOW,
    )


def build_job(*, quote_quality="VALID", candle_quality="VALID"):
    candles = Candles(candle_quality)
    analysis = AnalysisService()
    ai = AIService()
    opportunity = OpportunityService()
    alerts = Alerts()
    job = AutomatedInvestmentPipelineJob(
        provider_name="brapi",
        provider_symbols=Symbols(),
        quotes=Quotes(quote_quality),
        candles=candles,
        assets=Assets(),
        markets=Markets(),
        analysis_service=analysis,
        ai_service=ai,
        opportunity_service=opportunity,
        alert_service=alerts,
        recipient_id=123,
        interval=CandleInterval.ONE_DAY,
        lookback=timedelta(days=30),
        analysis_period=14,
    )
    return job, analysis, ai, opportunity, alerts


def test_pipeline_runs_analysis_ai_opportunity_and_alert_in_order():
    job, analysis, ai, opportunity, alerts = build_job()
    result = job.execute(context())
    assert result.processed_count == 1
    assert analysis.calls == 1
    assert ai.calls == 1
    assert ai.analysis_ids == [ANALYSIS]
    assert opportunity.record_payloads[0]["analysis_id"] == ANALYSIS
    assert opportunity.record_payloads[0]["ai_run_id"] == AI_RUN
    assert len(alerts.calls) == 1
    assert alerts.calls[0]["recipient_id"] == 123
    assert alerts.calls[0]["asset"] == "PETR4"


def test_pipeline_blocks_non_valid_quote_before_ai():
    job, analysis, ai, _opportunity, alerts = build_job(quote_quality="STALE")
    result = job.execute(context())
    assert result.processed_count == 0
    assert analysis.calls == 0
    assert ai.calls == 0
    assert alerts.calls == []


def test_pipeline_blocks_non_valid_candle_before_ai():
    job, analysis, ai, _opportunity, alerts = build_job(candle_quality="INCOMPLETE")
    result = job.execute(context())
    assert result.processed_count == 0
    assert analysis.calls == 0
    assert ai.calls == 0
    assert alerts.calls == []


class PersistedOpportunities:
    def __init__(self):
        self.rows = []

    def create(self, **payload):
        row = SimpleNamespace(id=uuid4(), **payload)
        self.rows.append(row)
        return row

class RecordingOpportunityService(DomainOpportunityService):
    pass


def build_prefilter_job(policy):
    candles = Candles()
    opportunity_repository = PersistedOpportunities()
    service = RecordingOpportunityService(
        engine=OpportunityEngine(policy), repository=opportunity_repository
    )
    analysis = AnalysisService()
    ai = AIService()
    alerts = Alerts()
    job = AutomatedInvestmentPipelineJob(
        provider_name="brapi",
        provider_symbols=Symbols(), quotes=Quotes(), candles=candles,
        assets=Assets(), markets=Markets(), analysis_service=analysis,
        ai_service=ai,
        opportunity_service=service,
        alert_service=alerts, recipient_ids=(123,),
        opportunity_pre_filter=OpportunityPreFilter(service.engine),
        interval=CandleInterval.ONE_DAY, lookback=timedelta(days=30),
        analysis_period=14,
    )
    return job, ai, alerts


@pytest.mark.parametrize(
    ("level", "rules", "expected_ai"),
    [
        (OpportunityLevel.NONE, (MetricRule("RETURN", MetricOperator.GT, Decimal("1"), Decimal("40"), EvidenceCategory.TREND.value),), 0),
        (OpportunityLevel.WATCH, (MetricRule("RETURN", MetricOperator.GT, Decimal("0"), Decimal("20"), EvidenceCategory.TREND.value),), 0),
        (OpportunityLevel.INTERESTING, (MetricRule("RETURN", MetricOperator.GT, Decimal("0"), Decimal("20"), EvidenceCategory.TREND.value), MetricRule("RSI", MetricOperator.GT, Decimal("50"), Decimal("20"), EvidenceCategory.MOMENTUM.value)), 1),
        (OpportunityLevel.HIGH_INTEREST, (MetricRule("RETURN", MetricOperator.GT, Decimal("0"), Decimal("40"), EvidenceCategory.TREND.value), MetricRule("RSI", MetricOperator.GT, Decimal("50"), Decimal("40"), EvidenceCategory.MOMENTUM.value)), 1),
    ],
)
def test_prefilter_controls_gemini_and_individual_alert(level, rules, expected_ai):
    job, ai, alerts = build_prefilter_job(OpportunityPolicy("candidate-v1", rules))
    result = job.execute(context())
    assert result.processed_count == 1
    assert ai.calls == expected_ai
    assert len(alerts.calls) == (1 if level in (OpportunityLevel.INTERESTING, OpportunityLevel.HIGH_INTEREST) else 0)
