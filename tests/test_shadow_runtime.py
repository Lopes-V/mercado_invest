from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.analysis import AnalysisMetric, AnalysisResult
from app.bootstrap import build_application
from app.config.settings import Environment, LogLevel, Settings
from app.database.repositories.policy_lifecycle import FrozenOpportunityPolicyRecord
from app.database.repositories.market_data import MarketCandleRepository
from app.jobs.models import JobContext, JobTrigger
from app.jobs.shadow import ShadowOpportunityPipelineJob
from app.market_data.models import Candle, CandleInterval, DataQuality
from app.shadow import ShadowService
from app.shadow_policy import FrozenPolicyError, load_frozen_opportunity_policy


NOW = datetime(2026, 8, 21, tzinfo=UTC)
ASSET_ID = uuid4()
POLICY_ID = uuid4()


def frozen_record(*, status: str = "FROZEN", approved: bool = True, rules=None):
    return FrozenOpportunityPolicyRecord(
        id=POLICY_ID,
        policy_version="candidate-v1",
        created_at=NOW,
        calibration_release_ready=approved,
        status=status,
        metric_rules=tuple(
            rules
            if rules is not None
            else (
                {
                    "metric_name": "RETURN",
                    "operator": "GT",
                    "threshold": "0",
                    "weight": "40",
                    "evidence_category": "TREND",
                },
                {
                    "metric_name": "VOLATILITY",
                    "operator": "LT",
                    "threshold": "1",
                    "weight": "40",
                    "evidence_category": "RISK",
                },
            )
        ),
    )


def test_frozen_loader_uses_persisted_rules_and_fails_closed():
    policy = load_frozen_opportunity_policy(
        frozen_record(), max_age=timedelta(days=2)
    )
    assert policy.version == "candidate-v1"
    assert policy.rules[0].threshold == Decimal("0")
    assert policy.rules[1].evidence_category == "RISK"
    assert (
        load_frozen_opportunity_policy(
            frozen_record(),
            max_age=timedelta(days=2),
            max_ai_weight=Decimal("20"),
        ).max_ai_weight
        == Decimal("20")
    )
    with pytest.raises(FrozenPolicyError, match="FROZEN"):
        load_frozen_opportunity_policy(
            frozen_record(status="RETIRED"), max_age=timedelta(days=2)
        )
    with pytest.raises(FrozenPolicyError, match="calibration_release_ready"):
        load_frozen_opportunity_policy(
            frozen_record(approved=False), max_age=timedelta(days=2)
        )
    with pytest.raises(FrozenPolicyError, match="operator"):
        load_frozen_opportunity_policy(
            frozen_record(
                rules=(
                    {
                        "metric_name": "RETURN",
                        "operator": "INVALID",
                        "threshold": "0",
                        "weight": "40",
                        "evidence_category": "TREND",
                    },
                )
            ),
            max_age=timedelta(days=2),
        )


class _Predictions:
    def __init__(self) -> None:
        self.rows = []

    def get_by_prediction_key(self, key):
        return next((row for row in self.rows if row.prediction_key == key), None)

    def create(self, **payload):
        row = SimpleNamespace(id=uuid4(), realized_at=None, **payload)
        self.rows.append(row)
        return row

    def list_pending_due(self, *, before):
        return ()

    def record_outcome(self, **_payload):
        raise AssertionError("não há settlement neste teste")


class _Policies:
    def __init__(self, record):
        self.record = record
        self.calls = []

    def get_by_version(self, version):
        self.calls.append(version)
        return self.record


class _Symbols:
    def list_active_by_provider(self, provider):
        assert provider == "brapi"
        return (SimpleNamespace(asset_id=ASSET_ID),)


class _Candles:
    def __init__(self, quality="VALID", observed_at=NOW):
        self.quality = quality
        self.observed_at = observed_at

    def get_range(self, **_kwargs):
        return (
            SimpleNamespace(
                asset_id=ASSET_ID,
                provider="brapi",
                provider_symbol="TEST3",
                observed_at=self.observed_at,
                received_at=self.observed_at,
                open=Decimal("99"),
                high=Decimal("101"),
                low=Decimal("98"),
                close=Decimal("100"),
                volume=Decimal("10"),
                adjusted_close=None,
                quality=self.quality,
            ),
        )


