from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.ai import AIAnalysisResponse, AIClassification
from app.analysis import AnalysisMetric
from app.jobs.investment_pipeline import AutomatedInvestmentPipelineJob
from app.jobs.models import JobContext, JobTrigger
from app.market_data.models import CandleInterval
from app.opportunity import OpportunityAssessment, OpportunityLevel


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

    def analyze(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            algorithm_version="analysis-v1",
            metrics=(
                AnalysisMetric("RETURN", Decimal("0.05")),
                AnalysisMetric("RSI", Decimal("55"), 14),
            ),
        )


class Analyses:
    def __init__(self, candles):
        self.candles = candles

    def get_latest_for_asset(self, _asset_id, _interval):
        return SimpleNamespace(id=ANALYSIS, reference_at=self.candles.rows[-1].observed_at)


class AIService:
    def __init__(self):
        self.calls = 0

    def analyze_live(self, **_kwargs):
        self.calls += 1
        return AIAnalysisResponse(
            AIClassification.POSITIVE,
            Decimal("0.7"),
            ("trend",),
            (),
            ("volatility",),
            "bounded",
        )


class AIRuns:
    def get_latest_for_asset(self, _asset_id):
        return SimpleNamespace(id=AI_RUN)


class OpportunityService:
    def assess(self, **_kwargs):
        return OpportunityAssessment(
            OpportunityLevel.INTERESTING,
            Decimal("60"),
            2,
            ("RETURN", "RSI"),
        )


class Opportunities:
    def get_latest_for_asset(self, _asset_id):
        return SimpleNamespace(id=OPPORTUNITY, evaluated_at=NOW)


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
    alerts = Alerts()
    job = AutomatedInvestmentPipelineJob(
        provider_name="brapi",
        provider_symbols=Symbols(),
        quotes=Quotes(quote_quality),
        candles=candles,
        assets=Assets(),
        markets=Markets(),
        analysis_service=analysis,
        analyses=Analyses(candles),
        ai_service=ai,
        ai_runs=AIRuns(),
        opportunity_service=OpportunityService(),
        opportunities=Opportunities(),
        alert_service=alerts,
        recipient_id=123,
        interval=CandleInterval.ONE_DAY,
        lookback=timedelta(days=30),
        analysis_period=14,
    )
    return job, analysis, ai, alerts


def test_pipeline_runs_analysis_ai_opportunity_and_alert_in_order():
    job, analysis, ai, alerts = build_job()
    result = job.execute(context())
    assert result.processed_count == 1
    assert analysis.calls == 1
    assert ai.calls == 1
    assert len(alerts.calls) == 1
    assert alerts.calls[0]["recipient_id"] == 123
    assert alerts.calls[0]["asset"] == "PETR4"


def test_pipeline_blocks_non_valid_quote_before_ai():
    job, analysis, ai, alerts = build_job(quote_quality="STALE")
    result = job.execute(context())
    assert result.processed_count == 0
    assert analysis.calls == 0
    assert ai.calls == 0
    assert alerts.calls == []


def test_pipeline_blocks_non_valid_candle_before_ai():
    job, analysis, ai, alerts = build_job(candle_quality="INCOMPLETE")
    result = job.execute(context())
    assert result.processed_count == 0
    assert analysis.calls == 0
    assert ai.calls == 0
    assert alerts.calls == []
