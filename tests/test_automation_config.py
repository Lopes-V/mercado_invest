import json
from decimal import Decimal

import pytest

from app.automation_config import build_opportunity_policy, build_quality_policy, validate_automation_settings
from app.config.settings import Environment, LogLevel, Settings
from app.market_data.models import CandleInterval
from app.opportunity import EvidenceCategory, MetricOperator


def settings(**overrides):
    values = dict(
        environment=Environment.TEST,
        log_level=LogLevel.INFO,
        supabase_url="https://example.supabase.co",
        supabase_secret_key="secret",
        telegram_bot_token="telegram",
        telegram_allowed_user_ids=frozenset({123}),
        gemini_api_key="gemini",
        gemini_model="gemini-test",
        twelve_data_api_key="twelve",
        automated_pipeline_enabled=True,
        opportunity_policy_version="test-v1",
        opportunity_rules_json=json.dumps(
            [
                {
                    "metric_name": "RETURN",
                    "operator": "GT",
                    "threshold": "0",
                    "weight": "40",
                    "evidence_category": "TREND",
                }
            ]
        ),
    )
    values.update(overrides)
    return Settings(**values)


def test_build_opportunity_policy_from_explicit_json():
    policy = build_opportunity_policy(settings())
    assert policy.version == "test-v1"
    assert policy.minimum_categories == 2
    assert policy.max_ai_weight == Decimal("20")
    assert len(policy.rules) == 1
    assert policy.rules[0].operator is MetricOperator.GT
    assert policy.rules[0].evidence_category == EvidenceCategory.TREND.value
    assert policy.rules[0].threshold == Decimal("0")
    assert policy.rules[0].weight == Decimal("40")


def test_automation_requires_explicit_rules_and_single_recipient():
    with pytest.raises(ValueError, match="OPPORTUNITY_RULES_JSON"):
        validate_automation_settings(settings(opportunity_rules_json=None))
    with pytest.raises(ValueError, match="exatamente um"):
        validate_automation_settings(
            settings(telegram_allowed_user_ids=frozenset({1, 2}))
        )


def test_quality_policy_covers_collection_and_pipeline_intervals():
    policy = build_quality_policy(
        settings(
            market_history_candle_interval="1d",
            automated_pipeline_candle_interval="1h",
        )
    )
    assert CandleInterval.ONE_DAY in policy.candle_max_age
    assert CandleInterval.ONE_HOUR in policy.candle_max_age