class _Analysis:
    def __init__(self):
        self.calls = 0

    def analyze(self, **_kwargs):
        self.calls += 1
        return AnalysisResult(
            ASSET_ID,
            "analysis-v1",
            (
                AnalysisMetric("RETURN", Decimal("0.1")),
                AnalysisMetric("VOLATILITY", Decimal("0.1")),
            ),
        )


def _shadow_job(*, record=None, quality="VALID"):
    predictions = _Predictions()
    analysis = _Analysis()
    candles = _Candles(quality)
    job = ShadowOpportunityPipelineJob(
        provider_name="brapi",
        policy_version="candidate-v1",
        frozen_policies=_Policies(record or frozen_record()),
        provider_symbols=_Symbols(),
        candles=candles,
        analysis_service=analysis,
        shadow_service=ShadowService(repository=predictions),
        interval=CandleInterval.ONE_DAY,
        lookback=timedelta(days=30),
        analysis_period=14,
        forward_horizon_days=5,
        round_trip_cost_bps=Decimal("20"),
    )
    return job, predictions, analysis, candles


def test_shadow_job_deduplicates_three_scheduler_slots_for_one_candle_and_accepts_a_new_candle():
    job, predictions, analysis, candles = _shadow_job()
    ten = NOW + timedelta(hours=10)
    ten_thirty = NOW + timedelta(hours=10, minutes=30)
    eleven = NOW + timedelta(hours=11)
    for scheduled_for in (ten, ten_thirty, eleven):
        assert job.execute(JobContext(uuid4(), JobTrigger.SCHEDULED, scheduled_for, scheduled_for)).processed_count == 1
    assert len(predictions.rows) == 1
    assert analysis.calls == 3
    prediction = predictions.rows[0]
    assert prediction.policy_id == POLICY_ID
    assert prediction.outcome_due_at == NOW + timedelta(days=5)
    assert prediction.reference_at == NOW
    assert prediction.predicted_at == ten
    assert prediction.quality == "VALID"

    candles.observed_at = NOW + timedelta(days=1)
    next_day = NOW + timedelta(days=1, hours=10)
    assert job.execute(JobContext(uuid4(), JobTrigger.SCHEDULED, next_day, next_day)).processed_count == 1
    assert len(predictions.rows) == 2
    assert predictions.rows[1].reference_at == NOW + timedelta(days=1)
    assert predictions.rows[1].outcome_due_at == NOW + timedelta(days=6)


def test_shadow_job_blocks_invalid_quality_and_ineligible_frozen_policy():
    job, predictions, analysis, _candles = _shadow_job(quality="STALE")
    assert job.execute(JobContext(uuid4(), JobTrigger.SCHEDULED, NOW, NOW)).processed_count == 0
    assert not predictions.rows and analysis.calls == 0
    job, _predictions, _analysis, _candles = _shadow_job(record=frozen_record(status="RETIRED"))
    with pytest.raises(FrozenPolicyError):
        job.execute(JobContext(uuid4(), JobTrigger.SCHEDULED, NOW, NOW))


def _settings(**overrides):
    values = dict(
        environment=Environment.TEST,
        log_level=LogLevel.INFO,
        supabase_url="https://example.supabase.co",
        supabase_secret_key="secret",
        telegram_bot_token=None,
        telegram_allowed_user_ids=frozenset(),
        market_quotes_enabled=False,
        market_history_enabled=False,
        automated_pipeline_enabled=False,
        automation_enabled=False,
        production_ready=False,
        shadow_mode_enabled=True,
        shadow_policy_version="candidate-v1",
    )
    values.update(overrides)
    return Settings(**values)


def test_shadow_bootstrap_builds_jobs_without_gemini_or_telegram(monkeypatch):
    import app.bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "create_supabase_client", lambda _settings: object())

    class Forbidden:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("shadow não deve instanciar integração de produção")

    monkeypatch.setattr(bootstrap, "GeminiProvider", Forbidden)
    monkeypatch.setattr(bootstrap, "TelegramClient", Forbidden)
    application = build_application(_settings())
    try:
        names = tuple(item.job.name for item in application.scheduler._jobs)
        assert "shadow_opportunity:brapi:1d" in names
        assert "shadow_settlement" in names
        assert not any(name.startswith("automated_investment") for name in names)
    finally:
        application.close()


