"""Validated configuration builders for the automated investment pipeline."""

import json
from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app.config.settings import Settings
from app.market_data.models import CandleInterval
from app.market_data.quality import QualityPolicy
from app.opportunity import (
    EvidenceCategory,
    MetricOperator,
    MetricRule,
    OpportunityPolicy,
)


def _interval(value: str, *, field: str) -> CandleInterval:
    try:
        return CandleInterval(value)
    except ValueError as exc:
        raise ValueError(f"{field} inválido: {value}") from exc


def build_quality_policy(settings: Settings) -> QualityPolicy:
    """Build a conservative quality policy from operational schedule settings.

    The candle age window is derived from the longest configured lookback so
    historical candles collected for analysis are not automatically labelled
    stale simply because they are older than the latest quote.
    """

    market_interval = _interval(
        settings.market_history_candle_interval,
        field="MARKET_HISTORY_CANDLE_INTERVAL",
    )
    pipeline_interval = _interval(
        settings.automated_pipeline_candle_interval,
        field="AUTOMATED_PIPELINE_CANDLE_INTERVAL",
    )
    shadow_interval = _interval(
        settings.shadow_candle_interval,
        field="SHADOW_CANDLE_INTERVAL",
    )
    max_lookback_days = max(
        settings.market_history_lookback_days,
        settings.automated_pipeline_lookback_days,
        settings.shadow_lookback_days,
    )
    candle_age = timedelta(days=max_lookback_days + 2)
    candle_max_age = {
        market_interval: candle_age,
        pipeline_interval: candle_age,
        shadow_interval: candle_age,
    }
    quote_age = timedelta(
        seconds=max(600, settings.market_quotes_interval_seconds * 2)
    )
    return QualityPolicy(
        quote_max_age=quote_age,
        market_status_max_age=quote_age,
        candle_max_age=candle_max_age,
        future_tolerance=timedelta(minutes=2),
    )


def _decimal(value: object, *, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError(f"{field} deve ser decimal em texto ou inteiro")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field} inválido") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field} deve ser finito")
    return parsed


def build_opportunity_policy(settings: Settings) -> OpportunityPolicy:
    if not settings.opportunity_policy_version:
        raise ValueError(
            "OPPORTUNITY_POLICY_VERSION é obrigatório quando a automação está ativa"
        )
    if not settings.opportunity_rules_json:
        raise ValueError(
            "OPPORTUNITY_RULES_JSON é obrigatório quando a automação está ativa"
        )

    try:
        raw = json.loads(settings.opportunity_rules_json)
    except json.JSONDecodeError as exc:
        raise ValueError("OPPORTUNITY_RULES_JSON contém JSON inválido") from exc

    if not isinstance(raw, list) or not raw:
        raise ValueError("OPPORTUNITY_RULES_JSON deve ser uma lista não vazia")

    rules: list[MetricRule] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"regra {index} deve ser objeto JSON")
        try:
            metric_name = item["metric_name"]
            operator_raw = item["operator"]
            threshold_raw = item["threshold"]
            weight_raw = item["weight"]
            category_raw = item["evidence_category"]
        except KeyError as exc:
            raise ValueError(f"regra {index} possui campo obrigatório ausente") from exc

        if not isinstance(metric_name, str) or not metric_name.strip():
            raise ValueError(f"regra {index}.metric_name deve ser texto não vazio")
        try:
            operator = MetricOperator(operator_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"regra {index}.operator inválido") from exc
        try:
            category = EvidenceCategory(category_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"regra {index}.evidence_category inválido") from exc

        threshold = _decimal(threshold_raw, field=f"regra {index}.threshold")
        weight = _decimal(weight_raw, field=f"regra {index}.weight")
        if weight <= 0 or weight > Decimal("100"):
            raise ValueError(f"regra {index}.weight deve estar entre 0 e 100")

        rules.append(
            MetricRule(
                metric_name=metric_name.strip(),
                operator=operator,
                threshold=threshold,
                weight=weight,
                evidence_category=category.value,
            )
        )

    if settings.opportunity_max_ai_weight > Decimal("100"):
        raise ValueError("OPPORTUNITY_MAX_AI_WEIGHT não pode exceder 100")

    return OpportunityPolicy(
        version=settings.opportunity_policy_version,
        rules=tuple(rules),
        minimum_categories=settings.opportunity_minimum_categories,
        max_ai_weight=settings.opportunity_max_ai_weight,
        max_age=timedelta(
            seconds=settings.automated_pipeline_reference_max_age_seconds
        ),
    )


def validate_automation_settings(settings: Settings) -> None:
    if not settings.automated_pipeline_enabled:
        return
    if not settings.telegram_alert_chat_ids:
        raise ValueError("TELEGRAM_ALERT_CHAT_IDS é obrigatório para automação")
    if settings.pipeline_simulation_enabled:
        if not settings.telegram_dry_run:
            raise ValueError("simulação exige TELEGRAM_DRY_RUN=true")
        if settings.automation_enabled or settings.production_ready:
            raise ValueError(
                "simulação não pode combinar gates de produção ativos"
            )
        if settings.dry_run_allow_ai and (
            not settings.gemini_api_key or not settings.gemini_model
        ):
            raise ValueError(
                "DRY_RUN_ALLOW_AI=true exige GEMINI_API_KEY e GEMINI_MODEL"
            )
    else:
        if settings.telegram_dry_run:
            raise ValueError("TELEGRAM_DRY_RUN exige PIPELINE_SIMULATION_ENABLED=true")
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY é obrigatória para automação")
        if not settings.gemini_model:
            raise ValueError("GEMINI_MODEL é obrigatório para automação")
        if not settings.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN é obrigatória para automação")
    supported = {"brapi", "twelve_data"}
    unknown = set(settings.automated_pipeline_providers) - supported
    if unknown:
        raise ValueError(
            "AUTOMATED_PIPELINE_PROVIDERS contém provider não suportado: "
            + ",".join(sorted(unknown))
        )
    if (
        "twelve_data" in settings.automated_pipeline_providers
        and not settings.twelve_data_api_key
    ):
        raise ValueError(
            "TWELVE_DATA_API_KEY é obrigatória quando twelve_data está na automação"
        )
    if not settings.opportunity_policy_version:
        raise ValueError(
            "OPPORTUNITY_POLICY_VERSION é obrigatório quando a automação está ativa"
        )


def validate_shadow_settings(settings: Settings) -> None:
    """Shadow is deterministic and intentionally does not require Gemini/Telegram."""

    if not settings.shadow_mode_enabled:
        return
    if not settings.shadow_policy_version:
        raise ValueError("SHADOW_POLICY_VERSION é obrigatória para shadow mode")
    _interval(settings.shadow_candle_interval, field="SHADOW_CANDLE_INTERVAL")