def test_production_job_is_not_built_without_both_execution_gates(monkeypatch):
    import app.bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "create_supabase_client", lambda _settings: object())

    class Forbidden:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("pipeline de produção não deve ser construído")

    monkeypatch.setattr(bootstrap, "GeminiProvider", Forbidden)
    monkeypatch.setattr(bootstrap, "TelegramClient", Forbidden)
    application = build_application(
        _settings(shadow_mode_enabled=False, automated_pipeline_enabled=True)
    )
    try:
        assert not application.scheduler._jobs
    finally:
        application.close()


def test_production_requires_matching_approved_frozen_policy(monkeypatch):
    import app.bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "create_supabase_client", lambda _settings: object())
    monkeypatch.setattr(
        bootstrap,
        "FrozenOpportunityPolicyRepository",
        lambda _client: SimpleNamespace(get_by_version=lambda _version: None),
    )
    rules = json.dumps(
        [
            {
                "metric_name": "RETURN",
                "operator": "GT",
                "threshold": "0",
                "weight": "40",
                "evidence_category": "TREND",
            }
        ]
    )
    with pytest.raises(ValueError, match="policy congelada"):
        build_application(
            _settings(
                shadow_mode_enabled=False,
                automated_pipeline_enabled=True,
                automation_enabled=True,
                production_ready=True,
                telegram_bot_token="telegram",
                telegram_allowed_user_ids=frozenset({1}),
                gemini_api_key="gemini",
                gemini_model="gemini-model",
                automated_pipeline_providers=("brapi",),
                opportunity_policy_version="candidate-v1",
                opportunity_rules_json=rules,
            )
        )


def test_realized_price_repository_queries_only_valid_candles_at_or_after_due():
    class Query:
        def __init__(self):
            self.filters = []

        def select(self, _fields):
            return self

        def eq(self, field, value):
            self.filters.append(("eq", field, value))
            return self

        def gte(self, field, value):
            self.filters.append(("gte", field, value))
            return self

        def order(self, field, desc=False):
            self.filters.append(("order", field, desc))
            return self

        def limit(self, value):
            self.filters.append(("limit", value))
            return self

        def execute(self):
            return SimpleNamespace(
                data=[
                    {
                        "id": str(uuid4()),
                        "asset_id": str(ASSET_ID),
                        "provider": "brapi",
                        "provider_symbol": "TEST3",
                        "interval": "1d",
                        "observed_at": (NOW + timedelta(days=5)).isoformat(),
                        "open": "100",
                        "high": "101",
                        "low": "99",
                        "close": "100",
                        "volume": "1",
                        "adjusted_close": None,
                        "received_at": NOW.isoformat(),
                        "quality": "VALID",
                        "created_at": NOW.isoformat(),
                    }
                ]
            )

    query = Query()
    repository = MarketCandleRepository(SimpleNamespace(table=lambda _name: query))
    result = repository.first_price_at_or_after(
        asset_id=ASSET_ID,
        provider="brapi",
        interval="1d",
        at_or_after=NOW + timedelta(days=5),
    )
    assert result is not None and result.quality == "VALID"
    assert ("eq", "quality", "VALID") in query.filters
    assert ("gte", "observed_at", (NOW + timedelta(days=5)).isoformat()) in query.filters
    assert ("order", "observed_at", False) in query.filters
    assert ("limit", 1) in query.filters


def test_overlapping_history_is_explicitly_idempotent_without_upsert(monkeypatch):
    candle = Candle(
        asset_id=ASSET_ID,
        provider_symbol="TEST3",
        timestamp=NOW,
        open=Decimal("99"),
        high=Decimal("101"),
        low=Decimal("98"),
        close=Decimal("100"),
        volume=Decimal("10"),
        interval=CandleInterval.ONE_DAY,
        provider="brapi",
        received_at=NOW,
        quality=DataQuality.VALID,
    )
    existing = SimpleNamespace(
        asset_id=ASSET_ID,
        provider="brapi",
        interval="1d",
        observed_at=NOW,
    )
    repository = MarketCandleRepository(object())
    monkeypatch.setattr(repository, "get_by_identity", lambda **_kwargs: existing)
    monkeypatch.setattr(
        repository,
        "create_many",
        lambda _candles: (_ for _ in ()).throw(AssertionError("não deve inserir")),
    )
    assert repository.create_many_idempotent((candle,)) == (existing,)
